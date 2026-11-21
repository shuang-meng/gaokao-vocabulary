# -*- coding: utf-8 -*-
"""Step 8d: a second, independent model pass over the uncertain labels, and a class for every phrase not yet reviewed.

Why: the first pass (step 8, Sonnet) agrees 99% with hand labels when it says "h", but only ~68% when it says "m".
Instead of you reading all medium / low rows, a different model (Opus 5.5) labels them again WITHOUT seeing the
first answer. Rows where both passes agree are accepted; only the disagreements are left for you.

Two tasks in one batch:
  relabel  — every row of data/interim/review_queue.csv (written by step 8c)
  phrases  — every phrase in data/processed/phrase_entries.csv whose class is still 'unreviewed'
             -> idiom / functional / collocation / drop

Commands:
  python scripts/08d_second_pass.py preview    # prompts + rough cost, no API call
  python scripts/08d_second_pass.py test       # one normal call per task, checks the settings
  python scripts/08d_second_pass.py submit
  python scripts/08d_second_pass.py status
  python scripts/08d_second_pass.py collect    # download; then compare runs automatically
  python scripts/08d_second_pass.py compare    # write the disagreement list again

Outputs:
  data/interim/second_pass/relabel.json             second-pass labels (exam sentences: not in git)
  data/interim/second_pass/disagreements.csv        rows where the two passes differ — fill in your_sense / your_phrase
  data/manual/phrase_classes_model.csv              model classes for the long-tail phrases (no sentences)
Step 8c reads your_sense / your_phrase from disagreements.csv, accepted.csv and data/manual/phrase_classes_model.csv.
"""
import argparse, collections, csv, glob, importlib.util, json, os, sys, time

spec = importlib.util.spec_from_file_location('s08', os.path.join(os.path.dirname(__file__), '08_annotate_senses.py'))
s08 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s08)

MODEL = 'claude-opus-5-5'
EXTRA = {'output_config': {'effort': 'high'}}   # Opus 5.5 does not accept thinking=between_tools; default thinking
HEADROOM = 3000                                  # extra max_tokens so thinking cannot cut the answer short
PRICE = (4, 20)            # $ per MTok in / out (batch is half)
OUT = 'data/interim/second_pass'      # round 2 and later: --round N -> data/interim/second_pass_rN
PHRASES_PER_CALL = 40

PHRASE_SYSTEM = """You sort English multi-word expressions found in Chinese gaokao exam texts into four classes.
- idiom: the meaning cannot be worked out from the parts (phrasal verbs like give up, pick up, turn out;
  idioms like by the way, come clean, take ... by storm; fixed expressions like in fact, at least)
- functional: grammar or discourse chunks — modal and tense forms (have to, used to, had better, be going to),
  complex conjunctions and prepositions (so that, as long as, instead of, in front of), quantifiers
  (a few, a lot of, a number of), discourse formulas (you know, excuse me, let me see)
- collocation: the meaning follows from the parts (look at, high school, make a decision, heart attack,
  around the world, take photos) — these are not phrases for a learner
- drop: not a real expression (a fragment, a wrong split, a name)
Answer with one line per item and nothing else:  id|class
Example:
1|idiom
2|collocation"""


def inventory():
    nmap = {}
    if os.path.exists('data/manual/new_sense_map.csv'):
        for r in csv.DictReader(open('data/manual/new_sense_map.csv', encoding='utf-8-sig')):
            if r['action'] == 'A':
                nmap.setdefault(r['word'], {})[r['target']] = r['name']
    inv = s08.load_inventory('data/processed/senses.csv', 'data/pilot/full/labels.json')
    for p in glob.glob('data/interim/annotations/*.json'):
        w = os.path.basename(p)[:-5]
        if not w.startswith('batch_') and w not in inv:
            inv[w] = [tuple(x) for x in json.load(open(p, encoding='utf-8'))['senses']]
    for w, add in nmap.items():
        have = {no for no, _ in inv[w]}
        inv[w] = inv[w] + [(k, v) for k, v in sorted(add.items()) if k not in have]
    return inv


def queue():
    rows = list(csv.DictReader(open('data/interim/review_queue.csv', encoding='utf-8-sig')))
    for r in rows:
        r['nth'] = int(r['occ_id'].split('|')[-1])
    return rows


def unreviewed_phrases():
    P = [p for p in csv.DictReader(open('data/processed/phrase_entries.csv', encoding='utf-8-sig')) if p['class'] == 'unreviewed']
    ex = collections.defaultdict(list)
    for r in csv.DictReader(open('data/interim/sense_occurrences.csv', encoding='utf-8-sig')):
        if r['phrase'] and len(ex[r['phrase']]) < 2:
            ex[r['phrase']].append(' '.join(r['sentence'].split()[:40]))
    return [(p['phrase'], ex[p['phrase']]) for p in P]


def build_requests():
    inv = inventory()
    reqs, index = [], {}
    byw = collections.defaultdict(list)
    for r in queue():
        byw[r['word']].append(r)
    for wi, (w, rs) in enumerate(sorted(byw.items())):
        for k in range(0, len(rs), s08.PER_CALL):
            chunk = rs[k:k + s08.PER_CALL]
            cid = f'r{wi:04d}-{k // s08.PER_CALL:02d}'
            index[cid] = {'task': 'relabel', 'word': w, 'occ_ids': [r['occ_id'] for r in chunk]}
            reqs.append({'custom_id': cid, 'params': dict(model=MODEL, max_tokens=25 * len(chunk) + HEADROOM, system=s08.SYSTEM,
                         messages=[{'role': 'user', 'content': s08.build_prompt(w, inv[w], chunk)}], **EXTRA)})
    ph = unreviewed_phrases()
    for k in range(0, len(ph), PHRASES_PER_CALL):
        chunk = ph[k:k + PHRASES_PER_CALL]
        cid = f'p{k // PHRASES_PER_CALL:03d}'
        index[cid] = {'task': 'phrases', 'phrases': [p for p, _ in chunk]}
        lines = [f'{i}. {p}   e.g. ' + ' / '.join(e) for i, (p, e) in enumerate(chunk, 1)]
        reqs.append({'custom_id': cid, 'params': dict(model=MODEL, max_tokens=12 * len(chunk) + HEADROOM, system=PHRASE_SYSTEM,
                     messages=[{'role': 'user', 'content': '\n'.join(lines)}], **EXTRA)})
    return reqs, index


def calib_rows():
    """Pilot occurrences (hand-labelled) where the first pass said m or l: the same kind of rows as the queue."""
    names = json.load(open('data/pilot/full/labels.json'))['names']
    rows = []
    for w in sorted(names):
        for l in json.load(open(os.path.join(s08.OUT, w + '.json'), encoding='utf-8'))['labels']:
            if (l.get('confidence') or 'h')[:1] in ('m', 'l'):
                rows.append({**l, 'nth': int(l['occ_id'].split('|')[-1])})
    return rows


def build_calib():
    inv = s08.load_inventory('data/processed/senses.csv', 'data/pilot/full/labels.json')
    reqs, index = [], {}
    byw = collections.defaultdict(list)
    for r in calib_rows():
        byw[r['word']].append(r)
    for wi, (w, rs) in enumerate(sorted(byw.items())):
        cid = f'c{wi:04d}'
        index[cid] = {'task': 'calib', 'word': w, 'occ_ids': [r['occ_id'] for r in rs]}
        reqs.append({'custom_id': cid, 'params': dict(model=MODEL, max_tokens=25 * len(rs) + HEADROOM, system=s08.SYSTEM,
                     messages=[{'role': 'user', 'content': s08.build_prompt(w, inv[w], rs)}], **EXTRA)})
    return reqs, index


def calib_report():
    import re
    norm = lambda x: re.sub(r'[^a-z]', '', x.lower())
    lab = json.load(open(os.path.join(OUT, 'calib.json'), encoding='utf-8'))
    hand = collections.defaultdict(list)
    for r in csv.DictReader(open('data/pilot/full/occ_units.csv', encoding='utf-8-sig')):
        hand[(r['paper'], r['word'], norm(r['sentence']))].append(r)
    t = collections.Counter()
    for r in calib_rows():
        b = lab.get(r['occ_id']); h = hand.get((r['paper'], r['word'], norm(r['sentence'])))
        if not b or not h:
            continue
        hs = h.pop(0)['sense']; hs = 'SKIP' if hs == 'X' else hs.lstrip('+')
        s1, s2 = r['sense'], b['sense']
        if s1 == s2:
            t['agree'] += 1; t['agree_right'] += s1 == hs
        else:
            k = 'dis_' + b['confidence']
            t[k] += 1; t[k + '_p1right'] += s1 == hs; t[k + '_p2right'] += s2 == hs
    print(f"calibration on {sum(v for k, v in t.items() if k in ('agree', 'dis_h', 'dis_m', 'dis_l'))} hand-labelled rows "
          f"(first pass m / l):")
    if t['agree']:
        print(f"  both passes agree: {t['agree']} rows, {t['agree_right'] / t['agree']:.0%} match the hand label")
    for c in 'hml':
        n = t['dis_' + c]
        if n:
            print(f"  disagree, second pass '{c}': {n} rows — first pass right {t[f'dis_{c}_p1right'] / n:.0%}, "
                  f"second pass right {t[f'dis_{c}_p2right'] / n:.0%}")


def parse_classes(text, n):
    out = {}
    for line in text.strip().splitlines():
        a = [x.strip().lower() for x in line.split('|')]
        if len(a) >= 2 and a[0].isdigit() and a[1] in ('idiom', 'functional', 'collocation', 'drop'):
            out[int(a[0])] = a[1]
    if len(out) < n:
        raise ValueError(f'{n - len(out)} class lines missing')
    return out


def compare(force=False):
    if os.path.exists(os.path.join(OUT, 'disagreements.csv')) and not force:
        return print(f'{OUT}/disagreements.csv exists (it may hold your verdicts); use compare --force to rebuild it')
    lab = json.load(open(os.path.join(OUT, 'relabel.json'), encoding='utf-8'))
    Q = queue()                                     # keep the queue as it was: 8c shrinks it once rows are settled
    with open(os.path.join(OUT, 'queue_snapshot.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(Q[0].keys())); w.writeheader(); w.writerows(Q)
    pclass = {}
    for f in ('data/manual/phrase_classes_model.csv', 'data/manual/phrase_classes.csv'):
        if os.path.exists(f):
            pclass.update({r['phrase']: r['class'] for r in csv.DictReader(open(f, encoding='utf-8-sig'))})
    strict = lambda p: bool(p) and pclass.get(s08_norm(p), 'idiom') in ('idiom', 'functional')
    agree, dis = 0, []
    for r in queue():
        b = lab.get(r['occ_id'])
        if not b:
            continue
        s1 = 'PHRASE' if r['sense'] == 'PHRASE' else r['sense']
        s2 = 'NEW' if b['sense'] == 'NEW' else b['sense']
        p1, p2 = r['phrase'] or '', b['phrase'] or ''
        same_sense = s1 == s2 or (s1 == 'PHRASE' and p2)
        same_phrase = strict(p1) == strict(p2) and (not strict(p1) or s08_norm(p1) == s08_norm(p2))
        if same_sense and same_phrase:
            agree += 1; continue
        dis.append({'occ_id': r['occ_id'], 'word': r['word'], 'section': r['section'],
                    'pass1': f"{r['sense']} {r['sense_name']}".strip() + (f" [{p1}]" if p1 else ''),
                    'pass2': (f"NEW:{b.get('new_sense_zh') or ''}" if s2 == 'NEW' else s2) + (f" [{p2}]" if p2 else '') + f" ({b['confidence']})",
                    'sentence': r['sentence'], 'your_sense': '', 'your_phrase': ''})
    with open(os.path.join(OUT, 'disagreements.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(dis[0].keys()) if dis else ['occ_id']); w.writeheader(); w.writerows(dis)
    ap_ = os.path.join(OUT, 'accepted.csv')          # keep earlier acceptances: after 8c re-runs they leave the queue
    old = {r['occ_id']: r for r in csv.DictReader(open(ap_, encoding='utf-8-sig'))} if os.path.exists(ap_) else {}
    new = {r['occ_id']: {'occ_id': r['occ_id'], 'sense': r['sense'], 'phrase': r['phrase']} for r in queue()
           if r['occ_id'] in lab and r['occ_id'] not in {d['occ_id'] for d in dis}}
    accepted = list({**old, **new}.values())
    with open(os.path.join(OUT, 'accepted.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['occ_id', 'sense', 'phrase']); w.writeheader(); w.writerows(accepted)
    print(f'second pass: {agree} rows agree (accepted), {len(dis)} disagree -> {OUT}/disagreements.csv')
    print(collections.Counter(d['word'] for d in dis).most_common(15))


def resolve(force=False, accept_m=False):
    """Settle the disagreements with the rules the calibration supports (135 hand-labelled pilot rows, first pass m/l):
       both agree -> 96% right (accepted already) | second pass h -> right 31/31, first pass 0/31 -> take the second pass
       second pass m -> 54% vs 38%: a coin flip -> left for you | second pass l -> first pass right 2/2 -> keep the first.
       Rows where only the phrase differs keep the first-pass phrase unless the second pass is h.
       NEW senses of the second pass are consolidated through data/manual/new_sense_map.csv (step 8c)."""
    tr = os.path.join(OUT, 'to_review.csv')
    if os.path.exists(tr) and not force:
        return print(f'{tr} exists (it may hold your verdicts); use resolve --force to rebuild it')
    import re
    lab = json.load(open(os.path.join(OUT, 'relabel.json'), encoding='utf-8'))
    inv = {w: dict(v) for w, v in inventory().items()}
    D = list(csv.DictReader(open(os.path.join(OUT, 'disagreements.csv'), encoding='utf-8-sig')))
    q = {r['occ_id']: r for r in csv.DictReader(open(os.path.join(OUT, 'queue_snapshot.csv'), encoding='utf-8-sig'))} \
        if os.path.exists(os.path.join(OUT, 'queue_snapshot.csv')) else {r['occ_id']: r for r in queue()}
    res, mine, rules = [], [], collections.Counter()
    for d in D:
        if d['occ_id'] not in q:                     # dropped by 8c since (e.g. its phrase became a collocation)
            continue
        r, b = q[d['occ_id']], lab[d['occ_id']]
        s1, p1 = r['sense'], r['phrase'] or ''
        s2, p2, c2 = b['sense'], b['phrase'] or '', b['confidence']
        same_sense = s1 == s2 or (s1 == 'PHRASE' and p2)
        if c2 == 'h':
            rule = 'second_h'; out = (s2, b.get('new_sense_zh') or '', p2)
        elif c2 == 'l':
            rule = 'first_l'; out = (s1, '', p1)
        elif same_sense:
            rule = 'phrase_only_first'; out = (s1, '', p1)
        elif accept_m:
            rule = 'second_m'; out = (s2, b.get('new_sense_zh') or '', p2)
        elif s2 == 'NEW':
            rule = 'second_m_new'; out = (s2, b.get('new_sense_zh') or '', p2)   # consolidated via new_sense_map
        else:
            name = lambda x: inv.get(r['word'], {}).get(x, x).split(' — ')[0]
            mine.append({'occ_id': d['occ_id'], 'word': r['word'], 'section': r['section'],
                         'pass1': f'{s1} {name(s1)}' + (f' [{p1}]' if p1 else ''),
                         'pass2': f'{s2} {name(s2)}' + (f' [{p2}]' if p2 else ''),
                         'sentence': r['sentence'], 'your_sense': '', 'your_phrase': '',
                         'all_senses': ' | '.join(f"{k} {v.split(' — ')[0]}" for k, v in inv.get(r['word'], {}).items())})
            rules['for_you'] += 1; continue
        rules[rule] += 1
        res.append({'occ_id': d['occ_id'], 'sense': out[0], 'new_sense_zh': out[1], 'phrase': out[2], 'rule': rule})
    with open(os.path.join(OUT, 'resolved.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['occ_id', 'sense', 'new_sense_zh', 'phrase', 'rule']); w.writeheader(); w.writerows(res)
    mine.sort(key=lambda t: (t['word'], t['occ_id']))
    if mine:
        with open(tr, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(mine[0].keys())); w.writeheader(); w.writerows(mine)
    print(dict(rules)); print(f'{len(mine)} rows for you -> {tr}')


def s08_norm(p):
    return ' '.join((p or '').lower().split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['preview', 'test', 'submit', 'status', 'collect', 'compare', 'errors', 'calibrate', 'calib-report', 'resolve'])
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--round', type=int, default=1)
    ap.add_argument('--accept-second-m', action='store_true',
                    help="resolve: also take the second pass when it says m (round 1: you agreed with it in 112 of 145 rows)")
    a = ap.parse_args()
    global OUT
    if a.round > 1:
        OUT = f'data/interim/second_pass_r{a.round}'
    os.makedirs(OUT, exist_ok=True)
    if a.command == 'compare':
        return compare(a.force)
    if a.command == 'resolve':
        return resolve(a.force, a.accept_second_m)
    if a.command == 'calib-report':
        return calib_report()
    if a.command == 'calibrate':                    # small batch: Opus on the hand-labelled pilot rows
        reqs, index = build_calib()
        print(f"{sum(len(v['occ_ids']) for v in index.values())} pilot rows in {len(reqs)} requests (≈ $0.2)")
        b = s08.client().messages.batches.create(requests=reqs)
        json.dump({'batch_id': b.id, 'created': time.strftime('%Y-%m-%d %H:%M'), 'index': index, 'state': 'submitted'},
                  open(os.path.join(OUT, f'batch_{b.id}.json'), 'w'), ensure_ascii=False)
        print(f'submitted batch {b.id}. Then: status, collect')
        return
    if a.command in ('preview', 'test', 'submit'):
        reqs, index = build_requests()
        chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content']) for r in reqs)
        n_rel = sum(len(v['occ_ids']) for v in index.values() if v['task'] == 'relabel')
        n_ph = sum(len(v['phrases']) for v in index.values() if v['task'] == 'phrases')
        est_in, est_out = chars / 3.2, n_rel * 12 + n_ph * 6
        print(f'{n_rel} rows to relabel, {n_ph} phrases to classify, {len(reqs)} requests')
        print(f'rough estimate ≈ ${(est_in * PRICE[0] + est_out * PRICE[1]) / 1e6 / 2:.2f} with the batch discount ({MODEL})')
        if a.command == 'preview':
            for t in ('r', 'p'):
                r = next((x for x in reqs if x['custom_id'].startswith(t)), None)
                if r:
                    print(f"\n===== {r['custom_id']} USER =====\n" + r['params']['messages'][0]['content'][:1500])
            return
        if a.command == 'test':                      # one normal call of each task, to check before a batch
            for t in ('r', 'p'):
                r = next(x for x in reqs if x['custom_id'].startswith(t))
                msg = s08.client().messages.create(**r['params'])
                text = ''.join(x.text for x in msg.content if getattr(x, 'type', '') == 'text')
                info = index[r['custom_id']]
                n = len(info.get('occ_ids') or info.get('phrases'))
                ok = (s08.parse if t == 'r' else parse_classes)(text, n)
                print(f"\n===== {r['custom_id']} ANSWER =====\n{text}\nparsed {len(ok)} of {n}; "
                      f"tokens {msg.usage.input_tokens} in / {msg.usage.output_tokens} out; stop: {msg.stop_reason}")
            return
        b = s08.client().messages.batches.create(requests=reqs)
        json.dump({'batch_id': b.id, 'created': time.strftime('%Y-%m-%d %H:%M'), 'index': index, 'state': 'submitted'},
                  open(os.path.join(OUT, f'batch_{b.id}.json'), 'w'), ensure_ascii=False)
        print(f'submitted batch {b.id}. Check with: python scripts/08d_second_pass.py status')
        return
    states = sorted(glob.glob(os.path.join(OUT, 'batch_*.json')))
    if not states:
        print('no batch yet'); return
    c = s08.client()
    if a.command == 'errors':                       # show why requests failed
        s = json.load(open(states[-1]))
        seen = collections.Counter()
        for res in c.messages.batches.results(s['batch_id']):
            if res.result.type != 'succeeded':
                msg = str(getattr(res.result, 'error', res.result))
                if seen[msg] == 0:
                    print(res.custom_id, res.result.type, msg[:600])
                seen[msg] += 1
        print({k[:80]: v for k, v in seen.items()})
        return
    for p in states:
        s = json.load(open(p))
        b = c.messages.batches.retrieve(s['batch_id']); rc = b.request_counts
        if a.command == 'status' or s['state'] == 'collected':
            print(f"{s['batch_id']} ({s['state']}): {b.processing_status} — succeeded {rc.succeeded}, processing {rc.processing}, errored {rc.errored}")
            continue
        if b.processing_status != 'ended':
            print('still', b.processing_status); continue
        rp = os.path.join(OUT, 'relabel.json')
        lab = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
        cp = os.path.join(OUT, 'calib.json')
        cal = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else {}
        cls = {}; usage = [0, 0]; bad = []
        for res in c.messages.batches.results(s['batch_id']):
            info = s['index'][res.custom_id]
            if res.result.type != 'succeeded':
                bad.append(res.custom_id); continue
            msg = res.result.message; usage[0] += msg.usage.input_tokens; usage[1] += msg.usage.output_tokens
            text = ''.join(x.text for x in msg.content if getattr(x, 'type', '') == 'text')
            try:
                if info['task'] in ('relabel', 'calib'):
                    out = s08.parse(text, len(info['occ_ids']))
                    for i, oid in enumerate(info['occ_ids'], 1):
                        (lab if info['task'] == 'relabel' else cal)[oid] = out[i]
                else:
                    out = parse_classes(text, len(info['phrases']))
                    for i, ph in enumerate(info['phrases'], 1):
                        cls[ph] = out[i]
            except ValueError as e:
                bad.append(res.custom_id); print(' ', res.custom_id, e, file=sys.stderr)
        json.dump(lab, open(rp, 'w', encoding='utf-8'), ensure_ascii=False)
        if cal:
            json.dump(cal, open(cp, 'w', encoding='utf-8'), ensure_ascii=False)
        if cls:
            f = 'data/manual/phrase_classes_model.csv'
            old = {r['phrase']: r['class'] for r in csv.DictReader(open(f, encoding='utf-8-sig'))} if os.path.exists(f) else {}
            old.update(cls)
            with open(f, 'w', encoding='utf-8-sig', newline='') as fh:
                w = csv.writer(fh); w.writerow(['phrase', 'class']); w.writerows(sorted(old.items()))
        s['state'] = 'collected'; s['usage'] = usage
        json.dump(s, open(p, 'w'), ensure_ascii=False)
        print(f"collected: {len(lab)} relabels, {len(cls)} phrase classes; tokens {usage[0]:,} in / {usage[1]:,} out "
              f"≈ ${(usage[0] * PRICE[0] + usage[1] * PRICE[1]) / 1e6 / 2:.2f}" + (f"; failed: {bad}" if bad else ''))
        if any(v['task'] == 'calib' for v in s['index'].values()):
            calib_report()
        else:
            compare()


if __name__ == '__main__':
    main()
