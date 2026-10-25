#!/usr/bin/env python3
"""iKuuu 免费节点探活：拉订阅 → 解析节点 → TCP 探测 →（存活时）真连测延迟/出口 IP。

输出 status.json（供下次运行做对比）+ 控制台 Markdown 报告。
环境变量：
  IKU_SUBS   订阅链接，逗号或换行分隔（必填）
  DEEP       1=对 TCP 通的节点做真连测试（默认 1）
  MIHOMO     mihomo 可执行文件路径（默认 ./bin/mihomo）
"""
import base64
import concurrent.futures
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import ssl

UA_SR = "Shadowrocket/2.2.60 (iPhone; iOS 17.0; Scale/3.00)"
UA_CLASH = "clash-verge/v2.0.0 mihomo/1.19.11"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
TMO = 8


def b64d(s):
    s = re.sub(r"\s+", "", s).replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4))


def fetch(url):
    ua = UA_SR if "shadowrocket" in url else UA_CLASH
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return r.read().decode("utf-8", "ignore").strip()


def parse_nodes(text):
    """返回 [{name, server, port, tls, raw}]，支持 clash yaml 与 base64 v2ray 两种订阅。"""
    nodes = []
    if "proxies:" in text[:3000] or text.startswith(("mixed-port:", "port:", "mode:")):
        try:
            import yaml
        except ImportError:
            print("!! 缺少 pyyaml，无法解析 clash 订阅", file=sys.stderr)
            return nodes
        cfg = yaml.safe_load(text) or {}
        for p in cfg.get("proxies") or []:
            nodes.append({"name": str(p.get("name")), "type": p.get("type"),
                          "server": str(p.get("server")), "port": int(p.get("port") or 0),
                          "tls": bool(p.get("tls")), "proxy": p})
        return nodes
    body = text
    if "://" not in text[:200]:
        try:
            body = b64d(text).decode("utf-8", "ignore")
        except Exception:
            return nodes
    for line in body.splitlines():
        line = line.strip()
        if not line.lower().startswith("vmess://"):
            continue
        try:
            j = json.loads(b64d(line[8:]))
        except Exception:
            continue
        nodes.append({"name": j.get("ps") or j.get("add"), "type": "vmess",
                      "server": j.get("add"), "port": int(j.get("port") or 0),
                      "tls": j.get("tls") == "tls", "vmess": j})
    return nodes


def tcp_ok(ip, port, tmo=TMO):
    s = socket.socket()
    s.settimeout(tmo)
    try:
        s.connect((ip, port))
        return True, "open"
    except socket.timeout:
        return False, "timeout"
    except ConnectionRefusedError:
        return False, "refused"
    except Exception as e:
        return False, type(e).__name__
    finally:
        s.close()


def probe_all(nodes):
    def one(n):
        try:
            ip = socket.gethostbyname(n["server"])
        except Exception as e:
            n.update(ip=None, tcp=False, why="dns-%s" % type(e).__name__)
            return n
        ok, why = tcp_ok(ip, n["port"])
        n.update(ip=ip, tcp=ok, why="open" if ok else why)
        return n

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        return list(ex.map(one, nodes))


def clash_proxies(nodes):
    out = []
    for n in nodes:
        if n.get("proxy"):
            out.append(n["proxy"])
            continue
        j = n["vmess"]
        p = {"name": n["name"], "type": "vmess", "server": n["server"], "port": n["port"],
             "uuid": j.get("id"), "alterId": int(j.get("aid") or 0), "cipher": "auto",
             "network": j.get("net") or "tcp", "udp": True, "client-fingerprint": "chrome"}
        if j.get("tls") == "tls":
            p["tls"] = True
            p["servername"] = j.get("host") or j["server"]
        if (j.get("net") or "tcp") == "ws":
            p["ws-opts"] = {"path": j.get("path") or "/", "headers": {"Host": j.get("host") or j["server"]}}
        out.append(p)
    return out


def deep_test(nodes):
    """对 TCP 通的节点起 mihomo，测握手延迟与出口 IP。"""
    alive = [n for n in nodes if n.get("tcp")]
    if not alive:
        return
    mihomo = os.environ.get("MIHOMO", "./bin/mihomo")
    if not os.path.exists(mihomo):
        print("!! 找不到 mihomo，跳过真连测试：%s" % mihomo, file=sys.stderr)
        return
    names = [n["name"] for n in alive]
    cfg = {
        "mixed-port": 7890, "allow-lan": False, "mode": "rule", "log-level": "error",
        "external-controller": "127.0.0.1:9090",
        "proxies": clash_proxies(alive),
        "proxy-groups": [{"name": "T", "type": "select", "proxies": names}],
        "rules": ["MATCH,T"],
    }
    import tempfile
    import yaml
    d = tempfile.mkdtemp()
    yp = os.path.join(d, "config.yaml")
    open(yp, "w").write(yaml.safe_dump(cfg, allow_unicode=True))
    proc = subprocess.Popen([mihomo, "-d", d, "-f", yp], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            time.sleep(0.5)
            try:
                urllib.request.urlopen("http://127.0.0.1:9090/version", timeout=2).read()
                break
            except Exception:
                continue

        def api(path, method="GET", body=None):
            req = urllib.request.Request("http://127.0.0.1:9090" + path, method=method,
                                         data=json.dumps(body).encode() if body else None,
                                         headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read().decode() or "null")

        for n in alive:
            try:
                api("/proxies/T", "PUT", {"name": n["name"]})
                time.sleep(0.3)
                dly = api("/proxies/" + urllib.parse.quote(n["name"]) +
                          "/delay?timeout=8000&url=" +
                          urllib.parse.quote("http://www.gstatic.com/generate_204"))
                n["delay"] = dly.get("delay")
            except Exception:
                n["delay"] = None
            try:
                out = subprocess.run(
                    ["curl", "-s", "--max-time", "20", "-x", "http://127.0.0.1:7890",
                     "http://ip-api.com/json/?fields=status,country,city,query,isp"],
                    capture_output=True, text=True, timeout=30).stdout.strip()
                j = json.loads(out) if out.startswith("{") else {}
                if j.get("status") == "success":
                    n["exitIp"] = j.get("query")
                    n["exitGeo"] = "%s/%s" % (j.get("country"), j.get("city"))
                    n["exitIsp"] = j.get("isp")
                else:
                    n["exitIp"] = None
            except Exception:
                n["exitIp"] = None
            n["alive"] = bool(n.get("delay"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def main():
    subs = [s.strip() for s in re.split(r"[,\s]+", os.environ.get("IKU_SUBS", "")) if s.strip()]
    if not subs:
        print("!! 未设置 IKU_SUBS", file=sys.stderr)
        return 1
    nodes, errors = [], []
    for u in subs:
        try:
            text = fetch(u)
            got = parse_nodes(text)
            tag = "clash" if "clash" in u else "shadowrocket"
            print("订阅(%s) %s… → %d 个节点" % (tag, u.split("/link/")[-1][:12], len(got)))
            nodes += got
        except Exception as e:
            errors.append("%s: %s" % (u.split("/link/")[-1][:12], e))
            print("订阅拉取失败 %s: %s" % (u.split("/link/")[-1][:12], e), file=sys.stderr)

    probe_all(nodes)
    # 按解析后的 IP+端口去重（两种订阅格式的入口域名随机、后端其实是同一台机器）
    seen, uniq = set(), []
    for n in nodes:
        k = (n.get("ip") or n["server"], n["port"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(n)
    if os.environ.get("DEEP", "1") == "1":
        deep_test(uniq)
    for n in uniq:
        if "alive" not in n:
            n["alive"] = False

    # 只保留可公开字段，绝不能让 uuid / 原始链接进 repo（repo 是 public）
    safe_keys = ("name", "type", "server", "port", "tls", "ip", "tcp", "why",
                 "delay", "exitIp", "exitGeo", "exitIsp", "alive")
    safe = [{k: n.get(k) for k in safe_keys if k in n} for n in uniq]

    status = {"ts": int(time.time()), "time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
              "nodes": safe, "subErrors": errors}
    # 把上次推送记录带过来（notify.py 会更新它）
    try:
        prev = json.load(open("prev.json"))
        if isinstance(prev.get("notify"), dict):
            status["notify"] = prev["notify"]
    except Exception:
        pass
    json.dump(status, open("status.json", "w"), ensure_ascii=False, indent=1)

    up = [n for n in uniq if n.get("alive")]
    print("\n## iKuuu 探活 %s（北京时间 %s）" % (status["time"], time.strftime(
        "%Y-%m-%d %H:%M", time.gmtime(time.time() + 8 * 3600))))
    print("节点 %d 个，TCP 通 %d，真连可用 %d" % (len(uniq), sum(1 for n in uniq if n.get("tcp")), len(up)))
    for n in uniq:
        print("| %s | %s:%s | TCP %s | 延迟 %s | 出口 %s |" % (
            n["name"], n["server"], n["port"], "✅" if n.get("tcp") else "❌ " + str(n.get("why")),
            n.get("delay") or "-", n.get("exitIp") or "-"))
    if errors:
        print("订阅错误：%s" % "; ".join(errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
