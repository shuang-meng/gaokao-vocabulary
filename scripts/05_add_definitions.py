"""Step 5: attach pronunciation, Chinese gloss, English definitions and word-root hints to entries.

Usage:
  python scripts/05_add_definitions.py data/processed/entries.csv \
      <ECDICT>/ecdict.csv <english-wordnet>/src/yaml <ECDICT>/wordroot.txt \
      data/processed/entries_with_defs.csv [data/external/wiktionary.csv]

Sources (all open licences, attribution in README):
  ECDICT (MIT)                 phonetic, Chinese translation (lines tagged [网络] are dropped),
                               Collins stars, Oxford-3000 flag, exam tags, inflections
  Open English WordNet (CC BY 4.0)  English definitions + examples, top senses per part of speech;
                               part-of-speech order follows the ECDICT Chinese gloss order
  ECDICT wordroot.txt (MIT)    root / affix hints, only when the word is listed as an example of
                               that root (no guessing from spelling)
  Wiktionary via wiktextract (CC BY-SA 4.0), optional: etymology + learner gloss, produced on a
                               machine that can reach kaikki.org by scripts/05b_extract_wiktionary.py
"""
import csv, json, os, re, sys, glob
from collections import defaultdict
import yaml

entries_path, ecdict_path, oewn_dir, wordroot_path, out_path = sys.argv[1:6]
wikt_path = sys.argv[6] if len(sys.argv) > 6 else None
occ_path = os.path.join(os.path.dirname(os.path.dirname(entries_path)), "interim", "occurrences.tsv")
csv.field_size_limit(10 ** 8)

entries = list(csv.DictReader(open(entries_path, encoding="utf-8-sig")))
need = {e["headword"] for e in entries} | {e["headword"].lower() for e in entries}

# ---------- ECDICT ----------
ec = {}
for r in csv.DictReader(open(ecdict_path, encoding="utf-8")):
    w = r["word"]
    if w in need or w.lower() in need:
        ec.setdefault(w, r)

def ec_row(h):
    return ec.get(h) or ec.get(h.lower()) or ec.get(h.capitalize())

def zh_gloss(r, order=None):
    lines = [l.strip() for l in r["translation"].replace("\\n", "\n").split("\n") if l.strip()]
    lines = [l for l in lines if not l.startswith("[网络]") and not l.startswith("[")]
    if order:                                   # put the exam's main part of speech first
        def rank(l):
            m = re.match(r"^\s*([a-z]+)\.", l)
            p = POS_MAP.get(m.group(1)) if m else None
            return order.index(p) if p in order else len(order)
        lines = sorted(lines, key=rank)
    return " | ".join(lines[:4])

POS_MAP = {"n": "n", "v": "v", "vt": "v", "vi": "v", "a": "a", "adj": "a", "ad": "r", "adv": "r"}
UPOS = {"NOUN": "n", "VERB": "v", "ADJ": "a", "ADV": "r", "PROPN": "n"}
exam_pos = defaultdict(lambda: defaultdict(int))     # headword -> {n/v/a/r: count} from exam occurrences
func_share = defaultdict(lambda: [0, 0])             # headword -> [function-word uses, all uses]
FUNC_UPOS = {"AUX", "ADP", "DET", "PRON", "CCONJ", "SCONJ", "PART", "NUM"}
if os.path.exists(occ_path):
    for o in csv.DictReader(open(occ_path, encoding="utf-8"), delimiter="\t"):
        if o.get("upos") in UPOS: exam_pos[o["headword"]][UPOS[o["upos"]]] += 1
        func_share[o["headword"]][1] += 1
        if o.get("upos") in FUNC_UPOS: func_share[o["headword"]][0] += 1

def pos_order(r, h=None):
    """part-of-speech order: as used in the exams first, then ECDICT gloss order."""
    order = [p for p, _ in sorted(exam_pos.get(h, {}).items(), key=lambda x: -x[1])] if h else []
    for l in (r["translation"].replace("\\n", "\n").split("\n") if r else []):
        m = re.match(r"^\s*([a-z]+)\.", l)
        if m and m.group(1) in POS_MAP and POS_MAP[m.group(1)] not in order:
            order.append(POS_MAP[m.group(1)])
    return order + [p for p in ("v", "n", "a", "s", "r") if p not in order]

# ---------- Open English WordNet ----------
L = yaml.CSafeLoader
senses = defaultdict(lambda: defaultdict(list))     # lemma -> pos -> [synset ids]
for f in sorted(glob.glob(os.path.join(oewn_dir, "entries-*.yaml"))):
    data = yaml.load(open(f, encoding="utf-8"), Loader=L)
    for lemma, by_pos in data.items():
        if lemma in need or lemma.lower() in need:
            for pos, d in by_pos.items():
                senses[lemma][pos] += [s["synset"] for s in d.get("sense", [])]
wanted = {sid for lm in senses.values() for ids in lm.values() for sid in ids}
synsets = {}
for f in sorted(glob.glob(os.path.join(oewn_dir, "*.yaml"))):
    if os.path.basename(f).startswith(("entries-", "frames")): continue
    data = yaml.load(open(f, encoding="utf-8"), Loader=L)
    for sid, d in data.items():
        if sid in wanted:
            synsets[sid] = d

POS_EN = {"n": "n.", "v": "v.", "a": "adj.", "s": "adj.", "r": "adv."}
def en_defs(h, order, max_total=3, per_pos=2):
    lm = senses.get(h) or (None if h[:1].isupper() and len(h) > 1 and not h.isupper() else senses.get(h.lower()))
    if not lm: return "", ""
    defs, exs = [], []
    for p in order:
        for sid in lm.get(p, [])[:per_pos]:
            s = synsets.get(sid)
            if not s: continue
            defs.append(f"{POS_EN[p]} {s['definition'][0]}")
            if s.get("example") and len(exs) < 2:
                ex = s["example"][0]
                exs.append(ex["text"] if isinstance(ex, dict) else ex)
            if len(defs) >= max_total: break
        if len(defs) >= max_total: break
    return " | ".join(defs), " | ".join(exs)

# ---------- word roots ----------
roots = json.load(open(wordroot_path, encoding="utf-8"))
root_of = defaultdict(list)
for key, d in roots.items():
    for ex in d.get("example", []):
        root_of[ex.lower()].append(f"{key}（{d.get('meaning', '')}）")

# ---------- Wiktionary (optional) ----------
wikt = {}
if wikt_path and os.path.exists(wikt_path):
    for r in csv.DictReader(open(wikt_path, encoding="utf-8-sig")):
        wikt.setdefault(r["word"].lower(), r)

# ---------- manual overrides (data/manual/zh_gloss_overrides.csv) ----------
manual = {}
man_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(entries_path)))),
                        "data", "manual", "zh_gloss_overrides.csv")
if os.path.exists(man_path):
    for m in csv.DictReader(open(man_path, encoding="utf-8")):
        manual[m["headword"]] = m["zh_gloss"]

# ---------- write ----------
extra = ["phonetic", "exam_pos", "function_word", "zh_gloss", "en_definitions", "en_def_examples", "collins_stars", "oxford3000",
         "exam_tags", "inflections", "word_roots", "etymology"]
stats = defaultdict(int)
with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(entries[0].keys()) + extra)
    w.writeheader()
    for e in entries:
        h = e["headword"]; r = ec_row(h)
        order = pos_order(r, h)
        defs, exs = en_defs(h, order)
        ep = exam_pos.get(h, {}); tot = sum(ep.values())
        exam_pos_txt = " / ".join(f"{POS_EN[p]}{round(100 * c / tot)}%" for p, c in
                                  sorted(ep.items(), key=lambda x: -x[1]) if c / tot >= 0.1) if tot else ""
        wk = wikt.get(h.lower(), {})
        row = dict(e)
        row.update({
            "phonetic": f"/{r['phonetic']}/" if r and r["phonetic"] else (wk.get("ipa", "") if wk else ""),
            "exam_pos": exam_pos_txt,
            "function_word": "1" if func_share[h][1] and func_share[h][0] / func_share[h][1] > 0.5 else "",
            "zh_gloss": manual.get(h) or (zh_gloss(r, order) if r else ""),
            "en_definitions": defs or wk.get("gloss", ""),
            "en_def_examples": exs,
            "collins_stars": r["collins"] if r else "",
            "oxford3000": "1" if r and r["oxford"] == "1" else "",
            "exam_tags": r["tag"] if r else "",
            "inflections": r["exchange"] if r else "",
            "word_roots": "; ".join(re.sub(r"\d", "", x) for x in root_of.get(h.lower(), [])[:3]),
            "etymology": wk.get("etymology", ""),
        })
        for k in ("phonetic", "zh_gloss", "en_definitions", "word_roots", "etymology"):
            if row[k]: stats[k] += 1
        w.writerow(row)
print(f"entries {len(entries)}  " + "  ".join(f"{k}:{v}" for k, v in stats.items()))
