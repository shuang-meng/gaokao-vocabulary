# -*- coding: utf-8 -*-
"""Step 9d: a click-through page to check the 熟词生义 list by hand (is the gloss right? keep / delete).

usage: python scripts/09d_rare_review_page.py   -> output/rare_review.html (exam sentences: local only, not in git)
For every candidate the page shows the word's usual dictionary meanings, its familiar exam senses, the rare sense
and all its exam sentences. Choose 是僻义 / 不是僻义, optionally correct the Chinese gloss, then press 导出:
it downloads rare_senses_review.csv. Put it in data/manual/ and run 09c and 06 again.
"""
import collections, csv, html, json, os, re

P = 'data/processed'
e = html.escape
SEC = {'listening': '听力', 'reading': '阅读', 'cloze': '完形', 'grammar': '语法填空', 'seven': '七选五',
       'writing': '写作', 'single_choice': '单选', 'correction': '改错'}


def main():
    R = list(csv.DictReader(open(f'{P}/rare_senses.csv', encoding='utf-8-sig')))
    E = {r['headword']: r for r in csv.DictReader(open(f'{P}/entries_with_defs.csv', encoding='utf-8-sig'))}
    S = collections.defaultdict(list)
    for r in csv.DictReader(open(f'{P}/senses_full.csv', encoding='utf-8-sig')):
        S[r['headword']].append(r)
    occ = collections.defaultdict(list)
    for r in csv.DictReader(open('data/interim/sense_occurrences.csv', encoding='utf-8-sig')):
        occ[(r['word'], r['sense'])].append(r)
    done = {}
    f = 'data/manual/rare_senses_review.csv'
    if os.path.exists(f):
        done = {(r['headword'], r['sense']): r for r in csv.DictReader(open(f, encoding='utf-8-sig'))}
    items = []
    for r in R:
        w, s = r['headword'], r['sense']
        sents = [{'s': re.sub(r'\s+', ' ', o['sentence'].strip()), 'f': o['surface'],
                  'src': f"{o['year']} {o['paper'].split('_')[1]} {SEC.get(o['section'], o['section'])}"} for o in occ[(w, s)]]
        fam = [f"{x['pos']} {x['zh']} ×{x['count']}" for x in S[w] if x['common'] == 'c']
        d = done.get((w, s), {})
        items.append({'w': w, 's': s, 'rank': r['rank'], 'gloss': f"{r['pos']} {r['zh']}", 'dom': r['dominant'] == 'True',
                      'dict': re.sub(r'\s+', ' ', E[w]['zh_gloss'].replace('\\r', ' '))[:160], 'fam': fam, 'sents': sents,
                      'v': d.get('verdict', ''), 'fix': d.get('zh_fixed', '')})
    page = r'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><title>熟词生义核对</title><style>
body{font-family:-apple-system,"PingFang SC",sans-serif;max-width:860px;margin:0 auto;padding:16px;color:#222;background:#fafafa}
header{position:sticky;top:0;background:#fafafa;padding:8px 0;border-bottom:1px solid #ddd;display:flex;gap:10px;align-items:center;z-index:2}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:12px 16px;margin:12px 0}.card.yes{border-color:#7bb77b;background:#f6fbf6}.card.no{border-color:#d99;background:#fcf6f6}
.w{font-size:20px;font-weight:600;color:#1f5fbf}.meta{color:#888;font-size:13px}.rare{font-size:16px;margin:6px 0}.rare b{color:#b5651d}
.dict,.fam{font-size:13px;color:#555;margin:2px 0}ul{margin:6px 0;padding-left:20px}li{font-size:14px;margin:3px 0}mark{background:#ffe27a}.src{color:#999;font-size:12px}
button{font:inherit;cursor:pointer;padding:6px 12px;border:1px solid #bbb;border-radius:6px;background:#fff}button.sel{color:#fff}
button.y.sel{background:#2d6a4f;border-color:#2d6a4f}button.n.sel{background:#a33;border-color:#a33}.primary{background:#1f5fbf;color:#fff;border-color:#1f5fbf}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px}input{font:inherit;padding:5px 8px;border:1px solid #ccc;border-radius:6px}.lbl{font-size:13px;color:#666}
.dom{font-size:11px;background:#b5651d;color:#fff;border-radius:3px;padding:0 5px;margin-left:6px}
</style></head><body><header><b>熟词生义核对</b><span id="prog" class="lbl"></span><label class="lbl"><input type="checkbox" id="todo"> 只看未完成</label>
<span style="flex:1"></span><button class="primary" onclick="exp()">导出 rare_senses_review.csv</button></header>
<p class="lbl">这些都是常见义之外、真题实际用到的义项，默认都收进书里。只需检查：释义对不对、是不是标错了。对 → 保留；标错了（句子里其实就是常见义，或根本不是这个意思）→ 删除。释义不准可以在框里改。选择会自动保存在本浏览器里。</p>
<div id="list"></div><script>
const IT=__DATA__;const KEY='gaokao_rare_v2';let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
IT.forEach(i=>{const k=i.w+'|'+i.s;if(!st[k]&&(i.v||i.fix))st[k]={v:i.v,fix:i.fix}});
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}prog()};
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hl=(s,f)=>esc(s).replace(new RegExp('\\b('+f.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')\\b','gi'),'<mark>$1</mark>');
function prog(){document.getElementById('prog').textContent=`已完成 ${IT.filter(i=>(st[i.w+'|'+i.s]||{}).v).length} / ${IT.length}`}
function render(){const only=document.getElementById('todo').checked,L=document.getElementById('list');L.innerHTML='';
IT.forEach(i=>{const k=i.w+'|'+i.s,v=st[k]||{};if(only&&v.v)return;const c=document.createElement('div');c.className='card'+(v.v==='y'?' yes':v.v==='n'?' no':'');
c.innerHTML=`<div><span class="w">${esc(i.w)}</span> <span class="meta">#${i.rank}</span>${i.dom?'<span class="dom">真题以此为主</span>':''}</div>
<div class="dict">词典常见义：${esc(i.dict)}</div>${i.fam.length?`<div class="fam">真题里的常见义：${esc(i.fam.join('；'))}</div>`:''}
<div class="rare">真题义：<b>${esc(i.gloss)}</b></div><ul>${i.sents.map(s=>`<li>${hl(s.s,s.f)} <span class="src">${s.src}</span></li>`).join('')}</ul>
<div class="row"><button class="y${v.v==='y'?' sel':''}">保留</button><button class="n${v.v==='n'?' sel':''}">删除（标错了）</button>
<span class="lbl">释义改为：</span><input class="fx" size="22" value="${esc(v.fix||'')}" placeholder="${esc(i.gloss)}"></div>`;L.appendChild(c);
const set=x=>{st[k]={...(st[k]||{}),v:x};save();c.className='card '+(x==='y'?'yes':'no');c.querySelector('.y').classList.toggle('sel',x==='y');c.querySelector('.n').classList.toggle('sel',x==='n');if(only)setTimeout(()=>c.remove(),250)};
c.querySelector('.y').onclick=()=>set('y');c.querySelector('.n').onclick=()=>set('n');
c.querySelector('.fx').onchange=e=>{st[k]={...(st[k]||{}),fix:e.target.value.trim()};save()}});prog()}
function exp(){const q=s=>'"'+String(s||'').replace(/"/g,'""')+'"';const L=['headword,sense,verdict,zh_fixed'];
IT.forEach(i=>{const v=st[i.w+'|'+i.s]||{};if(v.v||v.fix)L.push([i.w,i.s,v.v,v.fix].map(q).join(','))});
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+L.join('\n')],{type:'text/csv'}));a.download='rare_senses_review.csv';a.click()}
document.getElementById('todo').onchange=render;render();</script></body></html>'''
    open('output/rare_review.html', 'w', encoding='utf-8').write(page.replace('__DATA__', json.dumps(items, ensure_ascii=False)))
    print(f'{len(items)} candidates -> output/rare_review.html')


if __name__ == '__main__':
    main()
