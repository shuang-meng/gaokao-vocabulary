"""Step 1 (alternative list): parse 附录2 词汇表 of 《普通高中英语课程标准（2017年版2025年修订）》.

Usage:
  python scripts/01d_parse_curriculum_vocab.py <课标.pdf> data/processed/vocab_kb2025.csv data/processed/vocab_kb2025_countries.csv

The list has no POS and no Chinese. Level is marked by stars:
  no star = 义务教育 (1600 words) · * = 必修 (500) · ** = 选择性必修 (1000)   → 3100 words in total
Entry patterns handled:
  analyse (analyze)**     variant spelling -> forms
  ad (=advertisement)     full form -> forms
  according (to)          optional particle -> also matches the phrase 'according to'
  actor/actress, a/an     slash -> separate headwords sharing one `group`
Output columns match vocab_3500.csv so later steps can switch lists:
  id, headword, pos (empty), forms, forms_also_headword, level, group, pdf_page, raw
"""
import csv, re, sys
import pdfplumber

pdf_path, out_path, out_countries = sys.argv[1:4]
LEVEL = {0: "义务教育", 1: "必修", 2: "选择性必修"}
PARTICLES = {"to", "of", "for", "with", "on", "at", "about", "from", "in"}

raw_entries = []          # (page, text)
seen_I_heading = False
country_lines = []
with pdfplumber.open(pdf_path) as pdf:
    start = end = None
    for i, p in enumerate(pdf.pages):
        t = p.extract_text() or ""
        if start is None and "附录2" in t.replace(" ", "")[:80] and "词汇表" in t[:80]:
            start = i
        if start is not None and i > start and "部分国家名称" in t[:40]:
            end = i; break
    for i in range(start, end):
        p = pdf.pages[i]
        words = p.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
        # column boundary per page (odd/even pages are offset): start x of the right column
        xs = sorted(round(w["x0"]) for w in words if re.search(r"[a-z]", w["text"]))
        left = xs[0] if xs else 0
        right_starts = [x for x in xs if x > left + 120]
        split = (min(right_starts) - 15) if right_starts else p.width / 2
        cols = {0: {}, 1: {}}
        for w in words:
            col = 0 if w["x0"] < split else 1
            cols[col].setdefault(round(w["top"] / 3), []).append(w)
        for col in (0, 1):
            for key in sorted(cols[col]):
                text = " ".join(w["text"] for w in sorted(cols[col][key], key=lambda w: w["x0"])).strip()
                if text == "I" and seen_I_heading:
                    raw_entries.append((i + 1, "I")); continue      # pronoun I right after heading I
                if text == "I":
                    seen_I_heading = True
                if not text or re.search(r"[\u4e00-\u9fff│]", text) or re.fullmatch(r"[A-Z]|\d+", text):
                    continue
                if i == start and not re.search(r"[A-Za-z]", text):
                    continue
                raw_entries.append((i + 1, text))
    for i in range(end, len(pdf.pages)):
        t = pdf.pages[i].extract_text() or ""
        if "部分国家名称" not in t[:40] and "续表" not in t[:20]:
            break
        country_lines += t.splitlines()

# drop the 说明 block on the first page (lines before the first 'A' entries)
first = next(k for k, (_, t) in enumerate(raw_entries) if re.match(r"^a\.m\.|^a/an", t))
raw_entries = raw_entries[first - 0:] if first < 3 else raw_entries[first:]

# entries wrapped over two lines: the continuation ('Era)**') lands at the next row of the
# right column ('Era)** belt'). Join it back and keep the right-column word as its own entry.
fixed, carry = [], {}
for k, (page, t) in enumerate(raw_entries):
    if t.count("(") > t.count(")"):
        carry[page] = len(fixed)
    m = re.match(r"^([^(]*\)\**)\s*(\S*)$", t)
    if m and page in carry:
        j = carry.pop(page)
        fixed[j] = (page, fixed[j][1] + " " + m.group(1))
        if m.group(2): fixed.append((page, m.group(2)))
        continue
    fixed.append((page, t))
raw_entries = fixed

rows, gid = [], 0
for page, raw in raw_entries:
    t = raw.replace("’", "'").strip()
    stars = len(re.search(r"\**$", t).group(0)); t = t.rstrip("*").strip()
    gid += 1
    forms, phrase = [], None
    for g in re.findall(r"\(([^)]*)\)", t):
        g = g.strip()
        if g.startswith("="):
            forms += [x.strip() for x in g[1:].split("/") if x.strip()]
        elif g.lower() in PARTICLES:
            phrase = g.lower()
        else:
            forms += [x.strip() for x in re.split(r"[,/]", g) if x.strip()]
    head = re.sub(r"\s*\([^)]*\)", "", t).strip()
    heads = [h.strip() for h in head.split("/")] if "/" in head and not head.endswith(".") else [head]
    for h in heads:
        fs = list(forms)
        if phrase: fs.append(f"{h} {phrase}")
        rows.append({"headword": h, "forms": fs, "level": LEVEL[stars], "group": gid, "page": page, "raw": raw})

# merge duplicates, mark forms that are themselves headwords
by, order = {}, []
for r in rows:
    k = r["headword"]          # case-sensitive: China / china (porcelain), Miss / miss are different words
    if k in by:
        by[k]["forms"] += [f for f in r["forms"] if f not in by[k]["forms"]]; by[k]["raw"] += " || " + r["raw"]
    else:
        by[k] = r; order.append(k)
heads_lower = {k.lower() for k in by}
with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["id", "headword", "pos", "forms", "forms_also_headword", "level", "group", "pdf_page", "raw"])
    for i, k in enumerate(order, 1):
        r = by[k]
        amb = [x for x in r["forms"] if x.lower() in heads_lower]
        fs = [x for x in r["forms"] if x not in amb]
        w.writerow([i, r["headword"], "", ";".join(fs), ";".join(amb), r["level"], r["group"], r["page"], r["raw"]])

# countries: country / person / adjective (rows that wrap across lines are fixed by hand below)
crow = []
for line in country_lines:
    m = re.match(r"^([一-鿿]+)\s+(.+)$", line.strip())
    if not m: continue
    parts = m.group(2).split()
    if len(parts) == 3 and "COUNTRY" not in parts:
        crow.append(parts)            # wrapped / multiword rows are listed in MANUAL
MANUAL = [["Democratic People's Republic of Korea", "Korean", "Korean"],
          ["France", "Frenchman/Frenchwoman", "French"],
          ["Republic of Korea", "Korean", "Korean"],
          ["the United Kingdom", "Briton", "British"], ["UK", "Briton", "British"],
          ["the United States of America", "American", "American"], ["USA", "American", "American"],
          ["New Zealand", "New Zealander", "New Zealand"], ["Saudi Arabia", "Saudi Arabian", "Saudi Arabian"],
          ["South Africa", "South African", "South African"]]
with open(out_countries, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["country", "person", "adjective"])
    for r in crow + MANUAL:
        w.writerow(r)

from collections import Counter
print(f"raw entries {len(raw_entries)}  headwords {len(order)}  levels {Counter(by[k]['level'] for k in order)}")
print(f"country rows {len(crow) + len(MANUAL)}")
