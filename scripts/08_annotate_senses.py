# -*- coding: utf-8 -*-
"""Step 8: label every exam occurrence of the polysemous words with a sense (Claude API, Batch).

The API key is read from the environment variable ANTHROPIC_API_KEY. Never write the key into a file.
Model: Claude Sonnet 5.5 through the Message Batches API (half price; results usually within an hour),
with up-front thinking turned off and a compact answer format, to keep the cost low.

Commands (add --pilot, --all or --words a,b,c to choose the words):
  python scripts/08_annotate_senses.py preview --words draw     # show the prompt + cost estimate, no API call
  python scripts/08_annotate_senses.py test    --words draw     # one normal (non-batch) call, to check the format
  python scripts/08_annotate_senses.py submit  --pilot          # send a batch
  python scripts/08_annotate_senses.py status                   # how far the batches are
  python scripts/08_annotate_senses.py collect                  # download finished batches, write the results
Finished words are skipped by submit, so a stopped or partly failed run is resumed by submitting again.

Output: data/interim/annotations/<word>.json (contains exam sentences; data/interim is not in git).
Each occurrence: sense (a number from the list, NEW or SKIP), new_sense_zh, phrase (strict standard) and
confidence (h / m / l).
"""
import argparse, collections, csv, glob, json, os, re, sys, time

MODEL = 'claude-sonnet-5-5'
EXTRA = {'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'medium'}}   # no up-front thinking
PER_CALL = 40
WINDOW = 30            # words kept on each side of the target word
OUT = 'data/interim/annotations'
SEC = {'listening': 'listening', 'reading': 'reading', 'cloze': 'cloze', 'grammar': 'grammar gap-fill',
       'seven': 'gap-fill passage', 'writing': 'writing task', 'single_choice': 'single-choice item',
       'correction': 'error-correction text'}

SYSTEM = """You annotate word senses in Chinese college entrance exam (gaokao) English texts.
In each numbered sentence the target word is marked like ⟦this⟧. Decide its sense.

Answer with one line per sentence and nothing else, in this format:
  id|sense|phrase|confidence
- sense: the number of the best sense in the list. If no listed sense fits: NEW:<short Chinese gloss>.
  SKIP only when the target word appears as a bare option in a list of several options with no sentence
  around it (e.g. "A. draw B. strike C. rush"), or when the text is too garbled to judge.
  A single answer option IS a normal sentence: "A. Catch a train." or "C. To protect the plants." must get
  a sense number like any other sentence.
- phrase: leave empty unless the target word is part of a multi-word expression whose meaning cannot be
  worked out from its parts (STRICT standard). Then give its base form, e.g. deal with, of course, set aside,
  in order to, get in touch, catch on, pass away, stand for, lead to, a big deal.
  NOT phrases: transparent compounds (power line, TV set, face-to-face), ordinary collocations
  (draw attention to, make a decision), literal verb + direction (run down the hill, carry it around, head home).
- confidence: h, m or l. You may leave it empty when it is h.
Examples:
1|2||
2|3|draw on|
3|NEW:卷入||m
4|SKIP||"""


# ---------------------------------------------------------------- data
def load_inventory(senses_csv, pilot_json):
    inv = collections.defaultdict(list)
    for r in csv.DictReader(open(senses_csv, encoding='utf-8-sig')):
        inv[r['headword']].append((r['sense_no'], f"{r['pos']} {r['zh']} — {r['en']}".strip()))
    if pilot_json and os.path.exists(pilot_json):
        names = json.load(open(pilot_json))['names']
        for w, d in names.items():
            en = {no: t.split(' — ', 1)[1] for no, t in inv.get(w, []) if ' — ' in t}
            inv[w] = [(k, v + (f" — {en[k]}" if k in en else '')) for k, v in sorted(d.items(), key=lambda x: int(x[0]))]
    return inv


def load_occurrences(occ_tsv, words):
    occ = collections.defaultdict(list)
    seen = collections.Counter()
    for r in csv.DictReader(open(occ_tsv, encoding='utf-8'), delimiter='\t'):
        w = r['headword']
        if w not in words:
            continue
        base = (r['paper_id'], r['section'], r['sent_id'], w)
        seen[base] += 1
        r['occ_id'] = '|'.join(base) + f'|{seen[base]}'
        r['nth'] = seen[base]
        occ[w].append(r)
    return occ


def mark(sentence, surface, nth):
    s = re.sub(r'\s+', ' ', sentence).strip()
    ms = list(re.finditer(r'\b' + re.escape(surface) + r'\b', s))
    if not ms:
        return ' '.join(s.split()[:2 * WINDOW]) + f'  [target: {surface}]'
    m = ms[min(nth, len(ms)) - 1]
    left = s[:m.start()].split()[-WINDOW:]
    right = s[m.end():].split()
    tail = right[:WINDOW]
    return ('… ' if len(s[:m.start()].split()) > WINDOW else '') + ' '.join(left) + (' ' if left else '') + \
        '⟦' + m.group(0) + '⟧' + s[m.end():m.end() + (1 if s[m.end():m.end() + 1] in ',.;:!?’”' else 0)] + \
        (' ' + ' '.join(tail) if tail else '') + (' …' if len(right) > WINDOW else '')


def build_prompt(word, senses, batch):
    lines = [f'Target word: {word}', 'Senses:'] + [f'  {no}. {txt}' for no, txt in senses] + ['', 'Sentences:']
    for i, r in enumerate(batch, 1):
        lines.append(f"{i}. ({r['year']} {SEC.get(r['section'], r['section'])}) {mark(r['sentence'], r['surface'], r['nth'])}")
    return '\n'.join(lines)


def parse(text, n):
    out = {}
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.strip().split('|')]
        if not parts or not parts[0].isdigit():
            continue
        i = int(parts[0]); parts += [''] * (4 - len(parts))
        sense, new_zh = parts[1], None
        if sense.upper().startswith('NEW'):
            new_zh = sense.split(':', 1)[1].strip() if ':' in sense else ''
            sense = 'NEW'
        elif sense.upper() == 'SKIP':
            sense = 'SKIP'
        out[i] = {'sense': sense, 'new_sense_zh': new_zh, 'phrase': parts[2] or None,
                  'confidence': (parts[3] or 'h').lower()[:1]}
    missing = [i for i in range(1, n + 1) if i not in out]
    if missing:
        raise ValueError(f'answer is missing lines {missing[:5]}')
    return out


def requests_for(words, inv, occ):
    reqs, index = [], {}
    for wi, w in enumerate(words):
        for k in range(0, len(occ[w]), PER_CALL):
            batch = occ[w][k:k + PER_CALL]
            cid = f'w{wi:04d}-c{k // PER_CALL:03d}'
            index[cid] = {'word': w, 'occ_ids': [r['occ_id'] for r in batch]}
            reqs.append({'custom_id': cid, 'params': dict(
                model=MODEL, max_tokens=25 * len(batch) + 300, system=SYSTEM,
                messages=[{'role': 'user', 'content': build_prompt(w, inv[w], batch)}], **EXTRA)})
    return reqs, index


def choose_words(a, inv):
    if a.words:
        return a.words.split(',')
    if a.pilot:
        return sorted(json.load(open(a.pilot_labels))['names'])
    if a.all:
        return sorted(w for w, s in inv.items() if len(s) >= 2)
    sys.exit('choose words with --pilot, --all or --words')


def write_word(word, senses, occs, labels_by_occ):
    rows = []
    for r in occs:
        lab = labels_by_occ[r['occ_id']]
        rows.append({'occ_id': r['occ_id'], 'word': word, 'year': r['year'], 'paper': r['paper_id'],
                     'section': r['section'], 'surface': r['surface'], 'sentence': r['sentence'], **lab})
    tmp = os.path.join(OUT, word + '.json.tmp')
    json.dump({'word': word, 'model': MODEL, 'senses': senses, 'labels': rows},
              open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    os.replace(tmp, os.path.join(OUT, word + '.json'))


def client():
    if not os.environ.get('ANTHROPIC_API_KEY'):
        sys.exit('ANTHROPIC_API_KEY is not set.')
    import anthropic
    return anthropic.Anthropic()


# ---------------------------------------------------------------- commands
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['preview', 'test', 'submit', 'status', 'collect'])
    ap.add_argument('--occ', default='data/interim/occurrences.tsv')
    ap.add_argument('--senses', default='data/processed/senses.csv')
    ap.add_argument('--pilot-labels', default='data/pilot/full/labels.json')
    ap.add_argument('--words'); ap.add_argument('--pilot', action='store_true'); ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    inv = load_inventory(a.senses, a.pilot_labels)

    if a.command in ('preview', 'test', 'submit'):
        words = choose_words(a, inv)
        occ = load_occurrences(a.occ, set(words))
        pending = set()                                     # words already in a batch that is not collected yet
        for p in glob.glob(os.path.join(OUT, 'batch_*.json')):
            st = json.load(open(p))
            if st.get('state') != 'collected':
                pending |= {v['word'] for v in st['index'].values()}
        todo = [w for w in words if occ.get(w) and w not in pending and not os.path.exists(os.path.join(OUT, w + '.json'))]
        reqs, index = requests_for(todo, inv, occ)
        chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content']) for r in reqs)
        n_occ = sum(len(occ[w]) for w in todo)
        est_in, est_out = chars / 3.2, n_occ * 9
        price = (est_in * 2 + est_out * 10) / 1e6 / 2           # Sonnet 5.5 $2/$10 per MTok, batch half price
        print(f'{len(words)} words chosen, {len(todo)} to do: {n_occ} occurrences in {len(reqs)} requests')
        print(f'rough estimate: {est_in / 1e6:.2f}M input + {est_out / 1e6:.2f}M output tokens ≈ ${price:.2f} with the batch discount')
        if a.command == 'preview':
            if reqs:
                print('\n===== SYSTEM =====\n' + SYSTEM + '\n\n===== USER =====\n' + reqs[0]['params']['messages'][0]['content'])
            return
        if a.command == 'test':
            w = todo[0]; batch = occ[w][:PER_CALL]
            r = reqs[0]['params']
            msg = client().messages.create(**r)
            text = ''.join(b.text for b in msg.content if getattr(b, 'type', '') == 'text')
            print('\n===== ANSWER =====\n' + text)
            print(f'\nparsed {len(parse(text, len(batch)))} of {len(batch)} lines; tokens: {msg.usage.input_tokens} in / {msg.usage.output_tokens} out')
            return
        if not reqs:
            print('nothing to submit'); return
        b = client().messages.batches.create(requests=reqs)
        json.dump({'batch_id': b.id, 'created': time.strftime('%Y-%m-%d %H:%M'), 'index': index, 'state': 'submitted'},
                  open(os.path.join(OUT, f'batch_{b.id}.json'), 'w'), ensure_ascii=False)
        print(f'submitted batch {b.id} with {len(reqs)} requests. Check with: python scripts/08_annotate_senses.py status')
        return

    states = sorted(glob.glob(os.path.join(OUT, 'batch_*.json')))
    if not states:
        print('no batches submitted yet'); return
    c = client()
    if a.command == 'status':
        for p in states:
            s = json.load(open(p))
            b = c.messages.batches.retrieve(s['batch_id'])
            rc = b.request_counts
            print(f"{s['batch_id']} ({s['created']}, {s['state']}): {b.processing_status} — "
                  f"succeeded {rc.succeeded}, processing {rc.processing}, errored {rc.errored}, expired {rc.expired}")
        return

    # collect
    occ_cache = {}
    for p in states:
        s = json.load(open(p))
        if s['state'] == 'collected':
            continue
        b = c.messages.batches.retrieve(s['batch_id'])
        if b.processing_status != 'ended':
            print(f"{s['batch_id']}: still {b.processing_status}, try again later"); continue
        words = sorted({v['word'] for v in s['index'].values()})
        if not occ_cache or not set(words) <= set(occ_cache):
            occ_cache.update(load_occurrences(a.occ, set(words)))
        got = collections.defaultdict(dict); bad = collections.Counter(); usage = [0, 0]
        for res in c.messages.batches.results(s['batch_id']):
            info = s['index'][res.custom_id]
            w = info['word']
            if res.result.type != 'succeeded':
                bad[w] += 1; continue
            msg = res.result.message
            usage[0] += msg.usage.input_tokens; usage[1] += msg.usage.output_tokens
            text = ''.join(x.text for x in msg.content if getattr(x, 'type', '') == 'text')
            try:
                labs = parse(text, len(info['occ_ids']))
            except ValueError as e:
                bad[w] += 1; print(f'  {w} {res.custom_id}: {e}', file=sys.stderr); continue
            for i, oid in enumerate(info['occ_ids'], 1):
                got[w][oid] = labs[i]
        done = 0
        for w in words:
            occs = occ_cache[w]
            if bad[w] or any(r['occ_id'] not in got[w] for r in occs):
                continue
            write_word(w, inv[w], occs, got[w]); done += 1
        s['state'] = 'collected'; s['usage'] = usage
        json.dump(s, open(p, 'w'), ensure_ascii=False)
        cost = (usage[0] * 2 + usage[1] * 10) / 1e6 / 2
        print(f"{s['batch_id']}: {done} of {len(words)} words written; tokens {usage[0]:,} in / {usage[1]:,} out ≈ ${cost:.2f}")
        if bad:
            print(f'  {len(bad)} words had failed requests: {", ".join(sorted(bad))[:200]} — run submit again to redo them')


if __name__ == '__main__':
    main()
