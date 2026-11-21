# -*- coding: utf-8 -*-
"""Step 8c: turn the sense labels into sense frequencies, phrase entries and word metrics.

usage: python scripts/08c_aggregate.py
Inputs : data/interim/annotations/*.json        (API labels, step 8)
         data/pilot/full/occ_units.csv           (hand labels of the 30 pilot words; they override the API)
         data/pilot/full/labels.json             (sense names of the pilot words)
         data/processed/entries_with_defs.csv    (word ranking)
         data/manual/phrase_aliases.csv          (optional: alias,canonical  — merge spellings of one phrase)
         data/manual/new_sense_map.csv           (optional: what each NEW sense of the model becomes —
                                                  S existing sense / A added sense / P phrase / X drop)
         data/manual/sense_merges.csv            (optional: word,from,to,name — senses merged because a learner
                                                  cannot tell them apart; applied last, to every label)
         data/manual/phrase_classes.csv          (optional: phrase,class — idiom / functional / collocation / drop;
                                                  collocation and drop go back to the word sense)
Outputs (no exam sentences, can go to git):
         data/processed/sense_freq.csv       one row per word sense: count, years, passages, listening share ...
         data/processed/phrase_entries.csv   one row per phrase (strict standard), with the rank it would have as a word
         data/processed/word_sense_metrics.csv  per word: senses used, top-sense share, phrase share, passages
Outputs with exam sentences (data/interim, not in git):
         data/interim/sense_occurrences.csv  every labelled occurrence
         data/interim/review_queue.csv       NEW senses and medium / low confidence labels, for checking
"""
import collections, csv, glob, json, os, re

A = 'data/interim/annotations'
# hand phrase rules of the pilot that do not meet the strict standard (meaning follows from the parts)
NOT_STRICT = {'draw attention to', 'on top of / at the top', 'the key to', 'carry weight', 'run a red light',
              'at this / some point', 'be faced with', 'run away', "break sb.'s heart", 'pass by'}
# 'kind of' is a phrase only as the hedge 有点儿 ("it's kind of hard"), not after a determiner ("what kind of")
DET = r"(?:a|an|the|this|that|these|those|what|which|any|all|every|each|some|no|one|two|three|many|several|different|new|other|same|another|\d+|hundred|what's|whatever)"
HEDGE = lambda s: bool(re.search(r"\bkind of\b", s, re.I)) and not re.search(r"\b" + DET + r"\s+(?:\w+\s+)?kinds?\s+of\b", s, re.I)
norm = lambda s: re.sub(r'[^a-z]', '', s.lower())


def clean_phrase(p, alias):
    if not p:
        return None
    p = re.sub(r'\s+', ' ', p.strip().lower().strip('.,;:"“”')).replace('somebody', 'sb.').replace('something', 'sth.')
    return alias.get(p, p) or None


def main():
    alias = {}
    if os.path.exists('data/manual/phrase_aliases.csv'):
        alias = {r['alias'].strip().lower(): r['canonical'].strip().lower()
                 for r in csv.DictReader(open('data/manual/phrase_aliases.csv', encoding='utf-8-sig'))}
    nmap = {}
    if os.path.exists('data/manual/new_sense_map.csv'):
        nmap = {(r['word'], r['new_name']): r for r in csv.DictReader(open('data/manual/new_sense_map.csv', encoding='utf-8-sig'))}
    pclass = {}                                    # model classes (step 8d) first, your own classes win
    for f in ('data/manual/phrase_classes_model.csv', 'data/manual/phrase_classes.csv'):
        if os.path.exists(f):
            pclass.update({r['phrase'].strip().lower(): r['class'].strip() for r in csv.DictReader(open(f, encoding='utf-8-sig'))})
    merge, merge_name = {}, {}
    if os.path.exists('data/manual/sense_merges.csv'):
        for r in csv.DictReader(open('data/manual/sense_merges.csv', encoding='utf-8-sig')):
            merge[(r['word'], r['from'])] = r['to']
            if r['name']:
                merge_name[(r['word'], r['to'])] = r['name']
    mg = lambda w, s: merge.get((w, s), s)
    pair = {}             # second-pass rows left for you: if both answers merge into one sense, they agree
    verdict = {}          # your decisions on the second-pass disagreements: fill your_sense / your_phrase in the csv
    for tr in glob.glob('data/interim/second_pass*/to_review.csv'):
        for r in csv.DictReader(open(tr, encoding='utf-8-sig')):
            pair[r['occ_id']] = (r['pass1'].split(' ')[0], r['pass2'].split(' ')[0])
            if (r.get('your_sense') or '').strip() or (r.get('your_phrase') or '').strip():
                verdict[r['occ_id']] = {'sense': r['your_sense'], 'phrase': r['your_phrase']}
    for tf in glob.glob('data/interim/second_pass*/to_review_filled.csv'):  # exported from review.html (step 8e); wins
        for r in csv.DictReader(open(tf, encoding='utf-8-sig')):
            if (r.get('your_sense') or '').strip() or (r.get('your_phrase') or '').strip():
                verdict[r['occ_id']] = {'sense': r['your_sense'], 'phrase': r['your_phrase']}
    agreed = set()                                 # rows where the second model pass agreed with the first
    for f in glob.glob('data/interim/second_pass*/accepted.csv'):
        agreed |= {r['occ_id'] for r in csv.DictReader(open(f, encoding='utf-8-sig'))}
    resolved = {}                                  # disagreements settled by the calibrated rules of step 8d (resolve)
    for f in glob.glob('data/interim/second_pass*/resolved.csv'):
        resolved.update({r['occ_id']: r for r in csv.DictReader(open(f, encoding='utf-8-sig'))})
    added = collections.defaultdict(dict)
    for r in nmap.values():
        if r['action'] == 'A':
            added[r['word']][r['target']] = r['name']
    E = {r['headword']: r for r in csv.DictReader(open('data/processed/entries_with_defs.csv', encoding='utf-8-sig'))}
    pilot_names = json.load(open('data/pilot/full/labels.json'))['names']
    hand = collections.defaultdict(list)
    for r in csv.DictReader(open('data/pilot/full/occ_units.csv', encoding='utf-8-sig')):
        hand[(r['paper'], r['word'], norm(r['sentence']))].append(r)

    rows = []
    for p in sorted(glob.glob(os.path.join(A, '*.json'))):
        if os.path.basename(p).startswith('batch_'):
            continue
        d = json.load(open(p, encoding='utf-8'))
        w = d['word']
        names = {no: txt.split(' — ')[0] for no, txt in d['senses']}
        if w in pilot_names:
            names = dict(pilot_names[w])
        names.update(added.get(w, {}))
        names.update({k[1]: v for k, v in merge_name.items() if k[0] == w})
        for lab in d['labels']:
            src, sense, phrase, conf, new_zh = 'api', lab['sense'], lab.get('phrase'), (lab.get('confidence') or 'h')[:1], lab.get('new_sense_zh')
            if w in pilot_names:                                  # hand labels win for the pilot words
                h = hand.get((lab['paper'], w, norm(lab['sentence'])))
                if h:
                    h = h.pop(0)
                    src, conf, new_zh = 'hand', 'h', None
                    sense = 'SKIP' if h['sense'] == 'X' else h['sense']
                    phrase = h['unit'] if h.get('unit_kind') in ('短语动词', '习语') and h['unit'] not in NOT_STRICT else None
            if lab['occ_id'] in resolved and src == 'api':
                v = resolved[lab['occ_id']]
                sense, phrase, new_zh, conf = v['sense'], v['phrase'] or None, v['new_sense_zh'] or None, 'a'
            if sense == 'NEW' and (w, new_zh or '') in nmap:          # consolidate the model's new senses
                m = nmap[(w, new_zh or '')]
                if m['action'] == 'X':
                    continue
                if m['action'] == 'P':
                    sense, phrase = 'PHRASE', m['target']
                else:
                    sense, phrase, new_zh = m['target'], None, None
            if lab['occ_id'] in verdict:
                v = verdict[lab['occ_id']]
                sense, phrase, conf, src = v['sense'].strip(), (v.get('phrase') or '').strip() or None, 'h', 'hand'
                if sense.upper() in ('X', 'SKIP'):
                    continue
                if not sense and phrase:
                    sense = 'PHRASE'
                elif sense and sense not in names:                  # a gloss of your own instead of a number
                    sense, new_zh = 'NEW', sense.lstrip('+').strip()
            elif lab['occ_id'] in agreed:
                conf = 'a'                                          # two independent model passes agree
            if sense == 'SKIP':
                continue
            sense = mg(w, sense)
            if lab['occ_id'] in pair and lab['occ_id'] not in verdict and conf != 'a':
                a, b = pair[lab['occ_id']]
                if mg(w, a) == mg(w, b):
                    conf = 'a'                                      # the two passes differ only by merged senses
            if phrase and clean_phrase(phrase, alias) == 'kind of' and not HEDGE(lab['sentence']):
                phrase = None                                       # 'what kind of / all kinds of' = 种类, transparent
            if phrase and pclass.get(clean_phrase(phrase, alias)) in ('collocation', 'drop'):
                phrase = None                                       # transparent: back to the word sense
                if sense == 'PHRASE':
                    continue
            sid = sense if sense != 'NEW' else 'NEW:' + (new_zh or '?')
            rows.append({'occ_id': lab['occ_id'], 'word': w, 'year': lab['year'], 'paper': lab['paper'],
                         'section': lab['section'], 'sense': sid,
                         'sense_name': names.get(sense, new_zh or '') if sense != 'NEW' else (new_zh or ''),
                         'phrase': clean_phrase(phrase, alias), 'confidence': conf, 'source': src,
                         'surface': lab['surface'], 'sentence': lab['sentence']})
    if not rows:
        raise SystemExit('no annotations found')
    with open('data/interim/sense_occurrences.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys())); wr.writeheader(); wr.writerows(rows)
    review = [r for r in rows if r['source'] == 'api' and (r['sense'].startswith('NEW') or r['confidence'] in ('m', 'l'))]
    # after step 8d the queue is the input of the second pass; rows it agreed on (confidence 'a') leave the queue
    with open('data/interim/review_queue.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ['your_verdict']); wr.writeheader(); wr.writerows(review)

    unit = lambda r: (r['paper'], r['section'])
    # ---- sense frequencies (occurrences inside a phrase are counted under the phrase, not the word sense)
    by = collections.defaultdict(list)
    for r in rows:
        if not r['phrase']:
            by[(r['word'], r['sense'], r['sense_name'])].append(r)
    sf = []
    for (w, s, name), rs in by.items():
        lis = sum(r['section'] == 'listening' for r in rs)
        sf.append({'word': w, 'word_rank': E[w]['rank'], 'sense': s, 'sense_name': name, 'count': len(rs),
                   'years': len({r['year'] for r in rs}), 'passages': len({unit(r) for r in rs}),
                   'listening': lis, 'written': len(rs) - lis,
                   'first_year': min(r['year'] for r in rs), 'last_year': max(r['year'] for r in rs),
                   'new_sense': s.startswith('NEW') or s.startswith('a'), 'api_share': round(sum(r['source'] == 'api' for r in rs) / len(rs), 2)})
    sf.sort(key=lambda t: (int(t['word_rank']), -t['count']))
    with open('data/processed/sense_freq.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(sf[0].keys())); wr.writeheader(); wr.writerows(sf)

    # ---- phrase entries; one sentence counts once even if two head words carry the phrase
    ranking = sorted(((int(e['years_count']), int(e['total_count'])) for e in E.values()
                      if e['total_count'] and int(e['total_count']) > 0), reverse=True)
    eq_rank = lambda y, n: 1 + sum(1 for t in ranking if t > (y, n))
    ph = collections.defaultdict(dict)
    for r in rows:
        if r['phrase']:
            key = (r['paper'], r['section'], r['occ_id'].split('|')[2])
            ph[r['phrase']].setdefault(key, r)
    heads = collections.defaultdict(set)
    for r in rows:
        if r['phrase']:
            heads[r['phrase']].add(r['word'])
    pe = []
    for p, occs in ph.items():
        rs = list(occs.values()); y = len({r['year'] for r in rs}); n = len(rs)
        lis = sum(r['section'] == 'listening' for r in rs)
        pe.append({'phrase': p, 'class': pclass.get(p, 'unreviewed'), 'head_words': ' '.join(sorted(heads[p])), 'count': n, 'years': y,
                   'passages': len({unit(r) for r in rs}), 'listening': lis, 'equiv_rank': eq_rank(y, n),
                   'first_year': min(r['year'] for r in rs), 'last_year': max(r['year'] for r in rs)})
    pe.sort(key=lambda t: (-t['years'], -t['count']))
    with open('data/processed/phrase_entries.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(pe[0].keys())); wr.writeheader(); wr.writerows(pe)

    # ---- word metrics
    wm = []
    byw = collections.defaultdict(list)
    for r in rows:
        byw[r['word']].append(r)
    for w, rs in byw.items():
        c = collections.Counter(r['sense'] for r in rs if not r['phrase'])
        n = len(rs); nph = sum(1 for r in rs if r['phrase'])
        wm.append({'word': w, 'word_rank': E[w]['rank'], 'occurrences': n, 'senses_used': len(c),
                   'top_sense_share': round(max(c.values()) / n, 2) if c else 0,
                   'phrase_share': round(nph / n, 2), 'phrases': len({r['phrase'] for r in rs if r['phrase']}),
                   'passages': len({unit(r) for r in rs}),
                   'biggest_passage_share': round(max(collections.Counter(unit(r) for r in rs).values()) / n, 2),
                   'listening_share': round(sum(r['section'] == 'listening' for r in rs) / n, 2)})
    wm.sort(key=lambda t: int(t['word_rank']))
    with open('data/processed/word_sense_metrics.csv', 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(wm[0].keys())); wr.writeheader(); wr.writerows(wm)

    print(f'{len(byw)} words, {len(rows)} labelled occurrences ({sum(r["source"] == "hand" for r in rows)} by hand)')
    print(f'{len(sf)} word senses ({sum(t["new_sense"] for t in sf)} NEW), {len(pe)} phrase entries; '
          f'{sum(1 for r in rows if r["phrase"]) / len(rows):.1%} of occurrences are inside phrases')
    print('phrase classes:', dict(collections.Counter(t['class'] for t in pe)))
    print(f'review queue: {len(review)} rows -> data/interim/review_queue.csv')
    print('top phrases:', ', '.join(f"{t['phrase']} ({t['count']}/{t['years']}y, ≈#{t['equiv_rank']})" for t in pe[:15]))


if __name__ == '__main__':
    main()
