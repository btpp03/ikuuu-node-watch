#!/bin/bash
set -e
export GH_TOKEN="$(cat /root/.gh_tok)"
cd /root/ikuuu-watch
git rm --cached -q final_clean.sh final_clean2.sh 2>/dev/null || true
rm -f final_clean.sh final_clean2.sh
printf '%s\n' 'final_clean*.sh' '*_run.sh' 'watch_run.sh' 'check_run.sh' >> .gitignore
sort -u .gitignore -o .gitignore
git add -A
git -c user.name=btpp03 -c user.email=btpp03@gmail.com commit -q -m "chore: 清理本地脚本" || echo "无改动"
git pull --rebase -q origin main || true
git push -q origin main
echo "== 最终仓库文件:"; git ls-files
echo "== 仓库: https://github.com/btpp03/ikuuu-node-watch"
