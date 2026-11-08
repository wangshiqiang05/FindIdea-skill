#!/usr/bin/env python3
"""
GitHub 仓库开源真实性审计：基于 GitHub REST API 的机器初判；
API 不可用（限额/网络）时自动降级为 github.com 网页抓取模式。
输出真开源信号、假开源红旗、评分与 verdict 建议（true/partial/fake）。
机器初判不能替代人工实际跑通，最终结论结合 references/opensource-checklist.md。

用法:
  python3 github_audit.py https://github.com/owner/repo
  python3 github_audit.py owner/repo owner/repo2 -o audit.json
  GITHUB_TOKEN=xxx python3 github_audit.py owner/repo     # 提高 API 限额
  python3 github_audit.py owner/repo --no-web-fallback    # 强制仅用 API
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"

DEP_FILES = {"requirements.txt", "environment.yml", "setup.py", "pyproject.toml",
             "Pipfile", "package.json", "poetry.lock", "conda.yaml"}
SKIP_DIRS = {".github", ".gitlab", "docs", "doc", "examples", "assets",
             "figures", "data", ".idea", ".vscode"}
TRAIN_PAT = re.compile(r"(train|run_?train|finetune|fine_tune)", re.I)
INFER_PAT = re.compile(r"(infer|predict|demo|eval|test|generate|transcribe|inference)", re.I)
WEIGHT_URL_PAT = re.compile(
    r"(https?://[^\s)]*(huggingface|drive\.google|zenodo|dropbox|box\.com|s3\.|modelscope)[^\s)]*)",
    re.I)
WEIGHT_WORD_PAT = re.compile(r"(checkpoint|pretrain(ed)?\s*(model|weight)|weight(s)?\s*(download|link))", re.I)
COMING_SOON_PAT = re.compile(r"(code\s+(coming|will\s+be)|coming\s+soon|to\s+be\s+released)", re.I)


def http_get(url, token=None, web=False):
    headers = {"User-Agent": "Mozilla/5.0 cross-domain-idea-mining"}
    if not web:
        headers["Accept"] = "application/vnd.github+json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=30)


def api_get(path, token=None):
    try:
        with http_get(f"{API}{path}", token) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise RuntimeError("rate_limited")
        if e.code == 404:
            raise RuntimeError("not_found")
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")


def parse_repo(s):
    s = s.strip().rstrip("/")
    m = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$", s)
    if m:
        return m.group(1), m.group(2)
    if re.match(r"^[\w.-]+/[\w.-]+$", s):
        return tuple(s.split("/"))
    raise ValueError(f"无法解析仓库标识: {s}")


# ---------------- 数据采集：API 模式 ----------------

def collect_api(owner, repo, token):
    meta = api_get(f"/repos/{owner}/{repo}", token)
    root = api_get(f"/repos/{owner}/{repo}/contents", token)
    root_names = [item["name"] for item in root] if isinstance(root, list) else []
    root_dirs = [item["name"] for item in root
                 if isinstance(root, list) and item.get("type") == "dir"]
    langs = api_get(f"/repos/{owner}/{repo}/languages", token)
    code_bytes = sum(langs.values()) if isinstance(langs, dict) else 0

    readme_text = ""
    readme_item = next((i for i in root
                        if isinstance(root, list) and i["name"].lower().startswith("readme")), None)
    if readme_item:
        rdata = api_get(f"/repos/{owner}/{repo}/contents/{readme_item['name']}", token)
        readme_text = base64.b64decode(rdata["content"]).decode("utf-8", "ignore")

    sub_files = []
    for d in root_dirs:
        if d.lower() in SKIP_DIRS:
            continue
        try:
            items = api_get(f"/repos/{owner}/{repo}/contents/{d}", token)
            if isinstance(items, list):
                sub_files.extend(f"{d}/{i['name']}" for i in items)
        except RuntimeError:
            continue

    has_release = False
    try:
        has_release = bool(api_get(f"/repos/{owner}/{repo}/releases?per_page=1", token))
    except RuntimeError:
        pass

    return {
        "mode": "api",
        "description": meta.get("description"),
        "stars": meta["stargazers_count"],
        "archived": meta["archived"],
        "license_name": (meta.get("license") or {}).get("spdx_id"),
        "root_names": root_names,
        "root_dirs": root_dirs,
        "sub_files": sub_files,
        "readme_text": readme_text,
        "code_bytes": code_bytes,
        "languages": list(langs) if isinstance(langs, dict) else [],
        "pushed_at": meta["pushed_at"],
        "has_release": has_release,
    }


# ---------------- 数据采集：网页降级模式 ----------------

def web_get(url):
    try:
        with http_get(url, web=True) as resp:
            return resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError("not_found")
        raise RuntimeError(f"HTTP {e.code}")


def collect_web(owner, repo):
    html = web_get(f"https://github.com/{owner}/{repo}")
    branches = re.findall(rf"/{re.escape(owner)}/{re.escape(repo)}/(?:blob|tree)/([^/\"#?]+)", html)
    if not branches:
        if "This repository is empty" in html:
            raise RuntimeError("empty_repository")
        raise RuntimeError("无法从页面解析文件树（页面结构可能已变化）")
    branch = branches[0]

    pat = re.compile(rf"/{re.escape(owner)}/{re.escape(repo)}/(?:blob|tree)/"
                     rf"{re.escape(branch)}/([^\"#?]+)")
    entries = sorted({m.group(1) for m in pat.finditer(html)})
    root_names = [e for e in entries if "/" not in e]
    root_dirs = [e for e in entries if "/" not in e and
                 any(x.startswith(e + "/") for x in entries)]
    root_names = [e for e in root_names if e not in root_dirs]

    sub_files = []
    for d in root_dirs:
        if d.lower() in SKIP_DIRS:
            continue
        try:
            sub_html = web_get(f"https://github.com/{owner}/{repo}/tree/{branch}/{d}")
            sub_pat = re.compile(rf"/{re.escape(owner)}/{re.escape(repo)}/(?:blob|tree)/"
                                 rf"{re.escape(branch)}/{re.escape(d)}/([^\"#?]+)")
            sub_files.extend(f"{d}/{m.group(1)}" for m in sub_pat.finditer(sub_html)
                             if "/" not in m.group(1))
        except (urllib.error.URLError, RuntimeError):
            continue

    m = re.search(r'<article class="markdown-body[^"]*"[^>]*>(.*?)</article>', html, re.S)
    readme_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""

    stars = int(re.search(r'"stargazerCount":(\d+)', html).group(1)) \
        if re.search(r'"stargazerCount":(\d+)', html) else None
    archived_m = re.search(r'"isArchived":(true|false)', html)
    lic_m = re.search(r'"license":\{"spdxId":"([^"]+)"', html)
    time_m = re.search(r'relative-time datetime="([^"]+)"', html)

    return {
        "mode": "web-fallback",
        "description": (re.search(r'og:description" content="([^"]*)"', html) or [None, ""])[1],
        "stars": stars,
        "archived": archived_m.group(1) == "true" if archived_m else None,
        "license_name": lic_m.group(1) if lic_m else None,
        "root_names": root_names,
        "root_dirs": root_dirs,
        "sub_files": sub_files,
        "readme_text": readme_text,
        "code_bytes": None,
        "languages": [],
        "pushed_at": time_m.group(1) if time_m else None,
        "has_release": None,
    }


# ---------------- 共用评分逻辑 ----------------

def score(ctx):
    evidence, red_flags = [], []
    score_v = 0
    root_lower = {n.lower(): n for n in ctx["root_names"]}
    root_dirs_lower = [d.lower() for d in ctx["root_dirs"]]
    all_files = [n.lower() for n in ctx["root_names"] if "." in n] + \
                [f.lower() for f in ctx["sub_files"]]

    has_license = bool(ctx["license_name"]) or \
        any(n.lower().startswith("license") for n in ctx["root_names"])
    if has_license:
        score_v += 10
        evidence.append(f"存在许可证: {ctx['license_name'] or 'LICENSE 文件'}")
    else:
        red_flags.append("无 LICENSE 文件（法律意义上不算真正开源）")

    dep_found = sorted({n for n in root_lower if n in DEP_FILES or n.startswith("requirements")})
    if dep_found:
        score_v += 10
        evidence.append(f"依赖声明: {', '.join(dep_found)}")
    else:
        red_flags.append("根目录未发现依赖/安装声明（requirements/setup/pyproject 等）")

    readme_text = ctx["readme_text"]
    if readme_text:
        score_v += 10
        has_guide = bool(re.search(r"(install|usage|getting started|安装|使用|快速开始)", readme_text, re.I))
        evidence.append(f"README 存在{'且含安装/使用说明' if has_guide else '，但缺少安装使用说明'}")
        if not has_guide:
            red_flags.append("README 缺少安装与使用说明")
    else:
        red_flags.append("无 README 或无法读取")

    train_hits = sorted({f for f in all_files if TRAIN_PAT.search(f)}) or \
                 sorted({d for d in root_dirs_lower if TRAIN_PAT.search(d)})
    infer_hits = sorted({f for f in all_files if INFER_PAT.search(f)})
    if train_hits:
        score_v += 20
        evidence.append(f"训练/微调入口: {', '.join(train_hits[:4])}")
    else:
        red_flags.append("未发现训练/微调代码（可能只开放推理 demo，无法复现训练）")
    if infer_hits:
        score_v += 10
        evidence.append(f"推理/评测入口: {', '.join(infer_hits[:4])}")
    else:
        red_flags.append("未发现推理/评测入口")

    has_config = any("config" in f or f.endswith((".yaml", ".yml", ".json")) for f in all_files) \
        or "configs" in root_dirs_lower or "config" in root_dirs_lower
    if has_config:
        score_v += 10
        evidence.append("存在配置文件/配置目录")
    else:
        red_flags.append("未发现配置文件，超参与实验设置不可追溯")

    weight_urls = [m[0] for m in WEIGHT_URL_PAT.findall(readme_text)]
    has_ckpt_dir = any(d in ("checkpoints", "ckpt", "weights", "pretrained") for d in root_dirs_lower)
    if weight_urls or has_ckpt_dir or WEIGHT_WORD_PAT.search(readme_text):
        score_v += 15
        parts = []
        if has_ckpt_dir:
            parts.append("checkpoints 目录")
        if weight_urls:
            parts.append(weight_urls[0])
        evidence.append("权重线索: " + ("; ".join(parts) if parts else "README 文字提及权重"))
    else:
        red_flags.append("未发现预训练权重/ checkpoint 下载线索")

    if ctx["code_bytes"] is not None:
        cb = ctx["code_bytes"]
        if cb >= 100_000:
            score_v += 10
        elif cb >= 10_000:
            score_v += 5
        evidence.append(f"代码体量: {cb:,} 字节，语言: {', '.join(ctx['languages'][:4]) or '无'}")
        if cb < 10_000:
            red_flags.append(f"代码量极小（{cb} 字节），疑似空壳仓库")
    else:
        evidence.append("代码体量: 网页降级模式无法获取（N/A）")

    if ctx["pushed_at"]:
        pushed = datetime.fromisoformat(ctx["pushed_at"].replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - pushed).days
        if age_days <= 180:
            score_v += 3
        evidence.append(f"最近 push: {ctx['pushed_at'][:10]}（{age_days} 天前），"
                        f"stars={ctx['stars']}, archived={ctx['archived']}")
        if age_days > 730:
            red_flags.append(f"超过 2 年无代码推送（{age_days} 天）")
    else:
        evidence.append(f"活跃度: 网页降级模式无法精确获取，stars={ctx['stars']}")

    if ctx["has_release"] is True:
        score_v += 2
        evidence.append("存在 release")
    elif ctx["has_release"] is None:
        evidence.append("release 信息: 网页降级模式 N/A")

    if ctx["archived"]:
        red_flags.append("仓库已被作者归档（archived）")
    if COMING_SOON_PAT.search(readme_text):
        red_flags.append("README 含 'coming soon / to be released' 类长期占位表述")
    if ctx["code_bytes"] is not None and ctx["code_bytes"] < 10_000 and len(all_files) <= 1:
        red_flags.append("根目录几乎只有文档、无实质代码")

    verdict = "true" if score_v >= 70 else ("partial" if score_v >= 40 else "fake")
    return score_v, verdict, evidence, red_flags


def audit(repo_str, token, web_fallback):
    owner, repo = parse_repo(repo_str)
    try:
        ctx = collect_api(owner, repo, token)
    except RuntimeError as e:
        if str(e) == "not_found":
            return {"repo": f"{owner}/{repo}", "error": "仓库不存在或为私有仓库（404）"}
        if not web_fallback:
            return {"repo": f"{owner}/{repo}",
                    "error": "API 不可用且已禁用网页降级（设置 GITHUB_TOKEN 或开启降级）"}
        try:
            ctx = collect_web(owner, repo)
        except RuntimeError as e2:
            if str(e2) == "not_found":
                return {"repo": f"{owner}/{repo}", "error": "仓库不存在或为私有仓库（404）"}
            return {"repo": f"{owner}/{repo}", "error": f"API 与网页降级均失败: {e2}"}

    score_v, verdict, evidence, red_flags = score(ctx)
    return {
        "repo": f"{owner}/{repo}",
        "repo_url": f"https://github.com/{owner}/{repo}",
        "mode": ctx["mode"],
        "description": ctx["description"],
        "score": score_v,
        "verdict_machine": verdict,
        "evidence": evidence,
        "red_flags": red_flags,
        "note": "机器初判，必须人工克隆并实际跑通最小流程后才能最终确认为真开源"
                + ("；网页降级模式结论更弱，优先在 API 模式复核" if ctx["mode"] == "web-fallback" else ""),
    }


def main():
    ap = argparse.ArgumentParser(description="GitHub 开源真实性审计")
    ap.add_argument("repos", nargs="+", help="GitHub URL 或 owner/repo，可多个")
    ap.add_argument("-o", "--output", help="将完整 JSON 结果写入文件")
    ap.add_argument("--no-web-fallback", action="store_true", help="禁用网页降级，强制仅用 API")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    results = []
    for r in args.repos:
        try:
            res = audit(r, token, not args.no_web_fallback)
        except ValueError as e:
            res = {"repo": r, "error": str(e)}
        results.append(res)
        print(f"\n=== {res.get('repo')} ===")
        if "error" in res:
            print(f"  审计失败: {res['error']}")
            continue
        print(f"  模式: {res['mode']}  评分: {res['score']}/100  机器判定: {res['verdict_machine']}")
        for e in res["evidence"]:
            print(f"  [+] {e}")
        for f in res["red_flags"]:
            print(f"  [!] {f}")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nJSON 结果已写入: {args.output}")


if __name__ == "__main__":
    main()
#（注：内容由AI生成）
