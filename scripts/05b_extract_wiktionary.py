"""Step 5b (run locally; kaikki.org is not reachable from every environment):
keep only the Wiktionary entries for our headwords, plus a one-line summary per word.

Wiktionary content: CC BY-SA 4.0 / GFDL. Extracted by wiktextract (Ylonen, LREC 2022), served by kaikki.org.

Usage:
  python scripts/05b_extract_wiktionary.py <kaikki .jsonl or .jsonl.gz> data/processed/vocab_kb2025.csv data/external/wiktionary
writes
  data/external/wiktionary.jsonl   full entries (all senses, examples, sense-linked translations incl. Chinese)
  data/external/wiktionary.csv     word, ipa, gloss (first sense), etymology  -> used by step 5
Works for both the English Wiktionary and the Simple English Wiktionary extracts
(for the latter use a different output prefix, e.g. data/external/simplewiktionary).
"""
import csv, gzip, json, os, sys

src, vocab, out = sys.argv[1:4]
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
need = {r["headword"].lower() for r in csv.DictReader(open(vocab, encoding="utf-8-sig"))}
for extra in ("data/processed/vocab_kb2025_supplement.csv",):
    if os.path.exists(extra):
        need |= {r["word"].lower() for r in csv.DictReader(open(extra, encoding="utf-8-sig"))}

opener = gzip.open if src.endswith(".gz") else open
summary, kept, seen_lines = {}, 0, 0
with opener(src, "rt", encoding="utf-8") as f, open(out + ".jsonl", "w", encoding="utf-8") as fo:
    for line in f:
        seen_lines += 1
        if seen_lines % 200000 == 0:
            print(f"  read {seen_lines:,} lines, kept {kept:,}", flush=True)
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        w = d.get("word", "")
        if w.lower() not in need or d.get("lang_code", "en") != "en":
            continue
        fo.write(line if line.endswith("\n") else line + "\n"); kept += 1
        rec = summary.setdefault(w.lower(), {"word": w, "ipa": "", "gloss": "", "etymology": ""})
        if not rec["ipa"]:
            rec["ipa"] = next((s["ipa"] for s in d.get("sounds", []) if s.get("ipa")), "")
        if not rec["etymology"] and d.get("etymology_text"):
            rec["etymology"] = d["etymology_text"][:400]
        if not rec["gloss"]:
            for s in d.get("senses", []):
                g = (s.get("glosses") or [""])[0]
                if g:
                    rec["gloss"] = f"{d.get('pos', '')}. {g}"; break

with open(out + ".csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["word", "ipa", "gloss", "etymology"])
    w.writeheader(); w.writerows(summary.values())
print(f"read {seen_lines:,} lines; kept {kept:,} entries for {len(summary)} of {len(need)} words")
print(f"wrote {out}.jsonl and {out}.csv")
