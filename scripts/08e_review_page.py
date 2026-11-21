# -*- coding: utf-8 -*-
"""Step 8e: turn data/interim/second_pass/to_review.csv into a click-through web page.

usage: python scripts/08e_review_page.py
Writes data/interim/second_pass/review.html (contains exam sentences: stays on your computer, not in git).
Open it in a browser, choose a sense for each sentence (your choices are kept in the browser while you work),
then press "导出" — it downloads to_review_filled.csv. Put that file into data/interim/second_pass/ and run
python scripts/08c_aggregate.py. Step 8c reads to_review_filled.csv if it is there.
"""
import csv, json, os, re

D = 'data/interim/second_pass'
rows = list(csv.DictReader(open(os.path.join(D, 'to_review.csv'), encoding='utf-8-sig')))
surf = {}
snap = os.path.join(D, 'queue_snapshot.csv')
for r in csv.DictReader(open(snap if os.path.exists(snap) else 'data/interim/review_queue.csv', encoding='utf-8-sig')):
    surf[r['occ_id']] = r['surface']
filled = {}                       # answers already exported: shown again when the page is rebuilt
fp = os.path.join(D, 'to_review_filled.csv')
if os.path.exists(fp):
    filled = {r['occ_id']: r for r in csv.DictReader(open(fp, encoding='utf-8-sig'))}
merge = {}
if os.path.exists('data/manual/sense_merges.csv'):
    merge = {(r['word'], r['from']): r for r in csv.DictReader(open('data/manual/sense_merges.csv', encoding='utf-8-sig'))}
items = []
for r in rows:
    w = r['word']
    mg = lambda s: merge[(w, s)]['to'] if (w, s) in merge else s
    a, b = mg(r['pass1'].split(' ')[0]), mg(r['pass2'].split(' ')[0])
    if a == b and r['occ_id'] not in filled:          # the disagreement disappears once the senses are merged
        continue
    senses, seen = [], set()
    names = {m['to']: m['name'] for k, m in merge.items() if k[0] == w and m['name']}
    for part in r['all_senses'].split(' | '):
        m = re.match(r'(\S+)\s+(.*)', part.strip())
        if m and mg(m.group(1)) not in seen:
            no = mg(m.group(1)); seen.add(no)
            senses.append([no, names.get(no, m.group(2))])
    ph = lambda x: (re.search(r'\[(.*?)\]', x) or [None, ''])[1]
    items.append({'id': r['occ_id'], 'word': r['word'], 'section': r['section'], 'sentence': r['sentence'],
                  'surface': surf.get(r['occ_id'], r['word']), 'p1': a, 'p2': b,
                  'ph1': ph(r['pass1']), 'ph2': ph(r['pass2']), 'senses': senses,
                  'your_sense': filled.get(r['occ_id'], r).get('your_sense', ''),
                  'your_phrase': filled.get(r['occ_id'], r).get('your_phrase', '')})

HTML = r'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><title>义项复核</title>
<style>
body{font-family:-apple-system,"PingFang SC",sans-serif;max-width:860px;margin:0 auto;padding:16px;color:#222;background:#fafafa}
header{position:sticky;top:0;background:#fafafa;padding:8px 0 10px;border-bottom:1px solid #ddd;z-index:2;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
header b{font-size:18px} .prog{color:#666} button{font:inherit;cursor:pointer}
.tool{padding:6px 12px;border:1px solid #bbb;border-radius:6px;background:#fff}
.tool.primary{background:#1f5fbf;color:#fff;border-color:#1f5fbf}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px 16px;margin:14px 0}
.card.done{border-color:#7bb77b;background:#f6fbf6}
.meta{color:#888;font-size:13px;margin-bottom:6px} .w{font-size:20px;font-weight:600;color:#1f5fbf;margin-right:8px}
.sent{font-size:16px;line-height:1.6;margin:6px 0 10px} mark{background:#ffe27a;padding:0 2px;border-radius:3px}
.opts{display:flex;flex-direction:column;gap:6px}
.opt{text-align:left;padding:7px 10px;border:1px solid #ccc;border-radius:6px;background:#fff;display:flex;gap:8px;align-items:center}
.opt:hover{border-color:#1f5fbf} .opt.sel{background:#1f5fbf;color:#fff;border-color:#1f5fbf}
.no{font-weight:600;min-width:28px} .tag{font-size:11px;padding:1px 6px;border-radius:9px;background:#eee;color:#555;margin-left:auto}
.opt.sel .tag{background:#fff3;color:#fff}
.row2{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center}
.row2 input{padding:6px 8px;border:1px solid #ccc;border-radius:6px;font:inherit}
.chip{padding:3px 9px;border:1px dashed #999;border-radius:12px;background:#fff;font-size:13px}
.lbl{font-size:13px;color:#666}
</style></head><body>
<header><b>义项复核</b><span class="prog" id="prog"></span>
<label class="lbl"><input type="checkbox" id="todo"> 只看未完成</label>
<span style="flex:1"></span><button class="tool primary" onclick="exportCsv()">导出 to_review_filled.csv</button></header>
<p class="lbl">每句选一个义项（或写自己的中文释义，或"无法判断"）。只有当这个词在句中属于<b>严格短语</b>（意思不能从字面推出）时才填短语；留空 = 不是短语。选择会自动保存在本浏览器里，可以分几次做。</p>
<div id="list"></div>
<script>
const ITEMS = __DATA__;
const KEY = 'gaokao_review_v1';
let st = {}; try { st = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
ITEMS.forEach(it => { if (!st[it.id] && (it.your_sense || it.your_phrase)) st[it.id] = {s: it.your_sense, p: it.your_phrase}; });
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} prog(); };
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function hl(s, w) { const e = esc(s); const re = new RegExp('\\b(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')\\b', 'i'); return e.replace(re, '<mark>$1</mark>'); }
function prog() { const n = ITEMS.filter(it => st[it.id] && st[it.id].s).length; document.getElementById('prog').textContent = `已完成 ${n} / ${ITEMS.length}`; }
function render() {
  const only = document.getElementById('todo').checked; const L = document.getElementById('list'); L.innerHTML = '';
  ITEMS.forEach((it, i) => {
    const v = st[it.id] || {}; if (only && v.s) return;
    const c = document.createElement('div'); c.className = 'card' + (v.s ? ' done' : ''); c.id = 'c' + i;
    const known = it.senses.map(s => s[0]);
    let h = `<div class="meta"><span class="w">${esc(it.word)}</span>${it.section} · ${i + 1}/${ITEMS.length}</div><div class="sent">${hl(it.sentence, it.surface)}</div><div class="opts">`;
    it.senses.forEach(([no, name]) => {
      const tags = [it.p1 === no ? '模型1' : '', it.p2 === no ? '模型2' : ''].filter(Boolean).join(' · ');
      h += `<button class="opt${v.s === no ? ' sel' : ''}" data-s="${esc(no)}"><span class="no">${esc(no)}</span><span>${esc(name)}</span>${tags ? `<span class="tag">${tags}</span>` : ''}</button>`;
    });
    const other = v.s && v.s !== 'X' && !known.includes(v.s) ? v.s : '';
    const extra = [it.p1, it.p2].filter(x => !known.includes(x) && x !== 'PHRASE').map(x => `模型提出：${x}`).join('；');
    h += `<button class="opt${v.s === 'X' ? ' sel' : ''}" data-s="X"><span class="no">X</span><span>无法判断（选项列表 / 乱码）</span></button></div>`;
    h += `<div class="row2"><span class="lbl">都不对，写释义：</span><input class="other" placeholder="例如：考虑；顾及" value="${esc(other)}" size="18">${extra ? `<span class="lbl">${esc(extra)}</span>` : ''}</div>`;
    const chips = [...new Set([it.ph1, it.ph2].filter(Boolean))].map(p => `<button class="chip" data-p="${esc(p)}">${esc(p)}</button>`).join(' ');
    h += `<div class="row2"><span class="lbl">短语：</span><input class="ph" value="${esc(v.p || '')}" size="22" placeholder="留空 = 不是短语">${chips ? '<span class="lbl">模型给的：</span>' + chips : ''}</div>`;
    c.innerHTML = h; L.appendChild(c);
    c.querySelectorAll('.opt').forEach(b => b.onclick = () => { st[it.id] = {...(st[it.id] || {}), s: b.dataset.s}; save(); refresh(c, it, i); });
    c.querySelector('.other').onchange = e => { const t = e.target.value.trim(); st[it.id] = {...(st[it.id] || {}), s: t}; save(); refresh(c, it, i); };
    c.querySelector('.ph').onchange = e => { st[it.id] = {...(st[it.id] || {}), p: e.target.value.trim()}; save(); };
    c.querySelectorAll('.chip').forEach(b => b.onclick = () => { c.querySelector('.ph').value = b.dataset.p; st[it.id] = {...(st[it.id] || {}), p: b.dataset.p}; save(); });
  });
  prog();
}
function refresh(c, it, i) {
  const v = st[it.id] || {}; c.classList.toggle('done', !!v.s);
  c.querySelectorAll('.opt').forEach(b => b.classList.toggle('sel', b.dataset.s === v.s));
  if (document.getElementById('todo').checked && v.s) { setTimeout(() => { c.remove(); }, 250); }
}
function exportCsv() {
  const q = s => '"' + String(s || '').replace(/"/g, '""') + '"';
  const lines = ['occ_id,word,your_sense,your_phrase'];
  ITEMS.forEach(it => { const v = st[it.id] || {}; if (v.s || v.p) lines.push([it.id, it.word, v.s, v.p].map(q).join(',')); });
  const blob = new Blob(['﻿' + lines.join('\n')], {type: 'text/csv'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'to_review_filled.csv'; a.click();
}
document.getElementById('todo').onchange = render;
render();
</script></body></html>'''
out = os.path.join(D, 'review.html')
open(out, 'w', encoding='utf-8').write(HTML.replace('__DATA__', json.dumps(items, ensure_ascii=False)))
print(f'{len(items)} rows -> {out}')
