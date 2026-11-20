"""Step 1b: parse raw vocab lines into a clean headword table.

Input : data/interim/vocab_lines.tsv  (from 01a)
Output: data/processed/vocab_3500.csv
        data/interim/vocab_parse_issues.tsv  (lines that need a human look)

Each output row is one headword (homographs merged, POS unioned).
`forms` lists every surface form that should count toward this headword
(irregular forms, plurals, US spellings, optional-letter variants, abbreviations).
"""
import csv, re, sys
from collections import OrderedDict

IN, OUT, ISSUES = sys.argv[1], sys.argv[2], sys.argv[3]

POS_TOKENS = r"(?:modal v|aux v|link v|v\(be\)|n|v|a|ad|adv|prep|pron|conj|art|num|int|abbr)"
POS_RE = re.compile(rf"\s+({POS_TOKENS}(?:\s*(?:&|,)\s*{POS_TOKENS})*)\s*$")
SKIP_RE = re.compile(r"^(\d+|[A-Z]|附录|5|词汇表)$")

# ---------- 1. read lines, stop at 数词 ----------
lines = []
with open(IN, encoding="utf-8") as f:
    for page, col, n, text in csv.reader(f, delimiter="\t"):
        if text in ("数词", "基数词", "序数词"):
            # numerals block on the last page: drop the rest of this column
            stop_key = (page, col)
            lines.append(("STOP", page, col))
            continue
        lines.append((text, page, col))

clean = []
stopped = set()
for item in lines:
    if item[0] == "STOP":
        stopped.add((item[1], item[2])); continue
    text, page, col = item
    if (page, col) in stopped: continue
    text = text.replace("’", "'").strip()
    if SKIP_RE.match(text): continue
    clean.append((text, page))

# ---------- 2. merge continuation lines ----------
def has_pos(s): return bool(POS_RE.search(s))
def unbalanced(s): return s.count("(") > s.count(")")

merged = []
for text, page in clean:
    if merged:
        prev, ppage = merged[-1]
        if (not has_pos(prev)) and (text.startswith(("(", "或", "="))
                                    or unbalanced(prev) or prev.endswith((",", ";"))):
            merged[-1] = (prev + " " + text, ppage); continue
    merged.append((text, page))

# ---------- 3. parse each entry ----------
def norm_pos(p):
    p = p.replace("v(be)", "v").replace("adv", "ad")
    parts = re.split(r"\s*(?:&|,)\s*", p)
    return [x.strip() for x in parts if x.strip()]

def expand_ed(base, form):
    if form in ("-ed",):
        return base + ("d" if base.endswith("e") else "ed")
    return form

entries, issues = OrderedDict(), []
OVERRIDES = {  # raw line -> list of (headword, forms)
    "can (could); can't=cannot modal v": [("can", ["could", "can't", "cannot"])],
}
for raw, page in merged:
    if raw in OVERRIDES:
        for h, fs in OVERRIDES[raw]:
            e = entries.setdefault(h, {"headword": h, "pos": [], "forms": [], "notes": [], "page": page, "raw": []})
            if "modal v" not in e["pos"]: e["pos"].append("modal v")
            e["forms"] += [f for f in fs if f not in e["forms"]]; e["raw"].append(raw)
            if len(e["raw"]) > 1: e["homograph"] = True
        continue
    m = POS_RE.search(raw)
    if not m:
        issues.append((page, raw, "no POS")); continue
    pos = norm_pos(m.group(1))
    head = raw[: m.start()].strip()
    head = re.sub(r"\s+[12]\b", "", head)           # homograph index: 'bear 2' -> 'bear'
    head = re.sub(r"([a-z])[12](?=\(|$)", r"\1", head)  # 'will1' -> 'will'

    forms, note = [], []
    # parenthetical groups
    for grp in re.findall(r"\(([^)]*)\)", head):
        g = grp.strip()
        if g.startswith("Am "):
            forms += [x.strip() for x in g[3:].split("/")]; note.append("US:" + g[3:].strip())
        elif g.startswith("pl "):
            for x in re.split(r"[,/]", g[3:]): forms.append(x.strip())
            note.append("pl:" + g[3:].strip())
        elif g in ("s", "an"):
            pass  # handled below
        elif g == "Am":
            note.append("US")
        else:
            for x in re.split(r"[,/]|或", g):
                x = x.strip()
                if x: forms.append(x)
            note.append("forms:" + g)
    base_head = re.sub(r"\s*\([^)]*\)", lambda mm: "(s)" if mm.group(0).strip() == "(s)" else
                       ("(an)" if mm.group(0).strip() == "(an)" else ""), head).strip()

    # optional letters: afterward(s), a(an), Olympic(s)
    heads = []
    if "(s)" in base_head:
        b = base_head.replace("(s)", ""); heads = [b]; forms.append(b + "s")
    elif "(an)" in base_head:
        heads = ["a"]; forms.append("an")
    else:
        heads = [base_head]

    # '=' equivalents: ad=advertisement, can't=cannot
    expanded = []
    for h in heads:
        for piece in re.split(r";", h):
            piece = piece.strip()
            if not piece: continue
            if "=" in piece:
                left, right = [x.strip() for x in piece.split("=", 1)]
                expanded.append(left); forms += [x.strip() for x in right.split("/")]; note.append("=" + right)
            else:
                expanded.append(piece)
    # '/' alternatives: businessman/woman, a.m./am,A.M./AM
    final_heads = []
    for h in expanded:
        if re.fullmatch(r"\w+man/woman", h):
            stem = h[: -len("man/woman")]
            final_heads += [stem + "man", stem + "woman"]
        elif h == "schoolboy/girl":
            final_heads += ["schoolboy", "schoolgirl"]
        elif h == "madam/madame":
            final_heads += ["madam"]; forms.append("madame")
        elif h.startswith(("a.m.", "p.m.")):
            final_heads.append(h.split("/")[0]); forms += re.split(r"[/,]", h)[1:]
        else:
            final_heads.append(h)

    for i, h in enumerate(final_heads):
        h = h.strip()
        if not h: continue
        fs = [expand_ed(h, f) for f in forms if f and f != h]
        if re.fullmatch(r"\w+(man|woman)", h) and len(final_heads) == 2:
            stem = h[: -5] if h.endswith("woman") else h[: -3]
            fs = [stem + ("women" if h.endswith("woman") else "men")]
        key = h if (h.isupper() and len(h) > 1) else h.lower()
        e = entries.setdefault(key, {"headword": h, "pos": [], "forms": [], "notes": [],
                                     "page": page, "raw": []})
        for p in pos:
            if p not in e["pos"]: e["pos"].append(p)
        for f in fs:
            if f not in e["forms"]: e["forms"].append(f)
        e["notes"] += [x for x in note if x not in e["notes"]]
        e["raw"].append(raw)
        if len(e["raw"]) > 1: e["homograph"] = True

heads_lower = {e["headword"].lower() for e in entries.values()}
for e in entries.values():
    e["amb"] = [f for f in e["forms"] if f.lower() in heads_lower and f.lower() != e["headword"].lower()]
    e["forms"] = [f for f in e["forms"] if f not in e["amb"]]

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["id", "headword", "pos", "forms", "forms_also_headword", "homograph", "notes", "pdf_page", "raw"])
    for i, e in enumerate(entries.values(), 1):
        w.writerow([i, e["headword"], ";".join(e["pos"]), ";".join(e["forms"]), ";".join(e["amb"]),
                    int(e.get("homograph", False)), " | ".join(e["notes"]), e["page"],
                    " || ".join(e["raw"])])
with open(ISSUES, "w", newline="", encoding="utf-8") as f:
    csv.writer(f, delimiter="\t").writerows(issues)
print(f"entries: {len(entries)}  raw lines merged: {len(merged)}  issues: {len(issues)}")
