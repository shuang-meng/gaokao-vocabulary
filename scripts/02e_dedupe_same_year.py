# -*- coding: utf-8 -*-
"""Step 2e: count text shared by two papers of the same year only once.

usage: python scripts/02e_dedupe_same_year.py data/interim/corpus_all.tsv data/interim/corpus_dedup.tsv [report.tsv]

Some years have two papers (2008 DG1 + XKB, 2021-2023 YI + XG1). Papers of one year
can share material: in 2008 the listening, the single-choice items and part of the
reading are identical in both papers. A sentence of a later paper (sorted by line code:
DG1 < QG1 < XG1 < XKB < YI) is removed when the same sentence already appeared in an
earlier paper of that year, in sections where the two papers share at least 3 sentences
(so a question stem that recurs by chance is kept). Sentences are compared on their letters only, case ignored,
and only when they have at least 6 words, so short replies and question stems that recur by
chance ("Of course.", "What does the man mean?") are kept.
"""
import csv, re, sys
from collections import defaultdict

csv.field_size_limit(10**9)
SPLIT = re.compile(r'(?<=[.!?。！？])\s+')


def key(s):
    if len(s.split()) < 6:                       # short stems like "What does the man mean?" recur by chance
        return None
    k = re.sub(r'[^a-z]', '', s.lower())
    return k if len(k) >= 15 else None


def main(src, dst, report=None):
    rows = list(csv.DictReader(open(src, encoding='utf-8'), delimiter='\t'))
    fields = list(rows[0].keys())
    papers_by_year = defaultdict(set)
    for r in rows:
        papers_by_year[r['year']].add(r['paper_id'])
    seen = defaultdict(set)                      # year -> keys from earlier papers
    order = {}
    for y, ps in papers_by_year.items():
        for i, p in enumerate(sorted(ps)):
            order[p] = i
    # process papers of a year in order, so the first paper keeps the shared text
    rows_sorted = sorted(enumerate(rows), key=lambda t: (t[1]['year'], order[t[1]['paper_id']], t[0]))
    # first pass: which sections of a later paper really share material (>= 3 shared sentences)?
    first = defaultdict(set)
    for idx, r in rows_sorted:
        if order[r['paper_id']] == 0:
            first[r['year']].update(k for k in map(key, SPLIT.split(r['text'])) if k)
    shared = defaultdict(int)
    for idx, r in rows_sorted:
        if order[r['paper_id']] > 0:
            shared[(r['paper_id'], r['section'])] += sum(1 for k in map(key, SPLIT.split(r['text'])) if k and k in first[r['year']])
    blocks = {ps for ps, n in shared.items() if n >= 3}
    keep = {}
    removed = defaultdict(lambda: [0, 0])        # (paper, section) -> [sentences, words]
    for idx, r in rows_sorted:
        y, p = r['year'], r['paper_id']
        if len(papers_by_year[y]) == 1:
            keep[idx] = r['text']
            continue
        out, mine = [], []
        for s in SPLIT.split(r['text']):
            k = key(s)
            if k and k in seen[y] and (p, r['section']) in blocks and k not in mine:
                removed[(p, r['section'])][0] += 1
                removed[(p, r['section'])][1] += len(s.split())
                continue
            out.append(s)
            if k:
                mine.append(k)
        if order[p] == 0:
            seen[y].update(mine)
        dropped = len(out) < len(SPLIT.split(r['text']))
        keep[idx] = ' '.join(out) if dropped else r['text']   # untouched rows keep their exact text
    with open(dst, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter='\t')
        w.writeheader()
        for idx, r in enumerate(rows):
            if keep[idx].strip():
                r = dict(r, text=keep[idx])
                w.writerow(r)
    tot_s = sum(v[0] for v in removed.values()); tot_w = sum(v[1] for v in removed.values())
    print(f'removed {tot_s} duplicate sentences ({tot_w} words)')
    for (p, sec), (n, nw) in sorted(removed.items()):
        print(f'  {p} {sec}: {n} sentences, {nw} words')
    if report:
        with open(report, 'w', encoding='utf-8') as f:
            f.write('paper\tsection\tsentences\twords\n')
            for (p, sec), (n, nw) in sorted(removed.items()):
                f.write(f'{p}\t{sec}\t{n}\t{nw}\n')


if __name__ == '__main__':
    main(*sys.argv[1:])
