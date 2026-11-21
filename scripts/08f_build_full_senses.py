# -*- coding: utf-8 -*-
"""Step 8f: one table of word senses with FULL exam counts (replaces the sample counts of step 5b).

usage: python scripts/08f_build_full_senses.py
Inputs : data/processed/senses.csv            (hand-written senses: pos, zh, en, example — step 5b)
         data/processed/sense_freq.csv        (full counts per sense — step 8c)
         data/interim/sense_occurrences.csv   (to pick an example for senses found only by the full pass)
         data/manual/new_sense_map.csv, data/manual/sense_merges.csv (names of added / merged senses)
         data/processed/entries_with_defs.csv
Output : data/processed/senses_full.csv — one row per sense, most frequent first:
         headword, sense, pos, zh, en, count, years, passages, listening, share (of all occurrences, phrases included), example, example_src, added, counted, common
         common (low-frequency words, step 8h): c = the meaning students learn first, r = a less familiar meaning.
         counted = full (every occurrence labelled) or single (one sense only: count = the word's total).
Only a short example sentence per sense comes from the exam texts, as in senses.csv.
"""
import collections, csv, glob, importlib.util, json, os, re

spec = importlib.util.spec_from_file_location('b', os.path.join(os.path.dirname(__file__), '07b_build_senses.py'))
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
SEC = {'listening': '听力', 'reading': '阅读', 'cloze': '完形', 'grammar': '语法填空', 'seven': '七选五',
       'writing': '写作', 'single_choice': '单选', 'correction': '改错'}
EX_PREF = {'reading': 0, 'seven': 1, 'cloze': 2, 'grammar': 2, 'writing': 3, 'listening': 4, 'single_choice': 8, 'correction': 9}


def split_name(name):
    m = re.match(r'^((?:[a-z]+\./?)+)\s+(.*)$', name.strip())
    return (m.group(1), m.group(2)) if m else ('', name.strip())


def pick_example(rows):
    best = None
    for r in rows:
        s = b.clean(r['sentence'])
        if not b.usable(s) or not re.search(r'\b' + re.escape(r['surface']) + r'\b', s):
            continue
        n = len(s.split())
        if not 6 <= n <= 32:
            continue
        key = (EX_PREF.get(r['section'], 5), abs(n - 16) // 6, -int(r['year']))
        if best is None or key < best[0]:
            best = (key, s, f"{r['year']} {r['paper'].split('_')[1]} {SEC.get(r['section'], r['section'])}")
    return (best[1], best[2]) if best else ('', '')


def main():
    P = 'data/processed'
    base = collections.defaultdict(dict)
    for r in csv.DictReader(open(f'{P}/senses.csv', encoding='utf-8-sig')):
        base[r['headword']][r['sense_no']] = r
    E = {r['headword']: r for r in csv.DictReader(open(f'{P}/entries_with_defs.csv', encoding='utf-8-sig'))}
    merged_from = collections.defaultdict(set)
    if os.path.exists('data/manual/sense_merges.csv'):
        for r in csv.DictReader(open('data/manual/sense_merges.csv', encoding='utf-8-sig')):
            merged_from[(r['word'], r['to'])].add(r['from'])
    occ = collections.defaultdict(list)
    for r in csv.DictReader(open('data/interim/sense_occurrences.csv', encoding='utf-8-sig')):
        if not r['phrase']:
            occ[(r['word'], r['sense'])].append(r)
    total = {r['word']: int(r['occurrences'])                    # all labelled occurrences, phrases included
             for r in csv.DictReader(open(f'{P}/word_sense_metrics.csv', encoding='utf-8-sig'))}
    freq = collections.defaultdict(list)
    for r in csv.DictReader(open(f'{P}/sense_freq.csv', encoding='utf-8-sig')):
        freq[r['word']].append(r)

    common = {}                                # step 8h: c = the meaning students learn first, r = a less familiar one
    for p in glob.glob('data/interim/annotations/*.json'):
        d = json.load(open(p, encoding='utf-8'))
        if d.get('kind') == 'rare':
            common[d['word']] = d.get('sense_common', {})
    out = []
    for w in list(base) + sorted(w for w in freq if w not in base):
        if w in freq:
            for f in sorted(freq[w], key=lambda t: -int(t['count'])):
                s = f['sense']; bs = base.get(w, {}).get(s)
                pos, zh = split_name(f['sense_name'])
                if bs and not merged_from.get((w, s)):
                    pos, zh = bs['pos'] or pos, bs['zh']
                ex, src = (bs['example'], bs['example_src']) if bs and bs['example'] else pick_example(occ[(w, s)])
                n = int(f['count'])
                out.append({'headword': w, 'sense': s, 'pos': pos, 'zh': zh, 'en': bs['en'] if bs else '',
                            'count': n, 'years': f['years'], 'passages': f['passages'], 'listening': f['listening'],
                            'share': round(n / total[w], 3) if total[w] else '', 'example': ex, 'example_src': src,
                            'added': not bs and w not in common, 'counted': 'full',
                            'common': common.get(w, {}).get(s, '')})
        else:
            rs = list(base[w].values())
            for bs in rs:
                single = len(rs) == 1
                out.append({'headword': w, 'sense': bs['sense_no'], 'pos': bs['pos'], 'zh': bs['zh'], 'en': bs['en'],
                            'count': E[w]['total_count'] if single else '', 'years': E[w]['years_count'] if single else '',
                            'passages': '', 'listening': '', 'share': 1.0 if single else '',
                            'example': bs['example'], 'example_src': bs['example_src'], 'added': False,
                            'counted': 'single' if single else 'sample', 'common': ''})
    with open(f'{P}/senses_full.csv', 'w', encoding='utf-8-sig', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=list(out[0].keys())); wr.writeheader(); wr.writerows(out)
    c = collections.Counter(r['counted'] for r in out)
    print(f"{len({r['headword'] for r in out})} words, {len(out)} senses -> {P}/senses_full.csv; {dict(c)}; "
          f"{sum(1 for r in out if not r['example'])} without example, {sum(r['added'] for r in out)} added")


if __name__ == '__main__':
    main()
