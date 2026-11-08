#!/usr/bin/env python3
"""
跨领域 idea 挖掘台账（JSONL）：记录每篇论文从开源核验、idea 生成、
新颖性验证到代码改造的全流程状态，保证可追溯、可断点续做。

用法:
  python3 idea_ledger.py init [--ledger ledger.jsonl]
  python3 idea_ledger.py add --paper-title "..." --venue CVPR --year 2025 \
      --paper-url URL --repo-url URL --source-domain "Agent 长序列" --target-domain VLM
  python3 idea_ledger.py update P001 --set oss_verdict=true --set idea_title="..."
  python3 idea_ledger.py list [--oss true] [--novelty novel]
  python3 idea_ledger.py show P001
  python3 idea_ledger.py stats
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

FIELDS = [
    "id", "created_at", "updated_at", "paper_title", "authors", "venue", "year",
    "paper_url", "source_domain", "target_domain", "repo_url",
    "oss_verdict", "oss_evidence", "idea_title", "idea_summary",
    "novelty_verdict", "novelty_evidence", "adaptation_status", "code_path", "notes",
]
ENUMS = {
    "oss_verdict": {"true", "partial", "fake", "none"},
    "novelty_verdict": {"novel", "partial", "duplicate", "unknown"},
    "adaptation_status": {"pending", "in_progress", "done"},
}
DEFAULTS = {"oss_verdict": "none", "novelty_verdict": "unknown",
            "adaptation_status": "pending"}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load(ledger):
    if not ledger.exists():
        sys.exit(f"台账不存在: {ledger}，先运行 init")
    return [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]


def save(ledger, rows):
    ledger.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")


def next_id(rows):
    nums = [int(r["id"][1:]) for r in rows if r.get("id", "").startswith("P")]
    return f"P{max(nums, default=0) + 1:03d}"


def cmd_init(args):
    ledger = Path(args.ledger)
    if ledger.exists():
        sys.exit(f"台账已存在: {ledger}")
    ledger.write_text("")
    print(f"已创建空台账: {ledger.resolve()}")


def cmd_add(args):
    ledger = Path(args.ledger)
    rows = load(ledger) if ledger.exists() else []
    if any(r.get("paper_url") == args.paper_url and args.paper_url for r in rows):
        sys.exit("该 paper_url 已存在于台账，避免重复录入")
    record = {f: "" for f in FIELDS}
    record.update(DEFAULTS)
    for f in FIELDS:
        val = getattr(args, f, None)
        if val is not None:
            record[f] = val
    record["id"] = next_id(rows)
    record["created_at"] = record["updated_at"] = now()
    rows.append(record)
    save(ledger, rows)
    print(f"已添加 {record['id']}: {record['paper_title'][:60]}")


def cmd_update(args):
    ledger = Path(args.ledger)
    rows = load(ledger)
    for r in rows:
        if r["id"] == args.record_id:
            for pair in args.set:
                if "=" not in pair:
                    sys.exit(f"--set 需要 key=value 格式: {pair}")
                k, v = pair.split("=", 1)
                if k not in FIELDS:
                    sys.exit(f"未知字段: {k}，可选: {', '.join(FIELDS)}")
                if k in ENUMS and v not in ENUMS[k]:
                    sys.exit(f"{k} 取值必须为: {', '.join(sorted(ENUMS[k]))}")
                r[k] = v
            r["updated_at"] = now()
            save(ledger, rows)
            print(f"已更新 {args.record_id}")
            return
    sys.exit(f"未找到记录: {args.record_id}")


def cmd_list(args):
    rows = load(Path(args.ledger))
    if args.oss:
        rows = [r for r in rows if r["oss_verdict"] == args.oss]
    if args.novelty:
        rows = [r for r in rows if r["novelty_verdict"] == args.novelty]
    if not rows:
        print("无匹配记录")
        return
    cols = [("id", 7), ("paper_title", 36), ("venue", 12), ("year", 8),
            ("oss_verdict", 13), ("novelty_verdict", 17), ("adaptation_status", 19)]
    header = "".join(f"{name:<{w}}" for name, w in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        print("".join(f"{str(r.get(name, ''))[:w - 1]:<{w}}" for name, w in cols))


def cmd_show(args):
    for r in load(Path(args.ledger)):
        if r["id"] == args.record_id:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return
    sys.exit(f"未找到记录: {args.record_id}")


def cmd_stats(args):
    rows = load(Path(args.ledger))
    n = len(rows)
    print(f"论文总数: {n}")
    for stage, key, want in [
        ("真开源（机器初判 true）", "oss_verdict", "true"),
        ("已生成 idea", "idea_title", None),
        ("新颖性验证通过（novel）", "novelty_verdict", "novel"),
        ("代码改造完成", "adaptation_status", "done"),
    ]:
        if want:
            c = sum(1 for r in rows if r.get(key) == want)
        else:
            c = sum(1 for r in rows if r.get(key))
        print(f"  {stage}: {c}")
    if n:
        print("漏斗淘汰:")
        print(f"  开源环节淘汰 {n - sum(1 for r in rows if r['oss_verdict'] == 'true')} 篇；"
              f"新颖性环节淘汰/存疑 "
              f"{sum(1 for r in rows if r['novelty_verdict'] in ('duplicate', 'partial'))} 篇")


def build_parser():
    p = argparse.ArgumentParser(description="跨领域 idea 挖掘台账")
    p.add_argument("--ledger", default="ledger.jsonl")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    add = sub.add_parser("add")
    for f in FIELDS:
        if f in ("id", "created_at", "updated_at"):
            continue
        add.add_argument(f"--{f.replace('_', '-')}", dest=f)
    add.set_defaults(func=cmd_add)

    upd = sub.add_parser("update")
    upd.add_argument("record_id")
    upd.add_argument("--set", action="append", required=True)
    upd.set_defaults(func=cmd_update)

    lst = sub.add_parser("list")
    lst.add_argument("--oss", choices=sorted(ENUMS["oss_verdict"]))
    lst.add_argument("--novelty", choices=sorted(ENUMS["novelty_verdict"]))
    lst.set_defaults(func=cmd_list)

    show = sub.add_parser("show")
    show.add_argument("record_id")
    show.set_defaults(func=cmd_show)

    sub.add_parser("stats").set_defaults(func=cmd_stats)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
#（注：内容由AI生成）
