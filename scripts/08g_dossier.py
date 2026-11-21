# -*- coding: utf-8 -*-
"""Step 8g: word dossier — every labelled exam occurrence (all labelled words), grouped by sense and phrase.

usage: python scripts/08g_dossier.py            -> output/dossier_all.html
PERSONAL RESEARCH ONLY: the page holds about 21,000 exam sentences. output/*.html is in .gitignore; do not publish it.
"""
import collections, csv, html, json, re

SEC = {'listening': '听力', 'reading': '阅读', 'cloze': '完形', 'grammar': '语法填空', 'seven': '七选五',
       'writing': '写作', 'single_choice': '单选', 'correction': '改错'}
CLS = {'idiom': '习语', 'functional': '功能短语'}
e = html.escape


def hl(s, sf):
    s = e(re.sub(r'\s+', ' ', s.strip()))
    return re.sub(r'\b(' + re.escape(e(sf)) + r')\b', r'<mark>\1</mark>', s, count=1, flags=re.I)


def li(r):
    src = f"{r['year']} {r['paper'].split('_')[1]} {SEC.get(r['section'], r['section'])}"
    tag = '' if r['source'] == 'api' and r['confidence'] == 'h' else \
        f" <span class=c>{'人工' if r['source'] == 'hand' else '复核' if r['confidence'] == 'a' else r['confidence']}</span>"
    return f'<li>{hl(r["sentence"], r["surface"])} <span class="src">{src}</span>{tag}</li>'


def main():
    O = list(csv.DictReader(open('data/interim/sense_occurrences.csv', encoding='utf-8-sig')))
    S = collections.defaultdict(dict)
    for r in csv.DictReader(open('data/processed/senses_full.csv', encoding='utf-8-sig')):
        S[r['headword']][r['sense']] = r
    M = {r['word']: r for r in csv.DictReader(open('data/processed/word_sense_metrics.csv', encoding='utf-8-sig'))}
    PE = {r['phrase']: r for r in csv.DictReader(open('data/processed/phrase_entries.csv', encoding='utf-8-sig'))}
    GL = {r['phrase']: r['zh'] for r in csv.DictReader(open('data/manual/phrase_glosses.csv', encoding='utf-8-sig'))}
    by = collections.defaultdict(list)
    for r in O:
        by[r['word']].append(r)
    words = sorted(by, key=lambda w: int(M[w]['word_rank']))
    P = ['''<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>单词档案（全部真题用例，按义项分组）</title><style>
body{font-family:-apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif;max-width:920px;margin:20px auto;padding:0 16px;color:#222;line-height:1.5}
h1{font-size:22px}h2{margin-top:34px;border-bottom:2px solid #333;padding-bottom:4px}h2 small{font-weight:normal;color:#777;font-size:13px}
h3{font-size:14px;margin:12px 0 4px;color:#555}details{margin:5px 0 8px}summary{cursor:pointer;font-weight:600}
summary .n{color:#a33;font-weight:normal}.new{background:#ffe9a8;font-size:11px;padding:0 4px;border-radius:3px;margin-left:6px;font-weight:normal}
.bar{display:inline-block;height:8px;background:#c55;vertical-align:middle;margin-left:6px}.pbar{background:#4a7fc0}
ul{margin:4px 0 0;padding-left:20px}li{margin:3px 0;font-size:14px}.src{color:#888;font-size:12px}mark{background:#fff2a8}
.c{font-size:11px;color:#fff;background:#999;border-radius:3px;padding:0 3px}.mt{font-size:13px;color:#555}
.note{background:#f4f2ec;padding:8px 12px;font-size:13px}#q{font-size:16px;padding:6px 10px;width:260px;position:sticky;top:6px}
.toc{font-size:13px;line-height:1.9}.toc a{margin-right:6px;color:#1d4f91;text-decoration:none}
</style></head><body><h1>单词档案：课标词的全部真题用例（按义项分组）</h1>
<div class="note">仅供个人研究使用，含大量真题原文，请勿公开。每个词按义项分组，红色数字是全量次数；蓝色是短语。
黄色"新"＝抽样时没有、全量标注时新增的义项。灰色小标：人工＝人工判定，复核＝两个模型一致，m/l＝模型把握一般/较低。点击义项展开原句。</div>
<p><input id="q" placeholder="输入单词跳转，如 take" onkeydown="if(event.key==='Enter'){location.hash=this.value.trim().toLowerCase()}"></p>
<p class="toc">''' + ' '.join(f'<a href="#{w}">{w}</a>' for w in words) + '</p>']
    for w in words:
        rs, m = by[w], M[w]
        ys = len({r['year'] for r in rs})
        P.append(f'<h2 id="{w}">{w} <small>#{m["word_rank"]} · 真题 {len(rs)} 次 · {ys} 年 · {m["passages"]} 篇</small></h2>')
        bits = [f'首义项 {round(100 * float(m["top_sense_share"]))}%', f'短语中 {round(100 * float(m["phrase_share"]))}%',
                f'听力 {round(100 * float(m["listening_share"]))}%', f'最大单篇占 {round(100 * float(m["biggest_passage_share"]))}%']
        P.append(f'<div class="mt">{" · ".join(bits)}</div>')
        words_only = [r for r in rs if not r['phrase']]
        c = collections.Counter(r['sense'] for r in words_only)
        mx = max(list(c.values()) + [1])
        P.append(f'<h3>单词义项 <small class=src>{len(words_only)} 次</small></h3>')
        for k, n in c.most_common():
            items = sorted((r for r in words_only if r['sense'] == k), key=lambda r: r['year'])
            s = S[w].get(k, {})
            name = f"{s.get('pos', '')} {s.get('zh', '')}".strip() or items[0]['sense_name']
            lis = sum(r['section'] == 'listening' for r in items)
            new = '<span class="new">新</span>' if s.get('added') == 'True' else ''
            en = f"<br><i class=src>{e(s['en'])}</i>" if s.get('en') else ''
            P.append(f'<details{" open" if n == mx else ""}><summary>{e(name)} <span class="n">{n}</span>{new}'
                     f'<span class="bar" style="width:{int(160 * n / mx)}px"></span> <span class="src">听力 {lis} · 笔头 {n - lis}</span>{en}</summary><ul>'
                     + ''.join(li(r) for r in items) + '</ul></details>')
        phr = [r for r in rs if r['phrase']]
        if phr:
            pc = collections.Counter(r['phrase'] for r in phr)
            P.append(f'<h3>短语 <small class=src>{len(phr)} 次，占 {len(phr) / len(rs):.0%}</small></h3>')
            pm = max(pc.values())
            for p, n in pc.most_common():
                items = sorted((r for r in phr if r['phrase'] == p), key=lambda r: r['year'])
                pe = PE.get(p, {})
                P.append(f'<details><summary><span style="color:#1d4f91">{e(p)}</span> {e(GL.get(p, ""))} <span class="n">{n}</span>'
                         f'<span class="bar pbar" style="width:{int(120 * n / pm)}px"></span> '
                         f'<span class="src">{CLS.get(pe.get("class"), "")} · 全卷 {pe.get("count", "?")} 次 / {pe.get("years", "?")} 年</span></summary><ul>'
                         + ''.join(li(r) for r in items) + '</ul></details>')
    P.append('</body></html>')
    open('output/dossier_all.html', 'w', encoding='utf-8').write('\n'.join(P))
    print(f'{len(words)} words, {len(O)} sentences -> output/dossier_all.html')


if __name__ == '__main__':
    main()
