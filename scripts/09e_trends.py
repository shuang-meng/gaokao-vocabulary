# -*- coding: utf-8 -*-
"""Step 9e: what changed from 2024 (new structure of the 新课标 I 卷)?

Period A = 2008–2023 (20 papers), period B = 2024–2026 (3 papers).
usage: python scripts/09e_trends.py
Outputs (no exam sentences):
  data/processed/trend_words.csv     every word: count and rate per 10,000 word hits in A and B, log-likelihood G2,
                                     years present in B; direction = up / down when significant (see below)
  data/processed/trend_sections.csv  share of word hits by section in A and B
  data/processed/trend_holdout.csv   rank the words with A only, then ask how much of B the top N cover
A word counts as rising only when G2 >= 6.63 (p < .01), it is at least twice as frequent in B, and it appears in at
least 2 of the 3 years of B — one long 2025 passage about bees must not make "bee" a trend.
Word counts use passages / transcripts only: question stems and options are captured unevenly across papers, and
single choice and error correction no longer exist from 2024. Section shares use all word hits.
"""
import collections, csv, math

P = 'data/processed'
B_YEARS = {'2024', '2025', '2026'}


def g2(a, b, na, nb):
    e1 = na * (a + b) / (na + nb); e2 = nb * (a + b) / (na + nb)
    return 2 * sum(o * math.log(o / e) for o, e in ((a, e1), (b, e2)) if o > 0)


def main():
    E = {r['headword']: r for r in csv.DictReader(open(f'{P}/entries_with_defs.csv', encoding='utf-8-sig'))}
    cnt = {'A': collections.Counter(), 'B': collections.Counter()}
    yrs = collections.defaultdict(set); yrsA = collections.defaultdict(set)
    passages = collections.defaultdict(set)
    sec = {'A': collections.Counter(), 'B': collections.Counter()}
    for r in csv.DictReader(open('data/interim/occurrences.tsv', encoding='utf-8'), delimiter='\t'):
        per = 'B' if r['year'] in B_YEARS else 'A'
        w = r['headword']
        sec[per][r['section']] += 1
        # compare like with like: question stems and options are captured unevenly across papers (many listening
        # sections have none), and single choice / error correction no longer exist in B -> texts only
        if r['kind'] in ('question', 'option') or r['section'] in ('single_choice', 'correction'):
            continue
        cnt[per][w] += 1
        (yrs if per == 'B' else yrsA)[w].add(r['year'])
        if per == 'B':
            passages[w].add((r['paper_id'], r['section']))
    na, nb = sum(cnt['A'].values()), sum(cnt['B'].values())
    rows = []
    for w in set(cnt['A']) | set(cnt['B']):
        a, b = cnt['A'][w], cnt['B'][w]
        ra, rb = a / na * 1e4, b / nb * 1e4
        g = g2(a, b, na, nb)
        ratio = (rb + 0.5) / (ra + 0.5)
        d = ''
        if g >= 6.63 and ratio >= 2 and len(yrs[w]) >= 2:
            d = 'up'
        elif g >= 6.63 and ratio <= 0.5 and len(yrsA[w]) >= 5:
            d = 'down'
        e = E.get(w, {})
        rows.append({'headword': w, 'rank': e.get('rank', ''), 'level': e.get('level', ''), 'count_A': a, 'rate_A': round(ra, 1),
                     'count_B': b, 'rate_B': round(rb, 1), 'years_B': len(yrs[w]), 'passages_B': len(passages[w]),
                     'ratio': round(ratio, 2), 'G2': round(g, 1), 'direction': d,
                     'new_in_B': a == 0 and b > 0})
    rows.sort(key=lambda r: (r['direction'] != 'up', r['direction'] != 'down', -r['G2']))
    with open(f'{P}/trend_words.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    sa_tot, sb_tot = sum(sec['A'].values()), sum(sec['B'].values())
    with open(f'{P}/trend_sections.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['section', 'share_A', 'share_B'])
        for s in sorted(set(sec['A']) | set(sec['B']), key=lambda s: -sec['A'][s]):
            w.writerow([s, round(sec['A'][s] / sa_tot, 3), round(sec['B'][s] / sb_tot, 3)])
    # hold-out: rank by A only (years present, then count), measure coverage of B
    rankA = sorted(cnt['A'], key=lambda w: (-len(yrsA[w]), -cnt['A'][w]))
    rankAll = sorted(E, key=lambda w: int(E[w]['rank']))
    hold = []
    for n in (200, 500, 1000, 1600, 2000):
        sa = set(rankA[:n]); sl = set(rankAll[:n])
        hold.append({'top_n': n, 'coverage_of_B_ranked_with_A_only': round(sum(cnt['B'][w] for w in sa) / nb, 4),
                     'coverage_of_B_ranked_with_all_years': round(sum(cnt['B'][w] for w in sl) / nb, 4),
                     'coverage_of_A_ranked_with_A': round(sum(cnt['A'][w] for w in sa) / na, 4)})
    with open(f'{P}/trend_holdout.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(hold[0].keys())); w.writeheader(); w.writerows(hold)
    up = [r for r in rows if r['direction'] == 'up']; down = [r for r in rows if r['direction'] == 'down']
    print(f'word hits A {na:,} / B {nb:,}; rising {len(up)}, falling {len(down)}; words new in B: {sum(r["new_in_B"] for r in rows)} '
          f'({sum(r["count_B"] for r in rows if r["new_in_B"]) / nb:.1%} of B hits)')
    print('UP  :', ', '.join(f"{r['headword']}({r['count_A']}→{r['count_B']},{r['years_B']}y)" for r in up[:45]))
    print('DOWN:', ', '.join(f"{r['headword']}({r['count_A']}→{r['count_B']})" for r in down[:30]))
    print('sections:', [(s, round(sec['A'][s] / sa_tot, 3), round(sec['B'][s] / sb_tot, 3)) for s in sec['A']])
    print('hold-out:', hold)


if __name__ == '__main__':
    main()
