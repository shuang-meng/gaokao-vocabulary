# -*- coding: utf-8 -*-
"""Step 8b: compare the API labels with the hand labels of the 30 pilot words.

usage: python scripts/08b_evaluate.py data/interim/annotations data/pilot/full/occ_units.csv data/pilot/full/labels.json data/pilot/full/
Prints agreement and Cohen's kappa (overall and per word), agreement by confidence level and phrase
agreement, and writes review_disagreements.csv (contains exam sentences; not in git) for you to judge.
"""
import collections, csv, json, os, re, sys

norm = lambda s: re.sub(r'[^a-z]', '', s.lower())


def kappa(pairs):
    n = len(pairs)
    if n == 0:
        return float('nan')
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs); cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main(ann_dir, units_csv, labels_json, outdir):
    names = json.load(open(labels_json))['names']
    hand = collections.defaultdict(list)
    for r in csv.DictReader(open(units_csv, encoding='utf-8-sig')):
        hand[(r['paper'], r['word'], norm(r['sentence']))].append(r)
    pairs, rows, by_word, by_conf = [], [], collections.defaultdict(list), collections.defaultdict(list)
    ph_pairs = []
    for w in names:
        p = os.path.join(ann_dir, w + '.json')
        if not os.path.exists(p):
            continue
        for lab in json.load(open(p, encoding='utf-8'))['labels']:
            k = (lab['paper'], w, norm(lab['sentence']))
            if not hand.get(k):
                continue
            h = hand[k].pop(0)
            hs = 'SKIP' if h['sense'] == 'X' else h['sense']
            api = lab['sense']
            pairs.append((f'{w}:{hs}', f'{w}:{api}'))
            by_word[w].append((hs, api))
            by_conf[lab['confidence']].append(hs == api)
            hp = h.get('unit') if h.get('unit_kind') not in ('', '单词义项', None) and h.get('unit_kind') != '复合词' else None
            ap_ = (lab.get('phrase') or None)
            ph_pairs.append((bool(hp), bool(ap_)))
            if hs != api:
                rows.append({'word': w, 'year': lab['year'], 'section': lab['section'],
                             'hand': f"{hs} {names[w].get(hs, '')}", 'api': f"{api} {names[w].get(api, lab.get('new_sense_zh') or '')}",
                             'api_confidence': lab['confidence'], 'sentence': lab['sentence'], 'your_verdict': ''})
    n = len(pairs)
    if not n:
        sys.exit('no overlapping labels found; run 08_annotate_senses.py --pilot first')
    agree = sum(a == b for a, b in pairs) / n
    print(f'{n} occurrences compared: agreement {agree:.1%}, Cohen\'s kappa {kappa(pairs):.3f}')
    print('by API confidence:', {c: f'{sum(v) / len(v):.0%} of {len(v)}' for c, v in by_conf.items()})
    tp = sum(a and b for a, b in ph_pairs); fp = sum(b and not a for a, b in ph_pairs); fn = sum(a and not b for a, b in ph_pairs)
    print(f'phrases (strict, compounds excluded): both {tp}, API only {fp}, hand only {fn}')
    print('lowest agreement words:')
    for w, v in sorted(by_word.items(), key=lambda x: sum(a == b for a, b in x[1]) / len(x[1]))[:10]:
        print(f'  {w}: {sum(a == b for a, b in v) / len(v):.0%} of {len(v)}, kappa {kappa(v):.2f}')
    with open(os.path.join(outdir, 'review_disagreements.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ['word']); wr.writeheader(); wr.writerows(rows)
    print(f'{len(rows)} disagreements written to {outdir}/review_disagreements.csv')


if __name__ == '__main__':
    main(*sys.argv[1:5])
