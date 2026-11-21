# -*- coding: utf-8 -*-
"""Step 9c: 熟词僻义 — exam uses of a familiar word in a less familiar meaning.

usage: python scripts/09c_rare_senses.py  -> data/processed/rare_senses.csv
Filter: the model's c/r flag alone is unreliable, so an r sense is kept only when its Chinese gloss shares no
two-character word with the first ECDICT glosses of the word or with one of its familiar senses.
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
        known = first_glosses(E[w]['zh_gloss'])
        for s in ss:
            if s['common'] == 'c':
                known |= bigrams(s['zh'])
        for s in ss:
            # the model's r flag is noisy (awkward 尴尬的, plastic adj. 塑料的): keep an r sense only when its
            # Chinese shares no two-character word with the dictionary's first glosses or with a familiar sense
            if s['common'] == 'r' and not (bigrams(s['zh']) & known):
                out.append({'headword': w, 'rank': E[w]['rank'], 'level': E[w]['level'], 'sense': s['sense'],
                            'pos': s['pos'], 'zh': s['zh'], 'count': s['count'], 'familiar_count': c,
                            'dominant': int(s['count']) >= max(c, 2), 'example': s['example'], 'example_src': s['example_src']})
    out.sort(key=lambda r: (not r['dominant'], int(r['rank'])))
    with open(f'{P}/rare_senses.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0].keys())); wr.writeheader(); wr.writerows(out)
    d = [r for r in out if r['dominant']]
    print(f"{len(out)} less familiar senses in {len({r['headword'] for r in out})} words; "
          f"{len(d)} where the exam mostly uses the less familiar meaning")
    print('; '.join(f"{r['headword']} {r['pos']}{r['zh']}({r['count']}/{r['familiar_count']})" for r in d[:40]))


if __name__ == '__main__':
    main()
