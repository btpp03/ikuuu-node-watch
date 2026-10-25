#!/bin/bash
set -e
export GH_TOKEN="$(cat /root/.gh_tok)"
R=btpp03/ikuuu-node-watch
cd /root/ikuuu-watch
echo "== status.json 里是否有 uuid / id 泄露:"
curl -s -H "Authorization: Bearer $GH_TOKEN" "https://api.github.com/repos/$R/contents/status.json" \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); t=base64.b64decode(d['content']).decode(); print('uuid' in t, '\"id\"' in t, len(t), 'B'); print(t[:200])"
echo "== 清理仓库内的一次性脚本:"
git rm --cached -q dispatch.sh 2>/dev/null || true
printf '%s\n' 'dispatch.sh' 'watch_run.sh' 'check_run.sh' >> .gitignore
git add -A
git -c user.name=btpp03 -c user.email=btpp03@gmail.com commit -q -m "chore: 忽略本地运维脚本" || echo "无改动"
git push -q origin main
echo "== 最终仓库文件:"; git ls-files
