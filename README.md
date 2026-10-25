# ikuuu-node-watch

iKuuu 免费日本节点的自动探活。跑在 GitHub Actions 云 runner 上，不占任何自己的机器。

每天拉一次订阅 → 解析节点 → TCP 探测 → 对 TCP 通的节点再用 mihomo 真连测延迟和出口 IP → **只有状态变化时**才推 Telegram。

## 为什么需要它

iKuuu 免费线的后端是共享 IP 的临时机器，经常整批宕机被回收，而面板里的节点列表更新慢于真实机器（2026-10-25 实测：订阅里 7 个 AWS 东京 IP，42 次端口探测全超时、ICMP 全无回包）。这个仓库就是替你盯着——节点恢复的第一时间你手机会收到消息。

## 配置（Settings → Secrets and variables → Actions）

| Secret | 必填 | 说明 |
|---|---|---|
| `IKU_SUBS` | ✅ | 订阅链接，多条用英文逗号分隔。`?clash=3&extend=1` 和 `?shadowrocket=1` 两种都支持，可只填一条 |
| `TG_BOT_TOKEN` | ✅ | Telegram bot token |
| `TG_CHAT_ID` | ✅ | 接收消息的 chat id |
| `TG_THREAD_ID` | 选填 | 想推到某个话题才填，留空则发到私聊默认位置 |

> 订阅链接里有你账号的 UUID，**只放 secret，绝不写进代码或 issue**。仓库是 public，`status.json` 里已剔除 uuid 字段。

## 手动跑一次

Actions → `ikuuu-watch` → Run workflow。

本地跑：

```bash
pip install pyyaml
IKU_SUBS="https://xxx/link/TOKEN?clash=3&extend=1" \
TG_BOT_TOKEN=... TG_CHAT_ID=... \
DEEP=0 python3 probe.py        # 只看探活结果，不推送
```

`DEEP=1`（默认）会尝试下载/使用 mihomo 做真连测试；找不到 mihomo 会自动跳过，不影响 TCP 探活结论。

## 定时（重要）

GitHub 原生 `schedule` 在部分账号上几乎不触发。workflow 里已经写了 `cron: "0 23 * * *"`（北京时间 07:00），但更可靠的做法是再挂一个**外部定时腿**：在 [cron-job.org](https://cron-job.org) 建一个每天 07:00（北京）的任务，URL 填：

```
https://api.github.com/repos/btpp03/ikuuu-node-watch/actions/workflows/watch.yml/dispatches
```

- Method：`POST`
- Headers：
  - `Authorization: Bearer <一个只给这个仓库 actions:write 权限的 fine-grained PAT>`
  - `Accept: application/vnd.github+json`
- Body：`{"ref":"main"}`

两条腿同时存在也没关系：第二次跑发现状态没变就不会推送，不会刷屏。

## 推送策略

- 首次运行：发一条「已上线」基线
- 状态不变（可用节点集合相同）：**静默**
- 有节点恢复 / 掉线：立即发一条，带延迟、出口 IP、归属地
- **连续 30 天没有任何变化**：发一条月度提醒（还是全挂也一样会说一声）
- 订阅拉取失败（token 失效等）：消息里带 ⚠️

「上次推送时间」记在 `status.json` 的 `notify` 字段里，跟着仓库走，所以 runner 无状态也能算准天数。想改周期就设 secret `MONTHLY_DAYS`（默认 30），或手动跑时加 env。

## 文件

- `probe.py` — 拉订阅、解析、探活、真连测试，写 `status.json`
- `notify.py` — 和上一次 `status.json` 比对，变化才推 TG
- `status.json` — 最近一次结果（已脱敏，可公开）
