"""Step 1a: extract raw entry lines from 附录5 词汇表 of the 考试大纲 PDF.
Two-column layout: split words by x position, read left column then right column per page.
Output: data/interim/vocab_lines.tsv  (page, col, line_no, text)
"""
import sys, csv, pdfplumber
from collections import defaultdict

pdf_path, out_path = sys.argv[1], sys.argv[2]
rows = []
with pdfplumber.open(pdf_path) as pdf:
    start = end = None
    for i, p in enumerate(pdf.pages):
        t = p.extract_text() or ""
        if start is None and "附录 5" in t and "词汇表" in t: start = i
        if start is not None and "数词" in t: end = i; break
    for i in range(start, end + 1):
        p = pdf.pages[i]
        words = p.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
        mid = p.width / 2
        cols = defaultdict(lambda: defaultdict(list))
        for w in words:
            col = 0 if w["x0"] < mid - 5 else 1
            cols[col][round(w["top"] / 3)].append(w)
        for col in (0, 1):
            for n, key in enumerate(sorted(cols[col])):
                ws = sorted(cols[col][key], key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in ws).strip()
                if text: rows.append((i + 1, col, n, text))
with open(out_path, "w", newline="", encoding="utf-8") as f:
    csv.writer(f, delimiter="\t").writerows(rows)
print(f"pages {start+1}-{end+1}, lines {len(rows)}")
