"""Step 2b: split each paper's raw text into English content lines tagged by section,
and collect the answer key.

Usage: python scripts/02b_segment_papers.py data/interim/raw_text data/interim/segments

For every paper writes:
  <paper>.lines.tsv  : section, kind, qnum, text      (English content only)
  <paper>.answers.tsv: qnum, answer                   (letters or words)

section ∈ listening | single_choice | cloze | reading | seven | grammar | correction | writing
kind    ∈ passage | question | option | transcript
Explanation blocks (【解答】【点评】【答案】【解析】【详解】【参考范文】... ) are dropped from
content, but scanned for answers.
"""
import os, re, sys, glob
from collections import OrderedDict

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

CJK = re.compile(r"[一-鿿]")
GLOSS = re.compile(r"\s?[(（][^()（）]*[一-鿿][^()（）]*[)）]")  # community(社区) -> community

EXPLAIN_START = re.compile(r"^\s*【(考点|分析|解答|点评|答案|解析|详解|点睛|导语|参考答案|参考范文|"
                           r"高分句型[^】]*|亮点说明|易错提醒|备考提示|高考试题库备考提示|\d+题详解)】"
                           r"|^\s*(参考答案|答案与解析|参考范文|范文|应用文例文|读后续写例文|One possible version|Possible version)", re.I)
EXPLAIN_WORDS = re.compile(r"考查|故选|句意|可知|根据上文|根据下文|根据文章|根据第|推断|题意|答案为|故答案|解析|详解|本题")
TRANSCRIPT_START = re.compile(r"【原文】|\[原文\]|听力原文|听力材料|录音原文")
SECTION_RULES = [  # order matters: first match wins
    ("listening",     re.compile(r"听下面|听力")),
    ("seven",         re.compile(r"从短文后的选项中选出|七选五|短文后有两项为多余")),
    ("grammar",       re.compile(r"在空白处填入|语法填空")),
    ("correction",    re.compile(r"短文改错|修改你同桌|交换修改作文")),
    ("single_choice", re.compile(r"单项填空|单选填空|语法和词汇知识")),
    ("cloze",         re.compile(r"完形填空|从短文后各题所给的|选出可以填入空白处的最佳选项")),
    ("reading",       re.compile(r"阅读理解|阅读下列短文|从每题所给的.*选出最佳选项")),
    ("writing",       re.compile(r"书面表达|写作|应用文|读后续写|续写|假定你是|假设你是")),
]
HEADER = re.compile(r"^\s*(第[一二三四五六七]部分|第[一二三四]节|阅读下|听下面|根据短文|假定|假设|"
                    r"阅读下面|写作|书面表达|短文改错|(听力|阅读|语言运用|英语知识运用|阅读理解)\s*[（(])")
PART_DEFAULT = {"听力": "listening", "阅读理解": "reading", "阅读": "reading",
                "语言运用": "cloze", "写作": "writing"}
PART = re.compile(r"(第[一二三四五六七]部分\s*)?(听力|阅读理解|阅读|语言运用|英语知识运用|写作)\s*[（(]")
OPTION_LINE = re.compile(r"^\s*(\d{1,2}\s*[.．、]?\s*)?[A-G]\s*[.．、]\s*\S")
QUESTION_LINE = re.compile(r"^\s*(\d{1,2})\s*[.．、]\s*(?![A-G]\s*[.．])\S")

ANS_CONT = re.compile(r"^\s*(\d{1,2}\s*(?:[.．、]\s*|\s+)[A-Za-z][A-Za-z'’ \-/#|]{0,25}?\s*){1,6}$")
ANS_CONT_ITEM = re.compile(r"(?<!\d)(\d{1,2})\s*(?:[.．、]\s*|\s+)([A-Za-z][A-Za-z'’/#| \-]*?)(?=\s+\d{1,2}\b|\s*$)")
ANS_RANGE = re.compile(r"(\d{1,2})\s*[-–~～—]\s*(\d{1,2})\s*[:：]?\s*([A-G]{2,})")
ANS_SINGLE = re.compile(r"(?<!\d)(\d{1,2})\s*[.．、]?\s*([A-G])(?![A-Za-z.．])")
ANS_WORD = re.compile(r"(?<!\d)(\d{1,2})\s*[.．、]\s*([A-Za-z][A-Za-z'’/#| \-]*?)(?=\s*(?:[\u4e00-\u9fff【(（，,；;。]|\d{1,2}\s*[.．、]|$))")


def cjk_heavy(line):
    c = len(CJK.findall(line)); a = len(re.findall(r"[A-Za-z]", line))
    return c > 0 and c / (c + a) > 0.3


def classify_section(line, current):
    for name, rx in SECTION_RULES:
        if rx.search(line):
            return name
    return current


def harvest_answers(line, answers, sec):
    """Pull answer letters/words out of an explanation or answer-key line."""
    for a, b, letters in ANS_RANGE.findall(line):
        a, b = int(a), int(b)
        if b - a + 1 == len(letters):
            for i, ch in enumerate(letters):
                answers.setdefault((sec, a + i), ch)
    for n, ch in ANS_SINGLE.findall(line):
        answers.setdefault((sec, int(n)), ch)
    for n, w in ANS_WORD.findall(line):
        n = int(n); w = w.strip()
        if (sec, n) in answers or not w or re.fullmatch(r"[A-G]", w):
            continue
        answers.setdefault((sec, n), w)


def process(paper, text):
    lines_out, answers = [], OrderedDict()
    section, mode = "listening", "content"     # papers open with listening
    kind_override = None
    pending_instr = False
    part = ""
    qnum = ""
    for raw in text.splitlines():
        line = re.sub(r"^\s*\[(答案|解析|分析|详解|点睛|导语|\d+题详解)\]", r"【\1】", raw.strip())
        if not line:
            continue
        if TRANSCRIPT_START.search(line):
            section, mode, kind_override = "listening", "content", "transcript"
            rest = TRANSCRIPT_START.split(line)[-1].strip()
            if rest and not CJK.search(rest):
                lines_out.append((section, "transcript", "", rest.replace("\t", "    ")))
            continue
        if EXPLAIN_START.search(line):
            mode = "explain"
            harvest_answers(line, answers, section)
            continue
        if HEADER.search(line) and CJK.search(line):
            pm = PART.search(line)
            if pm: part = pm.group(2)
            specific = classify_section(line, None)
            if part in ("语言运用", "英语知识运用") and specific == "reading":
                specific = "cloze"
            if specific is None and pm:
                specific = PART_DEFAULT.get(part)
            section = specific or section
            pending_instr = specific is None or bool(pm)          # generic header: let the instruction decide
            if kind_override == "transcript" and section != "listening" and specific:
                kind_override = None
            mode = "content"
            continue
        if pending_instr and cjk_heavy(line) and mode == "content":
            section = classify_section(line, section)
            if part in ("语言运用", "英语知识运用") and section == "reading":
                section = "cloze"
            pending_instr = False
            if kind_override == "transcript" and section != "listening":
                kind_override = None
            continue
        if re.fullmatch(r"[A-E]", line) or re.fullmatch(r"Passage [A-E]", line):
            mode = "content"; continue                 # passage label resets explanation mode
        if mode == "explain" and ANS_CONT.match(line):
            harvest_answers(line, answers, section)      # multi-line answer key: '58. or  59. recognized'
            for n, w in ANS_CONT_ITEM.findall(line):     # tolerate '61 the' (missing dot)
                if not re.fullmatch(r"[A-G]", w.strip()):
                    answers.setdefault((section, int(n)), w.strip())
            continue
        if mode == "explain":
            harvest_answers(line, answers, section)
            # an English question line ends an explanation block (ks5u style: 21.… 【答案】… 22.…)
            if QUESTION_LINE.match(line) and not CJK.search(line) and section != "writing":
                mode = "content"
            else:
                continue
        # ---- content line ----
        line = GLOSS.sub("", line)
        if EXPLAIN_WORDS.search(line):
            harvest_answers(line, answers, section)   # explanation quoting English: '46．B 考查…根据"…"可知'
            continue
        if cjk_heavy(line):
            harvest_answers(line, answers, section)   # unmarked explanation lines: '46．B 考查…'
            continue                      # instructions, Chinese prompts
        line = re.sub(r"[\u4e00-\u9fff]+", " ", line)   # stray CJK (OCR noise, unbracketed glosses)
        line = re.sub(r"_{3,}", " ____ ", line.replace("\t", "    ")).strip()
        if not re.search(r"[A-Za-z]{2,}", line):
            continue
        if kind_override == "transcript":
            kind = "transcript"
        elif OPTION_LINE.match(line):
            kind = "option"
        elif QUESTION_LINE.match(line):
            kind = "question"
        else:
            kind = "passage"
        m = re.match(r"^\s*(\d{1,2})\s*[.．、]?", line)
        qnum = m.group(1) if m and kind in ("question", "option") else ""
        lines_out.append((section, kind, qnum, line))
    return lines_out, answers


papers = sorted(glob.glob(os.path.join(src, "*.txt")))
merged = {}
for p in papers:
    name = os.path.basename(p)[:-4]
    pid = "_".join(name.split("_")[:2])            # 2026_XG1_试题 + 2026_XG1_答案听力 -> 2026_XG1
    merged.setdefault(pid, []).append(open(p, encoding="utf-8").read())

for pid, texts in merged.items():
    if len(texts) > 1:   # 2026: 试题 first, then 答案听力 (answers + 范文 + 听力原文)
        texts = sorted(texts, key=lambda t: ("参考答案" in t[:200]))
    lines_out, answers = process(pid, "\n".join(texts))
    with open(os.path.join(out, pid + ".lines.tsv"), "w", encoding="utf-8") as f:
        f.write("section\tkind\tqnum\ttext\n")
        for row in lines_out:
            f.write("\t".join(row) + "\n")
    with open(os.path.join(out, pid + ".answers.tsv"), "w", encoding="utf-8") as f:
        f.write("section\tqnum\tanswer\n")
        for (sec, n) in sorted(answers, key=lambda k: (k[1], k[0])):
            f.write(f"{sec}\t{n}\t{answers[(sec, n)]}\n")
    from collections import Counter
    c = Counter((s, k) for s, k, _, _ in lines_out)
    print(pid, dict(sorted(c.items())), "answers:", len(answers))
