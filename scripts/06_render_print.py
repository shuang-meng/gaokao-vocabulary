"""Step 6: render the printable word book (A4, 6–8 entries per page) as HTML and PDF.

Usage:
  python scripts/06_render_print.py data/processed/entries_with_defs.csv data/processed/token_totals.json \
      output/gaokao_vocab --chapters 1            # only chapter 1 (sample)
  python scripts/06_render_print.py ... output/gaokao_vocab                  # whole book

Order: years appeared -> total count (the `rank` column). Chapters are frequency bands.
PDF: WeasyPrint (pip install weasyprint). Without it, open the HTML in Chrome and print to PDF.
"""
import argparse, csv, html, json, re

ap = argparse.ArgumentParser()
ap.add_argument("entries"); ap.add_argument("totals"); ap.add_argument("out")
ap.add_argument("--chapters", default="", help="comma list of chapter numbers to render, e.g. 1 or 1,2")
ap.add_argument("--senses", default="", help="data/processed/senses.csv (hand-written senses; replaces gloss and examples)")
ap.add_argument("--max-senses", type=int, default=5)
ap.add_argument("--metrics", default="", help="data/processed/word_sense_metrics.csv (step 8c)")
ap.add_argument("--phrases", default="", help="data/processed/phrase_entries.csv (step 8c)")
ap.add_argument("--phrase-glosses", default="data/manual/phrase_glosses.csv")
ap.add_argument("--max-phrases", type=int, default=4)
ap.add_argument("--tested", default="", help="data/processed/tested_words.csv (step 9a): mark cloze / grammar answers")
ap.add_argument("--rare-senses", default="", help="data/processed/rare_senses.csv (step 9c): mark 熟词生义, add an appendix")
ap.add_argument("--coverage", default="", help="data/processed/sense_coverage.csv (step 9b): sense coverage table on the cover")
a = ap.parse_args()

CHAPTERS = [(1, 200, "核心词"), (201, 500, "高频词"), (501, 1000, "中频词"),
            (1001, 1600, "常考词"), (1601, 9999, "偶考词"), (None, None, "真题未出现的课标词")]
LEVEL_TAG = {"义务教育": ("义务", "lv0"), "必修": ("必修", "lv1"), "选择性必修": ("选必", "lv2"), "": ("附表", "lv0")}
POS_CN = {"n.": "名", "v.": "动", "adj.": "形", "adv.": "副"}

rows = list(csv.DictReader(open(a.entries, encoding="utf-8-sig")))
rows.sort(key=lambda r: int(r["rank"]))
tot = json.load(open(a.totals))
import os
hits = {r["headword"]: int(r["coverage_hits"]) for r in csv.DictReader(
    open(os.path.join(os.path.dirname(a.totals), "word_freq.csv"), encoding="utf-8-sig"))}  # non-name tokens
seen = [r for r in rows if int(r["total_count"]) > 0]
unseen = [r for r in rows if int(r["total_count"]) == 0]
esc = html.escape
SENSES = {}
if a.senses and os.path.exists(a.senses):
    for s in csv.DictReader(open(a.senses, encoding="utf-8-sig")):
        SENSES.setdefault(s["headword"], []).append(s)
TESTED = {r["headword"]: r for r in csv.DictReader(open(a.tested, encoding="utf-8-sig"))} if a.tested else {}
RARE = list(csv.DictReader(open(a.rare_senses, encoding="utf-8-sig"))) if a.rare_senses else []
RARE_KEYS = {(r["headword"], r["sense"]) for r in RARE}
COVER = list(csv.DictReader(open(a.coverage, encoding="utf-8-sig"))) if a.coverage else []
METRICS = {r["word"]: r for r in csv.DictReader(open(a.metrics, encoding="utf-8-sig"))} if a.metrics else {}
PHRASES = {}
if a.phrases:
    gl = {r["phrase"]: r["zh"] for r in csv.DictReader(open(a.phrase_glosses, encoding="utf-8-sig"))} \
        if os.path.exists(a.phrase_glosses) else {}
    for p in csv.DictReader(open(a.phrases, encoding="utf-8-sig")):
        if p["class"] in ("idiom", "functional") and int(p["count"]) >= 2 and p["phrase"] in gl:
            for h in p["head_words"].split():
                PHRASES.setdefault(h, []).append({**p, "zh": gl[p["phrase"]]})


FUNC_POS = ("art", "prep", "pron", "conj", "aux", "num", "int", "interj", "det")


def is_function_word(r):
    first = re.match(r"^\s*([a-z]+)\.", r["zh_gloss"].replace("\r", ""))
    return r.get("function_word") == "1" or bool(first and first.group(1) in FUNC_POS)


def short_gloss(r, max_pos=3, per_pos=3):
    """keep the parts of speech used in the exams, first 3 meanings each."""
    exam = [] if is_function_word(r) else [p.split(".")[0] for p in re.findall(r"(n\.|v\.|adj\.|adv\.)", r["exam_pos"])]
    lines = [l.replace("\r", "").strip() for l in r["zh_gloss"].split(" | ") if l.strip()]
    if any(re.match(r"^[a-z]+\.", l) for l in lines):
        lines = [l for l in lines if re.match(r"^[a-z]+\.", l)]     # drop un-tagged lines like '第一个字母 A'
    out = []
    for line in lines:
        m = re.match(r"^\s*([a-z]+)\.\s*(.*)$", line)
        if not m:
            out.append(line); continue
        p, rest = m.group(1), m.group(2)
        key = {"vt": "v", "vi": "v", "a": "adj", "ad": "adv"}.get(p, p)
        if exam and key not in exam and len(out) >= 1:
            continue
        means = [x.strip() for x in re.split(r"[,，;；]", rest) if x.strip()][:per_pos]
        out.append(f"<b>{esc(p)}.</b> {esc('，'.join(means))}")
        if len(out) >= max_pos: break
    return "　".join(out)


def forms_of(r):
    fs = {r["headword"].lower()}
    for part in r["inflections"].split("/"):
        if ":" in part: fs.add(part.split(":", 1)[1].lower())
    return fs


def highlight(sentence, r):
    text = esc(sentence)
    fs = sorted(forms_of(r), key=len, reverse=True)
    pat = r"\b(" + "|".join(re.escape(esc(f)) for f in fs) + r")\b"
    return re.sub(pat, r"<mark>\1</mark>", text, flags=re.I)


def example_html(ex, r):
    m = re.match(r"^(.*)（(\d{4}) (\w+) (.+)）$", ex)
    if not m: return f"<li>{highlight(ex, r)}</li>"
    s, y, line, sec = m.groups()
    return f'<li>{highlight(s, r)} <span class="src">{y}·{esc(sec)}</span></li>'


def senses_html(r, senses):
    out = []
    if senses and senses[0].get("counted") == "full":        # full counts: drop rare senses (keep at least one)
        senses = [s for i, s in enumerate(senses) if i == 0 or (int(s["count"]) >= 2 and float(s["share"]) >= 0.03)]
    for s in senses[:a.max_senses]:
        ex = ""
        if s["example"]:
            src = s["example_src"].split()
            src = f'{src[0]}·{src[-1]}' if src else ""
            ex = f'<div class="sx">{highlight(s["example"], r)} <span class="src">{esc(src)}</span></div>'
        pct = ""
        if s.get("counted") == "full" and len(senses) > 1:
            v = float(s["share"])
            pct = f'<span class="pct"><span class="bar" style="width:{max(1, round(14 * v))}mm"></span>{round(100 * v)}%</span>'
        if (r["headword"], s["sense"]) in RARE_KEYS:
            pct += '<span class="rare">生义</span>'
        out.append(f'<li><b>{esc(s["pos"])}</b> <span class="zh">{esc(s["zh"])}</span>{pct}'
                   f'<span class="sen">{esc(s["en"])}</span>{ex}</li>')
    return f'<ol class="senses">{"".join(out)}</ol>'


def phrases_html(w):
    ps = sorted(PHRASES.get(w, []), key=lambda p: (-int(p["years"]), -int(p["count"])))[:a.max_phrases]
    if not ps: return ""
    items = "；".join(f'<span class="ph">{esc(p["phrase"])}</span> {esc(p["zh"])}<sup>{p["count"]}</sup>' for p in ps)
    return f'<div class="col"><span class="lab phl">短语</span>{items}</div>'


def metrics_html(w):
    m = METRICS.get(w)
    if not m or int(m["occurrences"]) < 5: return ""
    bits = []
    if float(m["phrase_share"]) >= 0.1: bits.append(f'{round(100 * float(m["phrase_share"]))}% 在短语中')
    bits.append(f'分布在 {m["passages"]} 篇')
    ls = float(m["listening_share"])
    if ls >= 0.5: bits.append(f'<b>听力占 {round(100 * ls)}%</b>')
    if float(m["biggest_passage_share"]) >= 0.4:
        bits.append(f'<b>{round(100 * float(m["biggest_passage_share"]))}% 集中在同一篇</b>')
    return f'<div class="mt">{" · ".join(bits)}</div>'


def entry_html(r):
    lv, cls = LEVEL_TAG.get(r["level"], ("", "lv0"))
    stats = f'{r["years_count"]}/19 年 · {r["total_count"]} 次' if int(r["total_count"]) else "真题未出现"
    t = TESTED.get(r["headword"])
    if t and not is_function_word(r):
        k = [f'完形×{t["cloze_answer"]}' if int(t["cloze_answer"]) else '', f'语法×{t["grammar_answer"]}' if int(t["grammar_answer"]) else '']
        stats = f'<span class="tested">考点 {" ".join(x for x in k if x)}</span> ' + stats
    pos = "　".join(f"{POS_CN.get(p.split('.')[0] + '.', p)}{p.split('.')[1]}" if False else p
                   for p in r["exam_pos"].split(" / ") if p)
    func = is_function_word(r)
    senses = SENSES.get(r["headword"])
    en = r["en_definitions"].split(" | ")[0] if r["en_definitions"] and not func else ""
    if func: pos = ""
    exs = [r[k] for k in ("example_1", "example_2") if r[k]]
    dict_ex = "" if exs or not r["en_def_examples"] else r["en_def_examples"].split(" | ")[0]
    col = "；".join(re.sub(r" ×(\d+)", r"<sup>\1</sup>", esc(c)) for c in r["collocations"].split("; ")[:4] if c)
    extra = []
    if r["derived_words"]: extra.append("派生 " + esc(re.sub(r" ×\d+", "", r["derived_words"])))
    if r["word_roots"]: extra.append("词根 " + esc(r["word_roots"]))
    if r["inflections"] and any(k in r["inflections"] for k in ("p:", "d:")):
        irr = {p.split(":")[0]: p.split(":")[1] for p in r["inflections"].split("/") if ":" in p}
        if irr.get("p") and not irr["p"].endswith("ed"):
            extra.append(f'变形 {esc(irr.get("p", ""))} / {esc(irr.get("d", ""))}')
    return f"""
<div class="entry">
  <div class="head">
    <span class="rank">{r["rank"]}</span>
    <span class="word">{esc(r["headword"])}</span>
    <span class="ipa">{esc(r["phonetic"])}</span>
    <span class="lv {cls}">{lv}</span>
    <span class="stats">{stats}</span>
  </div>
  {senses_html(r, senses) if senses else f'<div class="gloss">{short_gloss(r)}' + ('<span class="pos">真题词性 ' + esc(pos) + '</span>' if pos else '') + '</div>'}
  {f'<div class="en">{esc(en)}</div>' if en and not senses else ''}
  {phrases_html(r["headword"])}
  {metrics_html(r["headword"])}
  {f'<div class="col"><span class="lab">句素</span>{col}</div>' if col else ''}
  {f'<ul class="ex">{"".join(example_html(e, r) for e in exs)}</ul>' if exs and not senses else ''}
  {f'<ul class="ex dict"><li>{highlight(dict_ex, r)} <span class="src">词典例句</span></li></ul>' if dict_ex and not senses else ''}
  {f'<div class="extra">{" · ".join(extra)}</div>' if extra else ''}
</div>"""


CSS = """
@page { size: A4; margin: 14mm 14mm 14mm 14mm;
        @bottom-center { content: counter(page); font-size: 8pt; color: #888; }
        @top-right { content: string(chap); font-size: 8pt; color: #888; } }
body { font-family: "Times New Roman", "Liberation Serif", "DejaVu Serif", "Noto Serif CJK SC", "Songti SC", serif; font-size: 9.6pt; line-height: 1.38; color: #111; }
h1 { font-family: "Noto Sans CJK SC", "PingFang SC", sans-serif; font-size: 20pt; margin: 0 0 4mm; string-set: chap content(); }
.chapintro { font-size: 9.5pt; color: #333; margin-bottom: 5mm; padding: 3mm 4mm; background: #f3f1ea; }
.chapter { page-break-before: always; }
.entry { border-bottom: 0.4pt solid #bbb; padding: 2.2mm 0 2.4mm; page-break-inside: avoid; }
.head { display: flex; align-items: baseline; gap: 2.5mm; }
.rank { font-family: sans-serif; font-size: 7.5pt; color: #fff; background: #333; padding: 0 1.4mm; border-radius: 1mm; }
.word { font-family: "Noto Sans CJK SC", sans-serif; font-size: 15pt; font-weight: 700; }
.ipa { font-family: "DejaVu Sans", "Lucida Grande", sans-serif; font-size: 8.5pt; color: #555; }
.lv { font-size: 7.5pt; border: 0.5pt solid; padding: 0 1mm; border-radius: 1mm; }
.lv0 { color: #2d6a4f; } .lv1 { color: #b5651d; } .lv2 { color: #9d0208; }
.stats { margin-left: auto; font-family: sans-serif; font-size: 8pt; color: #333; }
.gloss { margin-top: 0.8mm; }
.pos { margin-left: 3mm; font-size: 7.5pt; color: #777; font-family: sans-serif; }
.en { font-size: 8.3pt; color: #444; font-style: italic; }
.col { font-size: 8.8pt; margin-top: 0.6mm; } .col sup { font-size: 6pt; color: #999; }
.lab { font-family: sans-serif; font-size: 7.5pt; color: #fff; background: #7a7a7a; padding: 0 1mm; margin-right: 1.5mm; border-radius: 1mm; }
ul.ex { margin: 0.8mm 0 0; padding-left: 4.5mm; font-size: 8.8pt; }
ul.ex li { margin: 0.2mm 0; }
mark { background: none; font-weight: 700; text-decoration: underline; }
ul.dict { color: #555; font-style: italic; }
.src { font-family: sans-serif; font-size: 7pt; color: #888; }
.extra { font-size: 8pt; color: #555; margin-top: 0.6mm; }
ol.senses { margin: 0.8mm 0 0; padding-left: 5mm; }
ol.senses li { margin: 0.5mm 0; }
.zh { font-weight: 700; } .sen { margin-left: 2mm; font-size: 8.3pt; color: #444; font-style: italic; }
.sx { font-size: 8.6pt; }
.pct { font-family: sans-serif; font-size: 7pt; color: #9d0208; margin-left: 2mm; }
.pct .bar { display: inline-block; height: 1.6mm; background: #d88; margin-right: 1mm; vertical-align: middle; }
.ph { font-weight: 700; color: #1d4f91; } .lab.phl { background: #1d4f91; }
.rare { font-family: sans-serif; font-size: 7pt; color: #fff; background: #b5651d; padding: 0 1mm; margin-left: 1.5mm; border-radius: 1mm; }
.tested { font-family: sans-serif; font-size: 7.5pt; color: #fff; background: #2d6a4f; padding: 0 1.2mm; border-radius: 1mm; margin-right: 1.5mm; }
table.rs { border-collapse: collapse; font-size: 8.6pt; width: 100%; } table.rs td { border-bottom: 0.3pt solid #ccc; padding: 1mm 1.5mm; vertical-align: top; }
table.cov { border-collapse: collapse; font-size: 9pt; margin: 2mm 0; } table.cov td, table.cov th { border: 0.4pt solid #bbb; padding: 0.8mm 2.5mm; text-align: right; }
.mt { font-family: sans-serif; font-size: 7.5pt; color: #666; margin-top: 0.4mm; }
.legend { font-size: 9pt; } .legend td { padding: 1mm 3mm; vertical-align: top; }
"""

def cover_table():
    if not COVER: return ""
    rows = "".join(f'<tr><td>前 {c["top_n"]} 词</td><td>{100 * float(c["word_coverage"]):.1f}%</td><td>{100 * float(c["first_sense"]):.1f}%</td>'
                   f'<td>{100 * float(c["first_two_senses"]):.1f}%</td></tr>' for c in COVER if c["top_n"] in ("200", "500", "1000", "1600", "2552"))
    return (f'<p style="font-size:9pt;margin-top:4mm"><b>背多少词，能读懂多少？</b>"按单词"是常见的算法：真题里有多少词次是这些词。'
            f'但只认识一个词的第一个意思，并不能读懂它的所有用法。"只会第一义项"只把用到第一义项的地方算作读懂，短语里的用法也不算。</p>'
            f'<table class="cov"><tr><th></th><th>按单词</th><th>只会第一义项</th><th>会前两个义项</th></tr>{rows}</table>')


def rare_appendix():
    if not RARE: return ""
    ER = {x["headword"]: x for x in rows}
    trs = "".join(f'<tr><td><b>{esc(r["headword"])}</b> <span class="src">#{r["rank"]}</span></td><td>{esc(r["pos"])} {esc(r["zh"])}'
                   f'{" <b>（真题以此为主）</b>" if r["dominant"] == "True" else ""}</td>'
                   f'<td>{highlight(r["example"], ER.get(r["headword"], {"headword": r["headword"], "inflections": ""})) if r["example"] else ""} <span class="src">{esc(r["example_src"])}</span></td></tr>'
                   for r in sorted(RARE, key=lambda r: (r["dominant"] != "True", int(r["rank"]))))
    return (f'<section class="chapter"><h1>附录　熟词生义</h1><div class="chapintro">1000 名以后的词里，真题用到的、学生通常先学的那个意思之外的义项，'
            f'共 {len(RARE)} 处（{len({r["headword"] for r in RARE})} 个词）。标"真题以此为主"的，真题里这个意思比常见义还多。'
            + ('已逐条人工核对。' if all(r.get("checked") == "y" for r in RARE) else '义项由模型标注，释义可能有误。') + f'</div><table class="rs">{trs}</table></section>')


def cover():
    return f"""<div class="cover"><h1>高考英语词汇表 · 按真题频次排序</h1>
<p>语料：2008–2026 年高考英语全国 I 卷系列，共 {tot['papers']} 份试卷、{tot['years']} 个年份，约 {tot['tokens_all']:,} 词次（不含人名地名）。<br>
词表：《普通高中英语课程标准（2017 年版 2025 年修订）》附录 2 词汇表，另加数词、月份、星期和国家名称。</p>
<table class="legend">
<tr><td><b>排序</b></td><td>先按"出现年数"，再按"总次数"。年年都考的词排在前面。</td></tr>
<tr><td><b>义务 / 必修 / 选必</b></td><td>课标级别：义务教育阶段 / 高中必修 / 选择性必修。</td></tr>
<tr><td><b>12/19 年 · 30 次</b></td><td>19 个年份里有 12 年出现，累计 30 次。</td></tr>
<tr><td><b>真题词性</b></td><td>这个词在真题里作各词性的比例；释义按这个顺序排。</td></tr>
<tr><td><b>义项</b></td><td>只列真题实际用到的义项。多义词的每一次出现都逐句标注过义项，按全部出现次数排序；红色百分比是这个义项占该词全部出现的比例（出现太少的义项不列）。每个义项附中文、简明英文释义和一句真题原句。</td></tr>
<tr><td><b>短语</b></td><td>意思不能从字面推出的短语和语法短语（如 take place、have to），右上角是真题出现次数。只看懂单词、看不懂短语，是常见的失分点。</td></tr>
<tr><td><b>考点</b></td><td>这个词当过完形填空或语法填空的<b>正确答案</b>（命题人专门考的词），"完形×2"表示两次。约四分之一的完形答案排在 1000 名以后。</td></tr>
<tr><td><b>生义</b></td><td>常见义之外、真题实际用到的意思（熟词生义）。不论生僻与否，真题这样用过，就值得单独记；书末附录汇总。</td></tr>
<tr><td><b>分布</b></td><td>"36% 在短语中"：这个词的出现有多少在短语里；"分布在 N 篇"：出现在多少篇不同的文章或对话里；"集中在同一篇"：次数主要来自一篇文章，实际重要性比次数显示的低；"听力占"：主要在听力里出现。</td></tr>
<tr><td><b>句素</b></td><td>从真题原句中抽出的固定搭配，右上角小数字是出现次数。"make + mistake"表示动宾搭配。</td></tr>
<tr><td><b>例句</b></td><td>真题原句，标出年份和题型；真题里没有合适例句的词，用斜体的词典例句（Open English WordNet）代替。</td></tr>
<tr><td><b>派生 / 词根</b></td><td>课标不单列、但真题出现过的派生词；词根词缀注释。</td></tr>
</table>
{cover_table()}
<p style="font-size:8pt;color:#666">义项、短语释义与简明英文释义：本项目自编（CC BY-SA 4.0）；义项标注由 Claude 模型完成，难判的句子经第二个模型复核和人工判定；其余词条释义：ECDICT（MIT）；英文释义：Open English WordNet（CC BY 4.0）。本词汇表以 CC BY-SA 4.0 发布。</p></div>"""


wanted = {int(x) for x in a.chapters.split(",") if x} or set(range(1, len(CHAPTERS) + 1))
parts, cum = [cover()], 0
for i, (lo, hi, name) in enumerate(CHAPTERS, 1):
    chunk = unseen if lo is None else [r for r in seen if lo <= int(r["rank"]) <= hi]
    if not chunk: continue
    before = cum
    cum += sum(hits.get(r["headword"], 0) for r in chunk)
    if i not in wanted: continue
    if lo is None:
        intro = f"以下 {len(chunk)} 个课标词在 2008–2026 年的真题中没有出现过。课标仍要求掌握，但可以放在最后。"
        title = f"第 {i} 章　{name}"
    else:
        last = int(chunk[-1]["rank"])
        intro = (f"本章 {len(chunk)} 个词（第 {lo}–{last} 名）。背完前 {last} 个词，可以覆盖真题文本 "
                 f"<b>{100 * cum / tot['tokens_all']:.1f}%</b> 的词次（本章贡献 {100 * (cum - before) / tot['tokens_all']:.1f}%）。")
        title = f"第 {i} 章　{name}（{lo}–{last}）"
    parts.append(f'<section class="chapter"><h1>{title}</h1><div class="chapintro">{intro}</div>')
    parts += [entry_html(r) for r in chunk]
    parts.append("</section>")

parts.append(rare_appendix())
doc = f"<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'><title>高考英语词汇表</title><style>{CSS}</style></head><body>{''.join(parts)}</body></html>"
open(a.out + ".html", "w", encoding="utf-8").write(doc)
try:
    from weasyprint import HTML
    HTML(string=doc).write_pdf(a.out + ".pdf")
    print("wrote", a.out + ".html", a.out + ".pdf")
except ImportError:
    print("wrote", a.out + ".html  (install weasyprint for PDF, or print the HTML from Chrome)")
