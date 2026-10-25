#!/bin/bash
set -e
export GH_TOKEN="$(cat /root/.gh_tok)"
cd /root/ikuuu-watch
git rm --cached -q create_repo.sh clean_push.sh
printf '%s\n' 'create_repo.sh' 'clean_push.sh' >> .gitignore
git add -A
git -c user.name=btpp03 -c user.email=btpp03@gmail.com commit -q -m "chore: 移除本地一次性脚本"
git push -q origin main
echo "== tracked:"; git ls-files
echo "== 触发 workflow:"
gh workflow run watch.yml -R btpp03/ikuuu-node-watch --ref main
sleep 12
gh run list -R btpp03/ikuuu-node-watch --limit 3
