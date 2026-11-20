"""Step 2c: restore cloze (完形填空) and grammar-fill (语法填空) passages with the answer key.

Usage: python scripts/02c_fill_blanks.py data/interim/segments data/interim/corpus

Writes data/interim/corpus/<paper>.tsv with columns: section, kind, text
  - cloze/grammar passages are rejoined into one 'passage_filled' row per section
  - cloze option lines are kept as kind=option (counting rules decide later)
and prints a fill report (blanks expected vs filled).
"""
import csv, glob, os, re, sys
from collections import defaultdict

seg, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
OPT = re.compile(r"([A-D])\s*[.．、]\s*(.*?)(?=\s+[A-D]\s*[.．、]|\s*$)")
report = []


def load(pid):
    lines = list(csv.DictReader(open(os.path.join(seg, pid + ".lines.tsv"), encoding="utf-8"), delimiter="\t"))
    ans = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(seg, pid + ".answers.tsv"), encoding="utf-8"), delimiter="\t"):
        ans[int(r["qnum"])][r["section"]] = r["answer"].strip()
    return lines, ans


def pick(ans, n, sec, letter):
    d = ans.get(n, {})
    cand = [d[sec]] if sec in d else list(d.values())
    for v in cand:
        if letter and re.fullmatch(r"[A-D]", v): return v
        if not letter and not re.fullmatch(r"[A-G]", v): return v
    return None


def blank_patterns(n):
    # prefer underscored blanks (____41____, __41__, 41____), then bracketed (41) / （41）, then bare ' 41 '
    return [re.compile(rf"_+\s*(?<!\d){n}(?!\d)\s*_*|_*\s*(?<!\d){n}(?!\d)\s*_+"),
            re.compile(rf"[(（]\s*{n}\s*[)）]"),
            re.compile(rf"(?<![\d.,:$£])\b{n}\b(?![\d.,:%]\d)")]


HINT = re.compile(r"\s*[(（]\s*[A-Za-z][A-Za-z\s]*[)）]")


def fill_text(text, nums, getter, strip_hint=False):
    """Fill blanks in question order; each blank is searched only after the previous one."""
    filled, missing, pos = 0, [], 0
    for n in nums:
        a = getter(n)
        if a is None: missing.append(n); continue
        m = None
        for pat in blank_patterns(n):
            m = pat.search(text, pos)
            if m: break
        if not m: missing.append(n); continue
        end = m.end()
        if strip_hint:                       # grammar: '61 (arrive)' -> 'arrived'
            h = HINT.match(text, end)
            if h: end = h.end()
        text = text[: m.start()] + f" {a} " + text[end:]
        pos = m.start() + len(a) + 2
        filled += 1
    return re.sub(r"\s{2,}", " ", text).strip(), filled, missing


for p in sorted(glob.glob(os.path.join(seg, "*.lines.tsv"))):
    pid = os.path.basename(p).split(".")[0]
    lines, ans = load(pid)
    rows = []
    by_sec = defaultdict(list)
    for r in lines: by_sec[r["section"]].append(r)

    # ---- cloze ----
    cl = by_sec.get("cloze", [])
    passage = " ".join(r["text"] for r in cl if r["kind"] == "passage")
    options, cur = defaultdict(dict), None
    for r in cl:
        if r["kind"] in ("option", "question"):
            if r["qnum"]: cur = int(r["qnum"])
            if cur is not None:
                for letter, txt in OPT.findall(re.sub(rf"^\s*{cur}\s*[.．、]?", "", r["text"])):
                    options[cur].setdefault(letter, txt.strip())
    nums = sorted(options)
    def cloze_get(n):
        letter = pick(ans, n, "cloze", True)
        return options[n].get(letter) if letter else None
    if passage:
        filled_text, k, miss = fill_text(passage, nums, cloze_get)
        report.append((pid, "cloze", len(nums), k, miss))
        rows.append(("cloze", "passage_filled", filled_text))
        rows += [("cloze", "option", r["text"]) for r in cl if r["kind"] in ("option", "question")]

    # ---- grammar ----
    gr = by_sec.get("grammar", [])
    gpass = " ".join(r["text"] for r in gr)
    if gpass:
        cand = sorted({int(m) for m in re.findall(r"(?<![\d.])(\d{2})(?![\d.])", gpass)
                       if 1 <= int(m) <= 80 and pick(ans, int(m), "grammar", False)})
        runs, run = [], []
        for n in cand:                      # keep the longest consecutive run (the 10 blanks)
            if run and n != run[-1] + 1: runs.append(run); run = []
            run.append(n)
        if run: runs.append(run)
        gnums = max(runs, key=len) if runs else []
        expected = sorted({int(m) for m in re.findall(r"_+\s*(\d{1,2})\s*_+|(?<!\d)(\d{2})\s*[(（]", gpass) for m in m if m})
        def gram_get(n):
            a = pick(ans, n, "grammar", False)
            return re.split(r"/|##|\|", a)[0].strip() if a else None
        filled_text, k, miss = fill_text(gpass, gnums or expected, gram_get, strip_hint=True)
        report.append((pid, "grammar", len(set(gnums) | set(expected)), k, miss))
        rows.append(("grammar", "passage_filled", filled_text))

    # ---- everything else unchanged ----
    for r in lines:
        if r["section"] not in ("cloze", "grammar"):
            rows.append((r["section"], r["kind"], r["text"]))
    with open(os.path.join(out, pid + ".tsv"), "w", encoding="utf-8") as f:
        f.write("section\tkind\ttext\n")
        for row in rows: f.write("\t".join(x.replace("\t", " ") for x in row) + "\n")

print("paper\tsection\tblanks\tfilled\tmissing")
for pid, sec, n, k, miss in report:
    print(f"{pid}\t{sec}\t{n}\t{k}\t{','.join(map(str, miss))}")
