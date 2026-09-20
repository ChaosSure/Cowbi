#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve PoE2 Tablet/Tower modifier descriptions to official Trade stat IDs."""
import argparse,json,re
from pathlib import Path
BASE=Path(__file__).resolve().parent; DATA=BASE/"data"
INPUT=DATA/"poe2_stats.json"; OUTPUT=DATA/"tablet_stats.json"; SUMMARY=DATA/"tablet_stats_summary.json"; CATALOG=DATA/"tablet_stat_text_catalog.json"

# Tower modifier descriptions. A stat is accepted only when it matches this
# whitelist; words like map/waystone/boss alone are never used for discovery.
PATTERNS=[
"(8-12)% increased Rarity of Items found in Map","Map has (30-40)% increased Magic Monsters","Map has (25-35)% increased number of Rare Monsters","Map has (15-20)% increased Monster Rarity","Map contains (2-3) additional Rare Chests","Unique Monsters have 1 additional Rare Modifiers",
"Unstable Breaches in Map spawn (1-2) additional Rare Monsters when Stabilised","(5-20)% increased Effectiveness of Rare Breach Monsters in Map","(15-30)% increased Quantity of Breach Splinters dropped by Breach Monsters in Map","(30-60)% increased Quantity of Hiveblood found in Map","(30-60)% increased Quantity of Wombgifts found in Map",
"(25-35)% increased number of Rare Expedition Monsters in Map","The first (1-2) unearthed Runic Monsters will be Rare Monsters in Map","(15-25)% increased Expedition Monster Rarity in Map","(15-25)% increased Quantity of Expedition Logbooks dropped by Runic Monsters in Map","(15-30)% increased quantity of Expedition Artifacts dropped by Monsters in Map","Expeditions contain (1-2) Additional Bosses encased in ice in Map",
"Slaying Rare Monsters in Map pauses the Delirium Mirror Timer for (3-5) seconds","Delirium Encounters in Map are (15-30)% more likely to spawn Unique Bosses",
"Revived Monsters from Ritual Altars in Map have (35-70)% increased chance to be Magic","Revived Monsters from Ritual Altars in Map have (25-40)% increased chance to be Rare",
"(18-30)% increased Quantity of Waystones dropped by Map Bosses","(13-20)% increased Quantity of Items dropped by Map Bosses","(40-80)% increased Experience gained from Map Bosses","(35-60)% increased Rarity of Items dropped by Map Bosses",
"(2-3) additional Rare Monsters are spawned from Abysses in Map","(10-25)% chance to add a Vaal Beacon Unique Monster to the Map","(30-60)% increased chance Vaal Beacon Chests are Rare in Map",
"(4-10)% increased Quantity of Items found in Map","(30-40)% increased Quantity of Waystones found in Map","% reduced Pack Size in Map","% increased Quantity of Waystones found in Map","Map contains 1 additional Shrines","Map contains 1 additional Strongboxes","Map contains 1 additional Essences","Map contains 1 additional Azmeri Spirits","Map is inhabited by 1 additional Rogue Exiles",
]
UNIQUE=[
"Breach Hives in Map have (2-5) additional waves of Hiveborn Monsters","Breaches in Map have (-10-20)% reduced Pack Size","Unstable Breaches in Map take 120 additional seconds to collapse after timer is filled","Unstable Breaches in Map spawn (2-5) additional Rare Monsters when Stabilised",
"Expedition Monsters in your Maps spawn with half of their Life missing","Runic Monsters in your Maps are Duplicated","Favours at Ritual Altars in Area costs (10-15)% increased Tribute","Can Reroll Favours at Ritual Altars in your Maps twice as many times",
"Map Bosses are Hunted by Azmeri Spirits","Map Bosses have 1 additional Modifiers","Can only be applied to Precursor Tower Maps","Completing the Tower makes all nearby Maps accessible","If the Map has not been Irradiated, it becomes Irradiated when completed",
"Map also counts as a Water Area","Map also counts as a Mountain Area","Map also counts as a Grass Area","Map also counts as a Forest Area","Map also counts as a Swamp Area",
"% more Waystones found in Area","additional Rare Monsters are spawned from Abysses in Map","Map contains (14-18) additional Abysses","Map is overrun by the Abyssal"
]
def norm(s): return re.sub(r"\s+"," ",s.replace("—","-").replace("–","-")).strip().lower()
def eq(a,b): a,b=norm(a),norm(b); return a==b or a in b or b in a
def load(p):
    with p.open(encoding="utf-8") as f:return json.load(f)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,default=INPUT); ap.add_argument("--output",type=Path,default=OUTPUT); a=ap.parse_args()
    inp=a.input if a.input.is_absolute() else BASE/a.input; out=a.output if a.output.is_absolute() else BASE/a.output
    if not inp.exists(): print("ERROR: missing",inp); return 2
    payload=load(inp); groups=payload.get("result",[]) if isinstance(payload,dict) else payload
    entries=[]
    for g in groups:
        if not isinstance(g,dict): continue
        for e in g.get("entries",[]) or []:
            if isinstance(e,dict) and isinstance(e.get("id"),str) and isinstance(e.get("text"),str):
                entries.append({**e,"group":g.get("label","")})
    catalog=[]; found={}; stats=[]
    for kind,patterns in (("tower",PATTERNS),("unique_tablet",UNIQUE)):
        for p in patterns:
            ids=[e["id"] for e in entries if eq(p,e["text"])]
            catalog.append({"pattern":p,"kind":kind,"matched_trade_ids":ids,"matched":bool(ids)})
            for e in entries:
                if eq(p,e["text"]) and e["id"] not in found:
                    x={k:e[k] for k in ("id","text","group","type","option","disabled") if k in e}; x["tablet_kind"]=kind; x["source_pattern"]=p; found[e["id"]]=x
    stats=list(found.values())
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8") as f: json.dump({"version":2,"source":"PoE2 Trade API /api/trade2/data/stats","domain":"Tablet / Tower","count":len(stats),"stats":stats},f,ensure_ascii=False,indent=2)
    summary={"version":2,"method":"PoE2DB Tower whitelist -> Trade stat text -> original Trade stat ID","count":len(stats),"matched_patterns":sum(x["matched"] for x in catalog),"unmatched_patterns":[x["pattern"] for x in catalog if not x["matched"]],"tower_patterns":len(PATTERNS),"unique_patterns":len(UNIQUE),"trade_groups":sorted(set(e["group"] for e in stats))}
    with SUMMARY.open("w",encoding="utf-8") as f: json.dump(summary,f,ensure_ascii=False,indent=2)
    with CATALOG.open("w",encoding="utf-8") as f: json.dump({"version":1,"entries":catalog},f,ensure_ascii=False,indent=2)
    print(f"Trade entries: {len(entries)}; Tablet/Tower IDs: {len(stats)}; matched: {summary['matched_patterns']}/{len(catalog)}")
    for p in summary["unmatched_patterns"]: print("UNMATCHED:",p)
if __name__=="__main__": raise SystemExit(main())
