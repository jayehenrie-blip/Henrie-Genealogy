#!/usr/bin/env python3
"""Sanity checks on a GEDCOM: parents born too close to (or after) their children, etc.
Usage: python3 tools/check_gedcom.py data/henrie.ged"""
import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
recs = {m.group(1): m.group(2) for m in re.finditer(r"0 @(\w+)@ \w+\n((?:[1-9].*\n)*)", t)}
def name(i): m = re.search(r"1 NAME (.*)", recs[i]); return m.group(1).replace("/", "") if m else i
def by(i):
    m = re.search(r"1 BIRT\n(?:[2-9].*\n)*?2 DATE .*?(\d{4})", recs[i]); return int(m.group(1)) if m else None
bad = []
for f, body in recs.items():
    if not f.startswith("F"): continue
    pars = re.findall(r"1 (?:HUSB|WIFE) @(\w+)@", body)
    for c in re.findall(r"1 CHIL @(\w+)@", body):
        cy = by(c)
        for p in pars:
            py = by(p)
            if cy and py and not (12 <= cy - py <= 70):
                bad.append(f"{f}: {name(p)} (b. {py}) parent of {name(c)} (b. {cy})")
print(f"{len(bad)} parent/child age problems")
print("\n".join(bad[:40]))
