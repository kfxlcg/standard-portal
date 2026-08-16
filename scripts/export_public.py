#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""私有产物 -> 公开产物：字段白名单 + 泄漏校验 + 规模/体积断言

用法（私有侧导出）：
  python export_public.py \
    --registry <私有 registry.json> \
    --demo <私有 enrich.json> \
    --demo-id ZJXFZN-2020 \
    --demo-title "浙江省消防难点问题操作技术指南（2020版）" \
    --demo-source-url https://openstd.samr.gov.cn/bzgk/std/ \
    --outdir data/public

用法（公开仓库 CI 部署前校验）：
  python export_public.py --check --outdir data/public [--expect 30000]

任何校验失败都会非零退出，不写入/不允许部署。
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------------ 白名单
PUBLIC_FIELDS = [
    "code", "title", "issue",
    "release_date", "implementation_date", "abolition_date",
    "category", "reference_count",
    "doc_type", "level", "source_url",
]
FIELD_MAP = {
    "code": "code", "title": "title", "issue": "issue",
    "releaseDate": "release_date", "implementationDate": "implementation_date",
    "abolitionDate": "abolition_date", "folderName": "category",
    "referenceCount": "reference_count",
}

# ------------------------------------------------------------------ 泄漏探测
FORBIDDEN_HOSTS = ("isdp-gw.com", "isdp-gw")
OFFICIAL_HOSTS = ("openstd.samr.gov.cn", "std.samr.gov.cn", "www.mohurd.gov.cn", "mohurd.gov.cn")
MAX_TITLE_LEN = 200
MAX_SUMMARY_LEN = 400
SIZE_LIMITS = {
    "catalog.json": 20 * 1024 * 1024,
    "stats.json": 100 * 1024,
    "demo.json": 2 * 1024 * 1024,
}
DEFAULT_EXPECT_TOTAL = 30000
TOLERANCE = 0.005

DOC_TYPE_RULES = [
    ("国标", re.compile(r"^GB")),
    ("图集", re.compile(r"^\d{2}[A-Z]{1,3}\d{2,}")),
    ("地标", re.compile(r"^DB")),
    ("协会标准", re.compile(r"^(?:CECS|T/)")),
    ("行标", re.compile(r"^(?:JGJ|CJJ|JG/T|CJ/T|TB|DL|SH|HG|SY|JT|CJ)")),
]
LEVEL_RULES = [
    ("national", re.compile(r"^GB")),
    ("local", re.compile(r"^DB")),
    ("association", re.compile(r"^(?:CECS|T/)")),
    ("industry", re.compile(r"^(?:JGJ|CJJ|JG/T|CJ/T|TB|DL|SH|HG|SY|JT|CJ)")),
]


def _match(code, rules, default):
    for val, rx in rules:
        if rx.match(code or ""):
            return val
    return default


def _host(url):
    if not url:
        return ""
    m = re.match(r"https?://([^/]+)", url)
    return (m.group(1) if m else "").lower()


def official_url(code, raw_url):
    """只保留官方域名链接；内部/未知域名一律替换为官方平台入口。"""
    if _host(raw_url) in OFFICIAL_HOSTS:
        return raw_url
    if re.match(r"^(GB|DB|CECS|T/)", code or ""):
        return "https://openstd.samr.gov.cn/bzgk/std/"
    return "https://www.mohurd.gov.cn/"


def to_catalog_item(raw):
    it = {k: raw.get(src) for src, k in FIELD_MAP.items()}
    it["source_url"] = official_url(it["code"], raw.get("linkUrl") or raw.get("linkOutSite"))
    it["doc_type"] = _match(it["code"], DOC_TYPE_RULES, "其他")
    it["level"] = _match(it["code"], LEVEL_RULES, "other")
    return {k: it[k] for k in PUBLIC_FIELDS}


def to_demo_item(entry, standard_id, standard_title, source_url):
    related = []
    for r in entry.get("related", []) or []:
        related.append({
            "article": r.get("article", ""),
            "relation": r.get("relation", ""),
            "note": r.get("note", ""),
        })
    return {
        "standard_id": standard_id,
        "standard_title": standard_title,
        "article_no": entry.get("article_no", ""),
        "summary": (entry.get("summary") or "").strip(),
        "tags": entry.get("tags", []) or [],
        "related": related,
        "source_url": source_url,
    }


def check_item(item, kind, errors, idx):
    for k, v in item.items():
        if isinstance(v, str):
            if any(h in v.lower() for h in FORBIDDEN_HOSTS):
                errors.append(f"[{kind}] 第{idx}条 {k} 含内部域名: {v[:80]}")
            if k in ("title", "category", "article_no") and len(v) > MAX_TITLE_LEN:
                errors.append(f"[{kind}] 第{idx}条 {k} 超长: {len(v)} 字符")
            if k == "summary" and len(v) > MAX_SUMMARY_LEN:
                errors.append(f"[{kind}] 第{idx}条 summary 超长: {len(v)} 字符")
            if re.search(r"data:image|base64,", v, re.I):
                errors.append(f"[{kind}] 第{idx}条 {k} 疑似内嵌文件: {v[:80]}")


def check_artifacts(outdir, expect=None):
    errors = []
    for fname, limit in SIZE_LIMITS.items():
        p = Path(outdir) / fname
        if not p.exists():
            errors.append(f"缺少公开产物: {p}")
            continue
        if p.stat().st_size > limit:
            errors.append(f"{fname} 超过体积上限 {limit} 字节: {p.stat().st_size}")
        data = json.loads(p.read_text(encoding="utf-8"))
        for i, it in enumerate(data.get("items", [])):
            check_item(it, fname, errors, i)
        if fname == "catalog.json" and expect and data.get("meta", {}).get("total"):
            total = data["meta"]["total"]
            lo, hi = int(expect * (1 - TOLERANCE)), int(expect * (1 + TOLERANCE))
            if not (lo <= total <= hi):
                errors.append(f"catalog.json 条数异常: {total}（期望约 {expect}）")
    return errors


def export(registry, outdir, demo=None, demo_id="", demo_title="", demo_source_url="", expect=DEFAULT_EXPECT_TOTAL, stats_extra=None):
    raw = json.loads(Path(registry).read_text(encoding="utf-8"))
    items = raw.get("items") if isinstance(raw, dict) else raw
    total = len(items)
    lo, hi = int(expect * (1 - TOLERANCE)), int(expect * (1 + TOLERANCE))
    if not (lo <= total <= hi):
        raise SystemExit(f"FAIL: registry 条数 {total} 不在期望范围 [{lo}, {hi}]")

    catalog = [to_catalog_item(it) for it in items]
    errors = []
    for i, it in enumerate(catalog):
        check_item(it, "catalog.json", errors, i)
        if not it["code"] or not it["title"]:
            errors.append(f"catalog.json 第{i}条缺少 code/title")
    if errors:
        raise SystemExit("FAIL:\n" + "\n".join(errors))

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    catalog_payload = {
        "meta": {
            "source": "国家标准全文公开系统 openstd.samr.gov.cn 等官方公开题录",
            "generated_at": now,
            "total": total,
            "version": "0.1.0",
        },
        "items": catalog,
    }
    (out / "catalog.json").write_text(
        json.dumps(catalog_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    by_issue, by_doc = {}, {}
    for it in catalog:
        by_issue[it["issue"] or "未知"] = by_issue.get(it["issue"] or "未知", 0) + 1
        by_doc[it["doc_type"]] = by_doc.get(it["doc_type"], 0) + 1
    stats_payload = {
        "meta": {"generated_at": now, "version": "0.1.0"},
        "registry": {"total": total, "by_issue": by_issue, "by_doc_type": by_doc},
        **({} if not stats_extra else stats_extra),
    }
    (out / "stats.json").write_text(
        json.dumps(stats_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if demo:
        demo_raw = json.loads(Path(demo).read_text(encoding="utf-8"))
        entries = demo_raw.get("enrich", demo_raw.get("items", demo_raw))
        demo_items = [to_demo_item(e, demo_id, demo_title, demo_source_url) for e in entries]
        demo_errors = []
        for i, it in enumerate(demo_items):
            check_item(it, "demo.json", demo_errors, i)
        if demo_errors:
            raise SystemExit("FAIL:\n" + "\n".join(demo_errors))
        demo_payload = {
            "meta": {
                "standards": [demo_id],
                "note": "演示子集：仅条文号 + 自写摘要 + 官方链接，不含条文原文",
                "generated_at": now,
                "version": "0.1.0",
            },
            "items": demo_items,
        }
        (out / "demo.json").write_text(
            json.dumps(demo_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"OK: catalog {total} 条 / stats / demo 已写入 {out}")


def main():
    ap = argparse.ArgumentParser(description="公开产物导出与校验")
    ap.add_argument("--registry", help="私有 registry.json 路径")
    ap.add_argument("--demo", help="私有 enrich.json 路径（演示子集来源）")
    ap.add_argument("--demo-id", default="")
    ap.add_argument("--demo-title", default="")
    ap.add_argument("--demo-source-url", default="https://openstd.samr.gov.cn/bzgk/std/")
    ap.add_argument("--stats-extra", help="可选的治理/评测统计 JSON（合并进 stats.json）")
    ap.add_argument("--outdir", default="data/public")
    ap.add_argument("--expect", type=int, default=None,
                    help="期望条数（导出模式默认 30000；--check 模式下不指定则跳过条数断言）")
    ap.add_argument("--check", action="store_true", help="只校验现有产物，不导出")
    args = ap.parse_args()

    if args.check:
        errors = check_artifacts(args.outdir, args.expect)
        if errors:
            raise SystemExit("FAIL:\n" + "\n".join(errors))
        print("OK: 公开产物校验通过")
        return

    if not args.registry:
        ap.error("导出模式需要 --registry（私有 registry.json 路径）")
    expect = args.expect if args.expect is not None else DEFAULT_EXPECT_TOTAL
    stats_extra = None
    if args.stats_extra:
        stats_extra = json.loads(Path(args.stats_extra).read_text(encoding="utf-8"))
    export(
        args.registry, args.outdir, args.demo,
        args.demo_id, args.demo_title, args.demo_source_url,
        expect, stats_extra,
    )


if __name__ == "__main__":
    main()
