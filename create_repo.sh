#!/bin/bash
set -e
export GH_TOKEN=$(cat /root/.gh_tok)
cd /root/ikuuu-watch
git init -b main 2>/dev/null || true
git add -A
git -c user.name=btpp03 -c user.email=btpp03@gmail.com commit -m "feat: iKuuu 免费节点探活 + Telegram 推送" || true
gh repo create btpp03/ikuuu-node-watch --public --source=. --remote=origin --push \
  --description "iKuuu 免费日本节点自动探活（GitHub Actions + Telegram 通知）"
echo "== repo created"
git log --oneline -1
gh repo view btpp03/ikuuu-node-watch --json url,visibility -q '.url + " " + .visibility'
