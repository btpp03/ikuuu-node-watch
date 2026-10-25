#!/usr/bin/env python3
"""对比 status.json 与上一次（prev.json），决定要不要推 Telegram。

推送时机（三选一）：
  1. 首次运行 → 基线消息
  2. 可用节点集合有变化 → 变化消息
  3. 连续 MONTHLY_DAYS 天（默认 30）没有任何变化 → 月度「still 挂/still 一样」提醒

推完会把 {sig, ts} 记回 status.json 的 notify 字段，跟着仓库一起保存。
环境变量：TG_BOT_TOKEN / TG_CHAT_ID / TG_THREAD_ID(可选) / FORCE=1 / DRYRUN=1 / MONTHLY_DAYS=30
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

DAYS = float(os.environ.get("MONTHLY_DAYS", "30"))


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def sig(st):
    return sorted("%s|%s:%s" % (n["name"], n["server"], n["port"])
                  for n in st.get("nodes", []) if n.get("alive"))


def bj(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts + 8 * 3600))


def tg(text):
    if os.environ.get("DRYRUN") == "1":
        print("---- DRYRUN 消息 ----\n%s\n--------------------" % text)
        return True
    tok = os.environ.get("TG_BOT_TOKEN", "")
    chat = os.environ.get("TG_CHAT_ID", "")
    if not tok or not chat:
        print("!! 缺少 TG_BOT_TOKEN / TG_CHAT_ID，跳过推送", file=sys.stderr)
        return False
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
        return bool(r.get("ok"))
    except Exception as e:
        print("!! TG 推送失败:", e, file=sys.stderr)
        return False


def build(cur, prev, kind, last_ts):
    nodes = cur.get("nodes", [])
    up = [n for n in nodes if n.get("alive")]
    if kind == "baseline":
        head = "🛰 iKuuu 探活已上线（首次基线）"
    elif kind == "change":
        was = len([n for n in (prev or {}).get("nodes", []) if n.get("alive")])
        head = "🔔 iKuuu 节点状态变化（%d → %d 可用）" % (was, len(up))
    elif kind == "monthly":
        head = "📅 iKuuu 探活月报：这 %d 天没有变化" % int(DAYS)
    else:
        head = "🛰 iKuuu 探活（手动测试）"

    lines = [head, "时间：%s 北京时间" % bj(cur["ts"])]
    if up:
        lines.append("当前可用 %d/%d：" % (len(up), len(nodes)))
        for n in up:
            lines.append("• %s  %s ms  %s %s" % (n["name"], n.get("delay") or "?",
                                                 n.get("exitIp") or "?", n.get("exitGeo") or ""))
    else:
        lines.append("当前可用 0/%d —— 全部不通（TCP 层就没回应）" % len(nodes))
        ips = [n.get("ip") for n in nodes if n.get("ip")]
        if ips:
            lines.append("后端 IP 仍是这 %d 个：%s" % (len(ips), "、".join(ips[:4])
                                                     + ("…" if len(ips) > 4 else "")))
    if kind == "monthly" and last_ts:
        lines.append("上次推送是 %s，距今已超过 %d 天。" % (bj(last_ts), int(DAYS)))
        lines.append("要不要继续等这个免费机场，你自己判断；想停就删了这个 workflow。")
    if cur.get("subErrors"):
        lines.append("⚠️ 订阅异常：" + "; ".join(cur["subErrors"]))
    return "\n".join(lines)


def main():
    cur = load("status.json")
    if not cur:
        print("!! 没有 status.json", file=sys.stderr)
        return 1
    prev = load("prev.json")
    state = cur.get("notify") or {}
    last_ts = int(state.get("ts") or 0)
    now = int(time.time())
    sig_now = sig(cur)

    if prev is None:
        kind = "baseline"
    elif sig(prev) != sig_now:
        kind = "change"
    elif os.environ.get("FORCE") == "1":
        kind = "forced"
    elif last_ts == 0:
        # 升级后第一次跑：只记录时间，不发消息
        print("初始化推送时间记录，本轮静默（%d 天后若无变化发月报）" % int(DAYS))
        cur["notify"] = {"sig": sig_now, "ts": now}
        json.dump(cur, open("status.json", "w"), ensure_ascii=False, indent=1)
        return 0
    elif now - last_ts >= DAYS * 86400:
        kind = "monthly"
    else:
        age = (now - last_ts) / 86400 if last_ts else 0
        print("状态无变化，不推送。可用 %d 个，距上次推送 %.1f 天（满 %d 天会发月报）"
              % (len([n for n in cur.get("nodes", []) if n.get("alive")]), age, int(DAYS)))
        cur["notify"] = {"sig": sig_now, "ts": last_ts or now}
        json.dump(cur, open("status.json", "w"), ensure_ascii=False, indent=1)
        return 0

    ok = tg(build(cur, prev, kind, last_ts))
    cur["notify"] = {"sig": sig_now, "ts": now if ok else last_ts}
    json.dump(cur, open("status.json", "w"), ensure_ascii=False, indent=1)
    print("已写回 status.json notify.ts=%s" % cur["notify"]["ts"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
