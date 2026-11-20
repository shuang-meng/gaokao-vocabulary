"""Step 2d: merge per-paper corpus files into one table with paper metadata.

Usage: python scripts/02d_build_corpus.py data/interim/corpus papers.csv data/interim/corpus_all.tsv

Columns: paper_id, year, line_code, section, kind, text
Exact duplicate lines within a paper (e.g. a question block printed twice in a 解析卷)
are dropped, except very short lines such as options.
"""
import csv, glob, os, sys
from collections import Counter

src, papers_csv, out = sys.argv[1], sys.argv[2], sys.argv[3]
codes = {}
for r in csv.DictReader(open(papers_csv, encoding="utf-8-sig")):
    codes[f"{r['year']}_{r['line_code']}"] = r["line_code"]

stats = Counter()
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
    w.writerow(["paper_id", "year", "line_code", "section", "kind", "text"])
    for p in sorted(glob.glob(os.path.join(src, "*.tsv"))):
        pid = os.path.basename(p)[:-4]
        year, code = pid.split("_")
        seen = set()
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE):
            t = r["text"].strip()
            if len(t) > 40 and t in seen:
                stats["dup_dropped"] += 1; continue
            seen.add(t)
            w.writerow([pid, year, code, r["section"], r["kind"], t])
            stats["rows"] += 1
print(dict(stats))
