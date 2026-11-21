# -*- coding: utf-8 -*-
"""Step 9b: how much of the exam text a student can read — counted by word, and counted by sense.

"Learn the top N words" is usually measured as: share of exam tokens that are one of those N words.
But knowing a word usually means knowing its first meaning. Here a token only counts as covered when it is used
in a sense the student has learned: the k most frequent senses of the word (k = 1, 2, all). Tokens inside an
idiom / functional phrase are not covered by knowing the single word.
Words without sense labels (function words; words not yet labelled) are counted as fully covered — an upper bound.
usage: python scripts/09b_sense_coverage.py     -> data/processed/sense_coverage.csv and a printed table
"""
import collections, csv, json

P = 'data/processed'


def main():
    E = sorted(csv.DictReader(open(f'{P}/entries_with_defs.csv', encoding='utf-8-sig')), key=lambda r: int(r['rank']))
    hits = {r['headword']: int(r['coverage_hits']) for r in csv.DictReader(open(f'{P}/word_freq.csv', encoding='utf-8-sig'))}
    tot = json.load(open(f'{P}/token_totals.json'))['tokens_all']
    M = {r['word']: int(r['occurrences']) for r in csv.DictReader(open(f'{P}/word_sense_metrics.csv', encoding='utf-8-sig'))}
    sc = collections.defaultdict(list)
    for r in csv.DictReader(open(f'{P}/sense_freq.csv', encoding='utf-8-sig')):
        sc[r['word']].append(int(r['count']))
    share = {}
    for w, n in M.items():
        c = sorted(sc[w], reverse=True)
        share[w] = (sum(c[:1]) / n, sum(c[:2]) / n, sum(c) / n)       # phrase uses are in n but not in c
    cum = [0.0, 0.0, 0.0, 0.0]; out = []; marks = {200, 500, 1000, 1600, 2000, 2552}
    labelled = 0
    for r in E:
        w, h = r['headword'], hits.get(r['headword'], 0)
        if not h:
            continue
        s = share.get(w, (1, 1, 1)); labelled += h if w in share else 0
        cum[0] += h; cum[1] += h * s[0]; cum[2] += h * s[1]; cum[3] += h * s[2]
        rk = int(r['rank'])
        if rk in marks:
            out.append({'top_n': rk, 'word_coverage': round(cum[0] / tot, 4), 'first_sense': round(cum[1] / tot, 4),
                        'first_two_senses': round(cum[2] / tot, 4), 'all_senses_no_phrases': round(cum[3] / tot, 4)})
    with open(f'{P}/sense_coverage.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0].keys())); wr.writeheader(); wr.writerows(out)
    print(f'tokens {tot:,}; tokens of sense-labelled words {labelled:,} ({labelled / tot:.0%})')
    print('top N | word | 1st sense | 2 senses | all senses, no phrases')
    for o in out:
        print(f"{o['top_n']:>5} | {o['word_coverage']:.1%} | {o['first_sense']:.1%} | {o['first_two_senses']:.1%} | {o['all_senses_no_phrases']:.1%}")


if __name__ == '__main__':
    main()
