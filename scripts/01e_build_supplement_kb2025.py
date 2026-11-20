"""Supplement list for the 课标 2025 word list.

The 课标 词汇表 lists countries separately and does not list numerals, months or weekdays
(they belong to the 义务教育 stage). To keep them from being counted as off-list words, this
script combines the 课标 country table with the numeral/month/weekday rows of the 考纲 supplement.

Usage: python scripts/01e_build_supplement_kb2025.py data/processed/vocab_kb2025_countries.csv \
           data/processed/vocab_supplement.csv data/processed/vocab_kb2025_supplement.csv
"""
import csv, sys
countries, old_supp, out = sys.argv[1:4]
rows, seen = [], set()
def add(w, cat, extra=""):
    for x in [p.strip() for p in w.split("/") if p.strip()]:
        if (x.lower(), cat) not in seen:
            seen.add((x.lower(), cat)); rows.append([x, cat, extra])
for r in csv.DictReader(open(countries, encoding="utf-8-sig")):
    add(r["country"], "country", f"person:{r['person']};adj:{r['adjective']}")
    for x in (r["person"], r["adjective"]):
        if x != r["country"]: add(x, "nationality")
for r in csv.DictReader(open(old_supp, encoding="utf-8-sig")):
    if r["category"] in ("numeral", "month", "weekday"):
        add(r["word"], r["category"], r["extra"])
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["word", "category", "extra"]); w.writerows(rows)
print(len(rows))
