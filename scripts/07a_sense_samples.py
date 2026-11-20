# -*- coding: utf-8 -*-
"""Draw a fixed, diverse sample of exam sentences per word for sense annotation.

usage: 07a_sense_samples.py occurrences.tsv entries_with_defs.csv out.json RANK_LO RANK_HI [digest.txt]
The sample is deterministic: it spreads across years and sections, keeps sentences
of 6-35 words, and skips error-correction items. Each sentence gets an index, which
the sense files in data/manual/senses/*.json use to point to their examples.
"""
import csv, json, sys, re, random
from collections import defaultdict

SEC = {'listening': 'list', 'reading': 'read', 'cloze': 'cloz', 'grammar': 'gram',
       'seven': 'seve', 'writing': 'writ', 'correction': 'corr'}

def main(occ, entries, out, lo, hi, digest=None):
    lo, hi = int(lo), int(hi)
    E = [r for r in csv.DictReader(open(entries, encoding='utf-8-sig'))
         if r['rank'] and lo <= int(r['rank']) <= hi]
    want = {r['headword']: r for r in E}
    occs = defaultdict(list)
    with open(occ, encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            if r['headword'] in want and not r['section'].startswith('corr'):
                n = len(r['sentence'].split())
                if 6 <= n <= 35:
                    occs[r['headword']].append(r)
    res, lines = {}, []
    for w, e in want.items():
        k = 12 if int(e['rank']) <= 200 else 8
        rows = occs.get(w, [])
        seen, uniq = set(), []
        for r in rows:
            key = r['sentence'].strip()
            if key not in seen:
                seen.add(key); uniq.append(r)
        rnd = random.Random(w)
        rnd.shuffle(uniq)
        # round-robin over (section) to spread the sample
        buckets = defaultdict(list)
        for r in uniq:
            buckets[r['section'][:4]].append(r)
        pick = []
        while len(pick) < k and any(buckets.values()):
            for b in list(buckets):
                if buckets[b] and len(pick) < k:
                    pick.append(buckets[b].pop())
        pick.sort(key=lambda r: (r['year'], r['section']))
        res[w] = {'rank': int(e['rank']), 'count': int(e['total_count']), 'years': int(e['years_count']),
                  'function_word': e['function_word'],
                  'sents': [[r['year'], r['section'][:4], r['upos'], r['surface'], r['sentence'].strip(), r['line_code']] for r in pick]}
        if digest is not None and not e['function_word']:
            zh = ' | '.join(e['zh_gloss'].split(' | ')[:3])[:70]
            lines.append(f"## {w} r{e['rank']} {e['total_count']}x/{e['years_count']}y {e['exam_pos']} fw={e['function_word'] or '-'} | {e['collocations'][:90]} | {zh}")
            for i, s in enumerate(res[w]['sents']):
                sent, sf = s[4], s[3]
                m = re.search(r'\b' + re.escape(sf) + r'\b', sent)
                p = m.start() if m else 0
                a, b = max(0, p - 32), min(len(sent), p + len(sf) + 32)
                lines.append(f" {i} {s[0][2:]}{s[1][:2]} {s[2][:4]} {sent[a:b]}")
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    if digest is not None:
        open(digest, 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'{len(res)} words sampled')

if __name__ == '__main__':
    main(*sys.argv[1:])
