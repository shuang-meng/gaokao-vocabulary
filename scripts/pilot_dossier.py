# -*- coding: utf-8 -*-
"""Private word dossier: every exam occurrence of the annotated words, grouped by sense.

usage: python scripts/pilot_dossier.py data/pilot/full/occ_labeled.csv data/pilot/full/labels.json \
           data/manual/senses/pilot_ch2.json data/processed/entries_with_defs.csv data/pilot/full/dossier_30.html
The output contains many exam sentences: personal research use only (it is in .gitignore).
"""
import collections, csv, html, json, re, sys

SEC = {'listening': '听力', 'reading': '阅读', 'cloze': '完形', 'grammar': '语法填空', 'seven': '七选五',
       'writing': '写作', 'single_choice': '单选', 'correction': '改错'}
e = html.escape


def hl(s, sf):
    s = e(re.sub(r'\s+', ' ', s.strip()))
    return re.sub(r'\b(' + re.escape(e(sf)) + r')\b', r'<mark>\1</mark>', s, count=1)


def main(occ_csv, labels_json, senses_json, entries_csv, out):
    R = list(csv.DictReader(open(occ_csv, encoding='utf-8-sig')))
    P = json.load(open(senses_json)); P.pop('__sample_size__', None)
    L = json.load(open(labels_json))
    E = {r['headword']: r for r in csv.DictReader(open(entries_csv, encoding='utf-8-sig'))}
    by = collections.defaultdict(list)
    for r in R:
        by[r['word']].append(r)
    parts = ['''<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>单词档案（全量真题用例）</title><style>
body{font-family:-apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#222;line-height:1.5}
h1{font-size:22px}h2{margin-top:36px;border-bottom:2px solid #333;padding-bottom:4px}h2 small{font-weight:normal;color:#777;font-size:13px}h3{font-size:15px;margin:14px 0 4px;color:#555}
details{margin:6px 0 10px}summary{cursor:pointer;font-weight:600}summary .n{color:#a33;font-weight:normal}
summary .new{background:#ffe9a8;font-size:11px;padding:0 4px;border-radius:3px;margin-left:6px;font-weight:normal}
.bar{display:inline-block;height:8px;background:#c55;vertical-align:middle;margin-left:6px}
ul{margin:4px 0 0 0;padding-left:20px}li{margin:3px 0;font-size:14px}.src{color:#888;font-size:12px}mark{background:#fff2a8}
.toc a{margin-right:8px}.note{background:#f4f2ec;padding:8px 12px;font-size:13px}
</style></head><body><h1>单词档案：多义词的全部真题用例</h1>
<div class="note">仅供个人研究使用，含大量真题原文，请勿公开。红字是全量次数（2008 年两卷共用的句子只算一次）；黄色"新"是抽样时没有发现、全量标注时新增的义项。点击义项展开原句。"不计"是选项列表、改错原文或原文错字。</div><p class="toc">''',
             ' '.join(f'<a href="#{w}">{w}</a>' for w in P if w in by) + '</p>']
    for w in P:
        rs = by.get(w, [])
        if not rs:
            continue
        valid = [r for r in rs if r['sense'] != 'X']
        nold = len(P[w])
        c = collections.Counter(r['sense'] for r in valid)
        yrs = len({r['year'] for r in valid})
        parts.append(f'<h2 id="{w}">{w} <small>真题 {len(valid)} 次 · {yrs} 年 · {e(E[w]["exam_pos"])}</small></h2>')
        has_units = 'unit_kind' in valid[0]
        words_only = [r for r in valid if not has_units or r['unit_kind'] == '单词义项']
        phr = [r for r in valid if has_units and r['unit_kind'] != '单词义项']
        c = collections.Counter(r['sense'] for r in words_only)
        mx = max(list(c.values()) + [1])
        if has_units:
            parts.append(f'<h3>单词义项 <small class=src>{len(words_only)} 次</small></h3>')
        for k, n in sorted(c.items(), key=lambda x: -x[1]):
            items = [r for r in words_only if r['sense'] == k]
            lis = sum(1 for r in items if r['section'] == 'listening')
            en = P[w][int(k) - 1][2] if int(k) <= nold else ''
            new = '<span class="new">新</span>' if int(k) > nold else ''
            parts.append(f'<details{" open" if n == mx else ""}><summary>{e(L["names"][w][k])} <span class="n">{n}</span>{new}'
                         f'<span class="bar" style="width:{int(160 * n / mx)}px"></span> <span class="src">听力 {lis} · 笔头 {n - lis}</span>'
                         f'{("<br><i class=src>" + e(en) + "</i>") if en else ""}</summary><ul>')
            for r in sorted(items, key=lambda r: r['year']):
                parts.append(f'<li>{hl(r["sentence"], r["surface"])} <span class="src">{r["year"]} {r["paper"].split("_")[1]} {SEC.get(r["section"], r["section"])}</span></li>')
            parts.append('</ul></details>')
        if phr:
            pc = collections.Counter((r['unit'], r['unit_zh'], r['unit_kind']) for r in phr)
            parts.append(f'<h3>短语词条 <small class=src>{len(phr)} 次，占 {len(phr) / len(valid):.0%}</small></h3>')
            for (u, zh, kind), n in sorted(pc.items(), key=lambda x: -x[1]):
                items = [r for r in phr if r['unit'] == u and r['unit_zh'] == zh]
                yrs = len({r['year'] for r in items})
                parts.append(f'<details><summary><span style="color:#1d5fa8">{e(u)}</span> {e(zh)} <span class="n">{n}</span> '
                             f'<span class="src">{yrs} 年 · {kind}</span></summary><ul>')
                for r in sorted(items, key=lambda r: r['year']):
                    parts.append(f'<li>{hl(r["sentence"], r["surface"])} <span class="src">{r["year"]} {r["paper"].split("_")[1]} {SEC.get(r["section"], r["section"])}</span></li>')
                parts.append('</ul></details>')
        xs = [r for r in rs if r['sense'] == 'X']
        if xs:
            parts.append('<details><summary class=src>不计 ' + str(len(xs)) + '</summary><ul>' +
                         ''.join(f'<li class=src>{e(r["sentence"][:120])}</li>' for r in xs) + '</ul></details>')
    parts.append('</body></html>')
    open(out, 'w', encoding='utf-8').write('\n'.join(parts))
    print('wrote', out)


if __name__ == '__main__':
    main(*sys.argv[1:6])
