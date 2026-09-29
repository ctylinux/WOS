#!/usr/bin/env python3
"""把本地目录推送到 GitHub 仓库并在需要时开启 GitHub Pages。

用法: python3 upload_portal.py <本地目录> <仓库内子路径> [<Pages 分支> <Pages 目录>]
例:   python3 upload_portal.py $WOS_WORKDIR/portal_publish portal main /
令牌从 ~/.hermes/.env 读取，经 GIT_ASKPASS 传给 git，不进命令行。
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
REPO = "ctylinux/WOS"
SRC = sys.argv[1] if len(sys.argv) > 1 else f"{W}/portal_publish"
SUBDIR = (sys.argv[2] if len(sys.argv) > 2 else "portal").strip("/")
PG_BRANCH = sys.argv[3] if len(sys.argv) > 3 else ""
PG_PATH = sys.argv[4] if len(sys.argv) > 4 else "/"
WORK = "/tmp/wos_repo_push"
ASKPASS = "/tmp/.wos_askpass.sh"

tok = next((l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/.hermes/.env"), encoding="utf-8")
            if l.startswith("GITHUB_TOKEN=")), None)
assert tok, "未在 ~/.hermes/.env 找到 GITHUB_TOKEN"
with open(ASKPASS, "w") as f:
    f.write('#!/bin/sh\ncase "$1" in *[Uu]sername*) echo "x-access-token" ;; *) echo "$GIT_TOKEN" ;; esac\n')
os.chmod(ASKPASS, 0o700)

env = dict(os.environ, GIT_ASKPASS=ASKPASS, GIT_TOKEN=tok, GIT_TERMINAL_PROMPT="0",
           GIT_AUTHOR_NAME="ctylinux", GIT_COMMITTER_NAME="ctylinux",
           GIT_AUTHOR_EMAIL="ctylinux@users.noreply.github.com",
           GIT_COMMITTER_EMAIL="ctylinux@users.noreply.github.com")


def git(*args, cwd=WORK):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    print(f"  git {args[0]}: {p.returncode} {out[-150:]}")
    if p.returncode != 0:
        raise SystemExit(f"git {args} 失败")
    return p


shutil.rmtree(WORK, ignore_errors=True)
git("clone", f"https://github.com/{REPO}.git", WORK, cwd="/tmp")

dst = f"{WORK}/{SUBDIR}"
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(SRC, dst)
n = sum(len(f) for _, _, f in os.walk(dst))
# 站点根索引：直接重定向到门户，方便 https://<user>.github.io/WOS/ 也能打开
if SUBDIR != "" and not os.path.exists(f"{WORK}/index.html"):
    open(f"{WORK}/index.html", "w", encoding="utf-8").write(
        '<!doctype html><meta charset="utf-8"><title>高校WOS论文收录智能分析月报系统</title>'
        f'<meta http-equiv="refresh" content="0;url=./{SUBDIR}/">'
        f'<p>正在跳转…<a href="./{SUBDIR}/">进入门户</a></p>')
print(f"待推送 {n} 个文件 → {SUBDIR}/")

git("add", "-A")
if not subprocess.run(["git", "status", "--porcelain"], cwd=WORK, capture_output=True, text=True).stdout.strip():
    print("无变更")
else:
    git("commit", "-m", f"feat: 发布作品门户到 /{SUBDIR}/（公开演示版：已隐去作者姓名）")
    br = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=WORK,
                        capture_output=True, text=True).stdout.strip()
    git("push", "-u", "origin", f"HEAD:{br}")


def api(path="", method="GET", payload=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}" + (f"/{path}" if path else ""),
                                 method=method,
                                 data=json.dumps(payload).encode() if payload else None,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Accept": "application/vnd.github+json",
                                          "User-Agent": "hermes-portal"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


if PG_BRANCH:
    st, body = api("pages")
    if st == 200:
        print(f"Pages 已启用：{body.get('html_url')} （来源 {body.get('source')}）")
    else:
        st2, body2 = api("pages", "POST", {"source": {"branch": PG_BRANCH, "path": PG_PATH}})
        print(f"启用 Pages: HTTP {st2} {body2.get('html_url') or body2.get('message')}")

st, tree = api(f"contents/{SUBDIR}")
print(f"\n[校验] 远端 /{SUBDIR}/ 顶层 {len(tree)} 项")
st2, page = api("pages")
if st2 == 200:
    print(f"[校验] Pages: {page.get('html_url')} | 状态 {page.get('status')} | 来源 {page.get('source')}")
