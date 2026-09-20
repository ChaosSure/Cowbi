#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Cowbi's Tablet/Tower modifier catalog directly from PoE2DB and resolve Trade stat IDs."""
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
    """Collect table rows and preserve <br> boundaries inside cells."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []
            self._buf = []
        elif tag == "br" and self._cell is not None:
            self._cell.append("\n")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "td" and self._row is not None and self._cell is not None:
            self._row.append(clean_text("".join(self._cell)))
            self._cell = None
            self._buf = []
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def clean_text(value):
    value = re.sub(r"[ \t\r\f\v]+", " ", value or "")
    value = re.sub(r" *\n+ *", "\n", value)
    return value.strip().replace("—", "-").replace("–", "-").replace("\xa0", " ")


def fetch_html(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Cowbi-Tablet-Parser/2.0 (+https://github.com/ChaosSure/Cowbi)"
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize_description(text):
    """Keep the complete <td> as one modifier.

    PoE2DB uses <br> inside some Tower modifier descriptions. Those line
    breaks are part of the same modifier, not separate mods.
    """
    text = clean_text(text)
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    parts = [
        p for p in parts
        if not re.fullmatch(r"[a-z0-9_ +%.-]+\[\d+\]", p, flags=re.I)
    ]
    return clean_text(" ".join(parts))


def extract_tower_rows(html):
    parser = TableParser()
    parser.feed(html)

    rows = []
    for cells in parser.rows:
        if len(cells) < 3:
            continue
        level = cells[0].strip()
        kind_raw = cells[1].strip().lower()
        if level != "1" or kind_raw not in {"prefix", "suffix", "前缀", "后缀"}:
            continue
        generation_type = "Prefix" if kind_raw in {"prefix", "前缀"} else "Suffix"
        # One HTML <tr> is one Tower modifier. Some descriptions contain
        # <br>, but those are continuation lines of the same modifier.
        description = normalize_description(" ".join(cells[2:]))
        if description:
            rows.append({
                "level": 1,
                "generation_type": generation_type,
                "text": description,
            })
    return rows


def norm_trade_text(value):
    s = clean_text(value).lower()
    s = s.replace(" %", "%")
    s = s.replace("#", "#")
    s = re.sub(r"\([^)]*\)", "#", s)
    s = re.sub(r"\b(?:an|1)\s+additional\b", "# additional", s)
    s = re.sub(r"\badditional\b", "# additional", s)
    s = re.sub(r"\b(?:map|area)\b", "area", s)

    # PoE2DB and Trade use slightly different pluralisation for these nouns.
    plural_map = {
        "circles": "circle", "exiles": "exile", "spirits": "spirit",
        "essences": "essence", "shrines": "shrine", "strongboxes": "strongbox",
        "abysses": "abyss", "breaches": "breach", "monsters": "monster",
        "chests": "chest", "rewards": "reward", "modifiers": "modifier",
        "waystones": "waystone", "mirrors": "mirror", "shards": "shard",
        "bosses": "boss", "players": "player", "favours": "favour",
        "omens": "omen", "beacons": "beacon", "crystals": "crystal",
        "packs": "pack", "remnants": "remnant", "relics": "relic",
        "sentires": "sentire", "sentries": "sentry",
    }
    for a, b in plural_map.items():
        s = re.sub(rf"\b{re.escape(a)}\b", b, s)

    # Trade sometimes uses '#' where PoE2DB has a literal fixed value.
    s = re.sub(r"\b1\s+extra\b", "# extra", s)
    s = re.sub(r"\b1\s+additional\b", "# additional", s)
    s = re.sub(r"\s+", " ", s).strip()
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
    # Duplicate texts are normally Area/Map aliases sharing the same stat ID.
    if exact:
        ids = {e["id"] for e in exact}
        if len(ids) == 1:
            return exact[0], "normalized-exact"

    # Fallback: token containment, but only when it resolves to one stat ID.
    candidates = []
    target_tokens = set(re.findall(r"[a-z0-9+#]+", target))
    for e in entries:
        et = e["_norm"]
        etokens = set(re.findall(r"[a-z0-9+#]+", et))
        if not target_tokens or not etokens:
            continue
        overlap = len(target_tokens & etokens)
        coverage = overlap / max(1, min(len(target_tokens), len(etokens)))
        if (target in et or et in target) and coverage >= 0.90:
            candidates.append((coverage, e))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if candidates:
        best = candidates[0][0]
        best_ids = {e["id"] for score, e in candidates if score == best}
        if len(best_ids) == 1:
            return candidates[0][1], "contains"
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
    en_rows = extract_tower_rows(fetch_html(POE2DB_EN))
    print("Fetching PoE2DB:", POE2DB_CN)
    cn_rows = extract_tower_rows(fetch_html(POE2DB_CN))
    print(f"Parsed PoE2DB rows: EN={len(en_rows)} CN={len(cn_rows)}")

    if len(en_rows) != 90 or len(cn_rows) != 90:
        raise RuntimeError(
            f"Expected 90 Precursor Tower modifiers, got EN={len(en_rows)} CN={len(cn_rows)}"
        )

    tower_rows = pair_rows(en_rows, cn_rows)
    trade_entries = load_trade_entries(trade_path)

    mods, unmatched, ambiguous = [], [], []
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
        elif method == "ambiguous":
            ambiguous.append(row)
        else:
            unmatched.append(row)
        mods.append(item)

    output = {
        "version": 4,
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

    with SUMMARY.open("w", encoding="utf-8") as f:
        json.dump({
            "version": 4,
            "source": "PoE2DB Precursor Tower Mods /90 + PoE2 Trade stats",
            "poedb_en_rows": len(en_rows),
            "poedb_cn_rows": len(cn_rows),
            "expected": 90,
            "matched": output["matched_count"],
            "unmatched": len(unmatched),
            "ambiguous": len(ambiguous),
            "status": "PASS" if output["matched_count"] == 90 else "FAIL",
            "unmatched_text": [x["text_en"] for x in unmatched],
            "ambiguous_text": [x["text_en"] for x in ambiguous],
        }, f, ensure_ascii=False, indent=2)

    with CATALOG.open("w", encoding="utf-8") as f:
        json.dump({
            "version": 4,
            "source": "PoE2DB",
            "count": len(tower_rows),
            "rows": tower_rows,
        }, f, ensure_ascii=False, indent=2)

    print(f"PoE2DB Tower Mods: {len(tower_rows)}/90")
    print(f"Trade entries: {len(trade_entries)}")
    print(f"Trade IDs matched: {output['matched_count']}/90")
    print(f"Unmatched: {len(unmatched)}")
    print(f"Ambiguous: {len(ambiguous)}")
    for row in unmatched:
        print("UNMATCHED:", row["index"], row["text_en"])
    for row in ambiguous:
        print("AMBIGUOUS:", row["index"], row["text_en"])

    if unmatched or ambiguous:
        raise SystemExit(1)
    print("STATUS: PASS")


if __name__ == "__main__":
    main()
