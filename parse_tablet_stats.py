#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Cowbi's Tablet/Tower modifier catalog directly from PoE2DB, then resolve Trade stat IDs."""
import argparse, json, re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
TRADE_STATS = DATA / "poe2_stats.json"
OUTPUT = DATA / "tablet_stats.json"
SUMMARY = DATA / "tablet_stats_summary.json"
CATALOG = DATA / "tablet_stat_text_catalog.json"

POE2DB_EN = "https://poe2db.tw/Tablet"
POE2DB_CN = "https://poe2db.tw/cn/Tablet"


class TableParser(HTMLParser):
    """Collect table rows while preserving each cell's text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []
            self._buf = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._row is not None and self._cell is not None:
            self._row.append(clean_text(" ".join(self._cell)))
            self._cell = None
            self._buf = []
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def clean_text(value):
    value = re.sub(r"\s+", " ", value or "").strip()
    return value.replace("—", "-").replace("–", "-").replace("\xa0", " ")


def fetch_html(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Cowbi-Tablet-Parser/1.0 (+https://github.com/ChaosSure/Cowbi)"
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_tower_rows(html):
    parser = TableParser()
    parser.feed(html)

    rows = []
    for cells in parser.rows:
        if len(cells) < 3:
            continue
        level, kind = cells[0].strip(), cells[1].strip().lower()
        # PoE2DB uses English "Prefix/Suffix" on /Tablet but Chinese
        # "前缀/后缀" on /cn/Tablet.
        if level == "1" and kind in {"prefix", "suffix", "前缀", "后缀"}:
            rows.append({
                "level": 1,
                "generation_type": "Prefix" if kind in {"prefix", "前缀"} else "Suffix",
                "text": clean_text(" ".join(cells[2:])),
            })
    return rows


def norm_trade_text(value):
    s = clean_text(value).lower()
    s = s.replace(" %", "%")
    s = re.sub(r"\s+", " ", s)
    return s


def load_trade_entries(path):
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)

    groups = payload.get("result", []) if isinstance(payload, dict) else payload
    entries = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_label = group.get("label", "")
        for entry in group.get("entries", []) or []:
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("id"), str) and isinstance(entry.get("text"), str):
                entries.append({
                    **entry,
                    "group": group_label,
                    "_norm": norm_trade_text(entry["text"]),
                })
    return entries


def resolve_trade_id(poedb_text, entries):
    target = norm_trade_text(poedb_text)

    exact = [e for e in entries if e["_norm"] == target]
    if len(exact) == 1:
        return exact[0], "exact"

    # PoE2DB occasionally renders an inline link or punctuation slightly
    # differently from Trade. Only accept a unique containment match.
    candidates = []
    for e in entries:
        a, b = target, e["_norm"]
        if a in b or b in a:
            candidates.append(e)

    if len(candidates) == 1:
        return candidates[0], "contains"

    return None, "unmatched" if not candidates else "ambiguous"


def pair_rows(en_rows, cn_rows):
    if len(en_rows) != len(cn_rows):
        raise RuntimeError(
            f"PoE2DB EN/CN Tower row count differs: EN={len(en_rows)} CN={len(cn_rows)}"
        )

    result = []
    for i, (en, cn) in enumerate(zip(en_rows, cn_rows), start=1):
        if en["generation_type"] != cn["generation_type"]:
            raise RuntimeError(f"Tower row {i}: EN/CN Prefix/Suffix mismatch")
        result.append({
            "index": i,
            "generation_type": en["generation_type"],
            "text_en": en["text"],
            "text_zh": cn["text"],
        })
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade-stats", type=Path, default=TRADE_STATS)
    ap.add_argument("--output", type=Path, default=OUTPUT)
    args = ap.parse_args()

    trade_path = args.trade_stats if args.trade_stats.is_absolute() else BASE / args.trade_stats
    output_path = args.output if args.output.is_absolute() else BASE / args.output

    if not trade_path.exists():
        raise SystemExit(f"ERROR: missing Trade stats file: {trade_path}")

    print("Fetching PoE2DB:", POE2DB_EN)
    en_html = fetch_html(POE2DB_EN)
    print("Fetching PoE2DB:", POE2DB_CN)
    cn_html = fetch_html(POE2DB_CN)

    en_rows = extract_tower_rows(en_html)
    cn_rows = extract_tower_rows(cn_html)

    if len(en_rows) != 90 or len(cn_rows) != 90:
        raise RuntimeError(
            f"Expected 90 Precursor Tower modifiers, got EN={len(en_rows)} CN={len(cn_rows)}"
        )

    tower_rows = pair_rows(en_rows, cn_rows)
    trade_entries = load_trade_entries(trade_path)

    mods = []
    unmatched = []
    ambiguous = []

    for row in tower_rows:
        match, method = resolve_trade_id(row["text_en"], trade_entries)
        item = {
            "index": row["index"],
            "trade_stat_id": match["id"] if match else None,
            "text_en": row["text_en"],
            "text_zh": row["text_zh"],
            "generation_type": row["generation_type"],
            "poedb_source": POE2DB_EN,
            "poedb_cn_source": POE2DB_CN,
            "match_method": method,
        }
        if match:
            item["trade_group"] = match.get("group", "")
            item["trade_text"] = match["text"]
        else:
            if method == "ambiguous":
                ambiguous.append(row)
            else:
                unmatched.append(row)
        mods.append(item)

    output = {
        "version": 3,
        "source": {
            "poedb_en": POE2DB_EN,
            "poedb_cn": POE2DB_CN,
            "trade_stats": "/api/trade2/data/stats",
        },
        "domain": "Tower",
        "expected_count": 90,
        "count": len(mods),
        "matched_count": sum(1 for x in mods if x["trade_stat_id"]),
        "unmatched_count": len(unmatched),
        "ambiguous_count": len(ambiguous),
        "mods": mods,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    summary = {
        "version": 3,
        "source": "PoE2DB Precursor Tower Mods /90 + PoE2 Trade stats",
        "poedb_en_rows": len(en_rows),
        "poedb_cn_rows": len(cn_rows),
        "expected": 90,
        "matched": output["matched_count"],
        "unmatched": output["unmatched_count"],
        "ambiguous": output["ambiguous_count"],
        "status": "PASS" if output["matched_count"] == 90 else "FAIL",
        "unmatched_text": [x["text_en"] for x in unmatched],
        "ambiguous_text": [x["text_en"] for x in ambiguous],
    }

    with SUMMARY.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with CATALOG.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "version": 3,
                "source": "PoE2DB",
                "count": len(tower_rows),
                "rows": tower_rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"PoE2DB Tower Mods: {len(tower_rows)}/90")
    print(f"Trade entries: {len(trade_entries)}")
    print(f"Trade IDs matched: {output['matched_count']}/90")
    print(f"Unmatched: {output['unmatched_count']}")
    print(f"Ambiguous: {output['ambiguous_count']}")

    if unmatched or ambiguous:
        for row in unmatched:
            print("UNMATCHED:", row["index"], row["text_en"])
        for row in ambiguous:
            print("AMBIGUOUS:", row["index"], row["text_en"])
        raise SystemExit(1)

    print("STATUS: PASS")


if __name__ == "__main__":
    main()
