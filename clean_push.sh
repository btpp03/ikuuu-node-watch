#!/bin/bash
set -e
export GH_TOKEN="$(cat /root/.gh_tok)"
cd /root/ikuuu-watch
git rm --cached status.json -q || true
rm -f status.json
git add -A
git -c user.name=btpp03 -c user.email=btpp03@gmail.com commit -q -m "chore: 首次运行前清空 status.json（让首次运行为基线）+ 忽略本地脚本" || echo "无改动"
git push -q origin main
echo "== pushed:"
git log --oneline -2
echo "== 仓库内容:"
git ls-files
