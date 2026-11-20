"""Step 2a: convert exam papers (.doc / .docx / .pdf) to UTF-8 plain text.

Usage: python scripts/02a_convert_papers.py <试卷 folder> data/interim/raw_text

- .doc  -> .docx via LibreOffice (soffice) if available, else macOS `textutil`
- .docx -> text, walking the body in document order so that tables
           (options are often laid out in tables) are kept in place
- .pdf  -> text via pdfplumber
Only files named like 2008_DG1_解析卷.doc are processed (see papers.csv).
"""
import os, re, shutil, subprocess, sys, tempfile
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
NAME = re.compile(r"^(\d{4})_([A-Z0-9]+)_(.+)\.(doc|docx|pdf)$")


def docx_text(path):
    d = docx.Document(path)
    lines = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append(Paragraph(child, d).text)
        elif tag == "tbl":
            for row in Table(child, d).rows:
                cells, seen = [], set()
                for c in row.cells:            # merged cells repeat; keep each once
                    if id(c._tc) in seen: continue
                    seen.add(id(c._tc)); cells.append(c.text.strip())
                lines.append("    ".join(x for x in cells if x))
    return "\n".join(lines)


def doc_to_docx(path, tmp):
    if shutil.which("soffice"):
        subprocess.run(["soffice", "--headless", "--convert-to", "docx", "--outdir", tmp, path],
                       check=True, capture_output=True)
    elif shutil.which("textutil"):
        subprocess.run(["textutil", "-convert", "docx", "-output",
                        os.path.join(tmp, os.path.basename(path)[:-4] + ".docx"), path], check=True)
    else:
        sys.exit("need LibreOffice (soffice) or macOS textutil to read .doc files")
    return os.path.join(tmp, os.path.basename(path)[:-4] + ".docx")


def pdf_text(path):
    # poppler's pdftotext keeps inter-word spaces better than pdfplumber on these files
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, check=True).stdout
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


with tempfile.TemporaryDirectory() as tmp:
    for fn in sorted(os.listdir(src)):
        m = NAME.match(fn)
        if not m: continue
        path = os.path.join(src, fn)
        ext = m.group(4)
        if ext == "doc":
            text = docx_text(doc_to_docx(path, tmp))
        elif ext == "docx":
            text = docx_text(path)
        else:
            text = pdf_text(path)
            # pdftotext puts blank numbers on their own line: 'The\n41\nthat' -> 'The 41 that'
            text = re.sub(r"(?m)^(\d{1,2}\.)\s*\n(?=[A-Za-z])", r"\1 ", text)   # '62.\nDrawn'
            text = re.sub(r"\n\s*(\d{1,2})\s*\n(?=[a-z,.;:!?’'\"]|\S)", r" \1 ", text)
        text = text.replace("　", " ").replace("\xa0", " ")
        dst = os.path.join(out, fn.rsplit(".", 1)[0] + ".txt")
        open(dst, "w", encoding="utf-8").write(text)
        print(f"{fn:28s} -> {len(text):7d} chars")
