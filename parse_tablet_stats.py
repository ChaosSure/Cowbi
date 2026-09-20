#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract PoE2 Tablet-related Trade stats from data/poe2_stats.json.

Input:
  data/poe2_stats.json

Output:
  data/tablet_stats.json
  data/tablet_stats_summary.json

The official /api/trade2/data/stats response is grouped as:
  {"result": [{"label": "...", "entries": [...]}]}

This script intentionally keeps the original Trade stat IDs and does not
invent IDs. Tablet detection is heuristic and records the matched keywords
so the result can be audited/refined later.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT = DATA_DIR / "poe2_stats.json"
OUTPUT = DATA_DIR / "tablet_stats.json"
SUMMARY = DATA_DIR / "tablet_stats_summary.json"

# Keep this list broad for discovery. We will refine it after inspecting the
# extracted result rather than silently dropping possible tablet modifiers.
KEYWORDS = (
    "tablet",
    "precursor tablet",
    "precursor",
    "area contains",
    "map",
    "waystone",
    "expedition",
    "ritual",
    "breach",
    "delirium",
    "abyss",
    "strongbox",
    "boss",
    "rare monsters",
    "magic monsters",
    "pack size",
    "quantity of items",
    "rarity of items",
)

# Common stat categories. We preserve the upstream group label verbatim.
CATEGORY_HINTS = {
    "explicit": re.compile(r"explicit", re.I),
    "implicit": re.compile(r"implicit", re.I),
    "enchant": re.compile(r"enchant", re.I),
    "pseudo": re.compile(r"pseudo", re.I),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def keyword_matches(text: str) -> list[str]:
    value = normalize(text)
    return [k for k in KEYWORDS if k in value]


def category_for(label: str) -> str:
    for name, pattern in CATEGORY_HINTS.items():
        if pattern.search(label):
            return name
    return "other"


def extract_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        groups = payload.get("result", [])
    elif isinstance(payload, list):
        groups = payload
    else:
        groups = []

    if not isinstance(groups, list):
        raise ValueError("poe2_stats.json 的 result 不是数组")

    output: list[dict[str, Any]] = []

    for group in groups:
        if not isinstance(group, dict):
            continue

        label = str(group.get("label", ""))
        entries = group.get("entries", [])
        if not isinstance(entries, list):
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            stat_id = entry.get("id")
            text = entry.get("text")

            # Trade IDs are the critical output. Ignore malformed entries.
            if not isinstance(stat_id, str) or not stat_id.strip():
                continue
            if not isinstance(text, str) or not text.strip():
                continue

            matches = keyword_matches(text)
            if not matches:
                # Also inspect option labels when a stat uses a selectable value.
                option = entry.get("option")
                option_text = ""
                if isinstance(option, dict):
                    option_text = " ".join(
                        str(v) for v in option.values() if isinstance(v, (str, int, float))
                    )
                matches = keyword_matches(f"{text} {option_text}")

            if not matches:
                continue

            item = {
                "id": stat_id,
                "text": text,
                "group": label,
                "category": category_for(label),
                "tablet_match_keywords": matches,
            }

            # Preserve useful upstream fields without copying arbitrary payload.
            for key in ("type", "option", "disabled"):
                if key in entry:
                    item[key] = entry[key]

            output.append(item)

    # Deduplicate by Trade stat ID while preserving first occurrence.
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in output:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        deduped.append(item)

    return deduped


def build_summary(stats: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_group: dict[str, int] = {}

    for stat in stats:
        by_category[stat["category"]] = by_category.get(stat["category"], 0) + 1
        group = stat["group"]
        by_group[group] = by_group.get(group, 0) + 1

    return {
        "input": str(INPUT.relative_to(BASE_DIR)),
        "output": str(OUTPUT.relative_to(BASE_DIR)),
        "count": len(stats),
        "by_category": dict(sorted(by_category.items())),
        "by_group": dict(sorted(by_group.items())),
        "keywords": list(KEYWORDS),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    input_path = args.input if args.input.is_absolute() else BASE_DIR / args.input
    output_path = args.output if args.output.is_absolute() else BASE_DIR / args.output
    summary_path = output_path.with_name("tablet_stats_summary.json")

    if not input_path.exists():
        print(f"ERROR: 找不到输入文件: {input_path}")
        print("请先运行 fetch_poe2_data.py，或把已经获取的 poe2_stats.json 放进 data/。")
        return 2

    payload = load_json(input_path)
    stats = extract_entries(payload)
    summary = build_summary(stats)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "version": 1,
                "source": "PoE2 Trade API /api/trade2/data/stats",
                "count": len(stats),
                "stats": stats,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print("PoE2 Tablet Stats Extractor")
    print("=" * 70)
    print(f"输入: {input_path}")
    print(f"输出: {output_path}")
    print(f"提取数量: {len(stats)}")
    print()
    print("分类:")
    for key, value in summary["by_category"].items():
        print(f"  {key}: {value}")
    print()
    print("前 20 条:")
    for stat in stats[:20]:
        print(f"  [{stat['id']}] {stat['text']}")
    print()
    print(f"摘要: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
