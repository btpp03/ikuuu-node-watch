#!/usr/bin/env python3
"""对比 status.json 与上一次（prev.json），只有状态变化时才推 Telegram。

环境变量：TG_BOT_TOKEN / TG_CHAT_ID / TG_THREAD_ID(可选) / FORCE=1(强制推送)
"""
import json
import os
import sys
import urllib.parse
import urllib.request


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def sig(st):
    return sorted("%s|%s:%s" % (n["name"], n["server"], n["port"])
                  for n in st.get("nodes", []) if n.get("alive"))


def tg(text):
    tok = os.environ.get("TG_BOT_TOKEN", "")
    chat = os.environ.get("TG_CHAT_ID", "")
    if not tok or not chat:
        print("!! 缺少 TG_BOT_TOKEN / TG_CHAT_ID，跳过推送", file=sys.stderr)
        return
    data = {"chat_id": chat, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": "true"}
    th = os.environ.get("TG_THREAD_ID", "").strip()
    if th:
        data["message_thread_id"] = th
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % tok,
        data=urllib.parse.urlencode(data).encode(), method="POST")
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
        print("TG 推送:", r.get("ok"), r.get("description", ""))
    except Exception as e:
        print("!! TG 推送失败:", e, file=sys.stderr)


def main():
    cur = load("status.json")
    if not cur:
        print("!! 没有 status.json", file=sys.stderr)
        return 1
    prev = load("prev.json")
    nodes = cur.get("nodes", [])
    up = [n for n in nodes if n.get("alive")]

    if prev is None:
        head = "🛰 iKuuu 探活已上线（首次基线）"
    elif sig(prev) == sig(cur):
        if os.environ.get("FORCE") == "1":
            head = "🛰 iKuuu 探活（手动测试）"
        else:
            print("状态无变化，不推送。可用节点 %d 个" % len(up))
            return 0
    else:
        head = "🔔 iKuuu 节点状态变化"

    lines = [head, "时间：%s（北京时间）" % __import__("time").strftime(
        "%m-%d %H:%M", __import__("time").gmtime(cur["ts"] + 8 * 3600))]
    if up:
        lines.append("可用 %d/%d：" % (len(up), len(nodes)))
        for n in up:
            lines.append("• %s  %s ms  %s %s" % (
                n["name"], n.get("delay") or "?", n.get("exitIp") or "?",
                n.get("exitGeo") or ""))
    else:
        lines.append("可用 0/%d —— 全部不通（TCP 层就没回应）" % len(nodes))
    sample = [n for n in nodes if not n.get("alive")][:3]
    if sample and up:
        lines.append("不通的：" + "、".join(n["name"].split("-")[-1] for n in sample) + " 等")
    if cur.get("subErrors"):
        lines.append("⚠️ 订阅异常：" + "; ".join(cur["subErrors"]))
    tg("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
