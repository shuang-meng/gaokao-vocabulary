# -*- coding: utf-8 -*-
"""Step 9c: 熟词生义 — exam senses beyond the meaning students learn first.

Scope (user decision, 2026-11-21): not only "rare" meanings. Any exam sense other than the familiar one is worth
learning on its own, because the exam uses the word in exactly that way. Only part-of-speech variants of a
familiar exam sense are left out.

usage: python scripts/09c_rare_senses.py  -> data/processed/rare_senses.csv
Filter: an r sense is kept unless its Chinese gloss shares a two-character word with a familiar (c) exam sense.
Hand check: data/manual/rare_senses_review.csv (from the page of step 9d) — verdict n removes a candidate,
zh_fixed replaces its gloss; column checked = y for confirmed rows.
Source: the low-frequency words labelled in step 8h, where the model marked each sense c (the meaning students
learn first) or r (a less familiar meaning). A row is one r sense; "dominant" = the exam uses the r sense at least
as often as all c senses together (and at least twice), i.e. a student who knows only the familiar meaning misreads most uses.
"""
import collections, csv, re

P = 'data/processed'


def bigrams(t):
    t = re.sub(r'[（(].*?[)）]|[a-zA-Z.…]', '', t)
    return {t[i:i + 2] for i in range(len(t) - 1) if re.fullmatch(r'[\u4e00-\u9fff]{2}', t[i:i + 2])}


def first_glosses(zh_gloss, k=4):
    """The first k Chinese glosses of each part of speech in ECDICT — what a student meets first."""
    out = set()
    for part in zh_gloss.replace('\\r', ' ').split('|'):
        gl = [g for g in re.split(r'[,，;；]', re.sub(r'^\s*[a-z]+\.\s*', '', part.strip())) if g.strip()]
        for g in gl[:k]:
            out |= bigrams(g)
    return out


def main():
    E = {r['headword']: r for r in csv.DictReader(open(f'{P}/entries_with_defs.csv', encoding='utf-8-sig'))}
    by = collections.defaultdict(list)
    for r in csv.DictReader(open(f'{P}/senses_full.csv', encoding='utf-8-sig')):
        if r['common'] in ('c', 'r'):
            by[r['headword']].append(r)
    out = []
    for w, ss in by.items():
        c = sum(int(s['count']) for s in ss if s['common'] == 'c')
        known = set()        # (until 2026-11-21 also the dictionary's first glosses; dropped at the user's request:
        for s in ss:         #  every exam sense beyond the familiar one is worth learning, rare or not)
            if s['common'] == 'c':
                known |= bigrams(s['zh'])
        for s in ss:
            # drop r senses that only change the part of speech of a familiar exam sense (plastic n. 塑料 -> adj. 塑料的)
            if s['common'] == 'r' and not (bigrams(s['zh']) & known):
                out.append({'headword': w, 'rank': E[w]['rank'], 'level': E[w]['level'], 'sense': s['sense'],
                            'pos': s['pos'], 'zh': s['zh'], 'count': s['count'], 'familiar_count': c,
                            'dominant': int(s['count']) >= max(c, 2), 'example': s['example'], 'example_src': s['example_src']})
    # your check (step 9d): verdict n drops a candidate, zh_fixed corrects its gloss
    import os
    rv = {}
    if os.path.exists('data/manual/rare_senses_review.csv'):
        rv = {(r['headword'], r['sense']): r for r in csv.DictReader(open('data/manual/rare_senses_review.csv', encoding='utf-8-sig'))}
    for r in out:
        v = rv.get((r['headword'], r['sense']), {})
        r['checked'] = v.get('verdict', '')
        if v.get('zh_fixed') and v.get('verdict') != 'n':
            m = re.match(r'^((?:[a-z]+\./?)+)\s+(.*)$', v['zh_fixed'])     # "n. 旅鸽" also corrects the part of speech
            r['pos'], r['zh'] = (m.group(1), m.group(2)) if m else (r['pos'], v['zh_fixed'])
    out = [r for r in out if r['checked'] != 'n']
    out.sort(key=lambda r: (not r['dominant'], int(r['rank'])))
    with open(f'{P}/rare_senses.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0].keys())); wr.writeheader(); wr.writerows(out)
    d = [r for r in out if r['dominant']]
    print(f"{len(out)} less familiar senses in {len({r['headword'] for r in out})} words; "
          f"{len(d)} where the exam mostly uses the less familiar meaning")
    print('; '.join(f"{r['headword']} {r['pos']}{r['zh']}({r['count']}/{r['familiar_count']})" for r in d[:40]))


if __name__ == '__main__':
    main()
