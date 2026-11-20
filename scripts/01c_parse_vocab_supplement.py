"""Step 1c: parse the supplementary tables after 附录5 main list
(数词 / 月份 / 星期 / 主要国家名称及相关信息) into data/processed/vocab_supplement.csv.

These words are part of the syllabus but are not headwords in the main A-Z list.
"""
import csv, re, subprocess, sys

pdf, out = sys.argv[1], sys.argv[2]
text = subprocess.run(["pdftotext", "-layout", "-f", "67", "-l", "71", pdf, "-"],
                      capture_output=True, text=True, check=True).stdout
text = text[text.index("数词"):]

rows, seen = [], set()
def add(word, cat, extra=""):
    w = word.strip()
    if w and (w.lower(), cat) not in seen:
        seen.add((w.lower(), cat)); rows.append([w, cat, extra])

sec_num = text[: text.index("月份")]
sec_month = text[text.index("月份"): text.index("星期")]
sec_week = text[text.index("星期"): text.index("主要国家名称")]
sec_country = text[text.index("主要国家名称"):]

# numerals: words only (skip 1st/2nd and digits); multiword kept whole, tokens added too
for line in sec_num.splitlines():
    for chunk in re.split(r"\s{2,}", line.strip()):
        chunk = re.sub(r"\(and\)", " and ", chunk).strip()
        if not chunk or re.search(r"\d", chunk) or re.search(r"[一-鿿]", chunk):
            continue
        for tok in re.findall(r"[a-z]+(?:-[a-z]+)?", chunk.lower()):
            if tok != "and":
                for part in tok.split("-"):
                    add(part, "numeral")

for sec, cat in ((sec_month, "month"), (sec_week, "weekday")):
    for m in re.finditer(r"\b([A-Z][a-z]+day|January|February|March|April|May|June|July|"
                         r"August|September|October|November|December)\s*\(([^)]+)\)", sec):
        add(m.group(1), cat, "abbr:" + m.group(2))

for line in sec_country.splitlines():
    parts = [p for p in re.split(r"\s{2,}", line.strip()) if p]
    if len(parts) >= 4 and re.search(r"[一-鿿]", parts[0]):
        country, person, adj = parts[1], parts[2], parts[3]
        add(country, "country", f"person:{person};adj:{adj}")
        for w in {person, adj} - {country}:
            add(w, "nationality")

# two rows wrap across lines in the PDF (英国 / 荷兰); add them explicitly
for c in ("Britain", "U.K.", "United Kingdom"):
    add(c, "country", "person:British;adj:British")
for c in ("Holland", "Netherlands"):
    add(c, "country", "person:Dutch;adj:Dutch")
add("British", "nationality"); add("Dutch", "nationality")

with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["word", "category", "extra"]); w.writerows(rows)
from collections import Counter
print(len(rows), Counter(r[1] for r in rows))
