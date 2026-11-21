# -*- coding: utf-8 -*-
"""Step 8h: "exam meaning" of the low-frequency words (rank 1001 and below).

These words occur only 1–10 times, so there is no hand-written sense list. In one call the model both lists
the senses a word actually has in these exam sentences and labels every sentence. For each sense it also says
whether it is the meaning students normally learn first ("c" = common) or a less common one ("r" = rare):
the "r" senses are the 熟词僻义 a student is most likely to misread.

Commands:  preview | test | submit | status | collect      (API key: ANTHROPIC_API_KEY)
Output: data/interim/annotations/<word>.json, same format as step 8 plus "sense_common", so step 8c counts them too.
"""
import argparse, collections, csv, glob, importlib.util, json, os, re, sys, time

spec = importlib.util.spec_from_file_location('s08', os.path.join(os.path.dirname(__file__), '08_annotate_senses.py'))
s08 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s08)
MODEL = s08.MODEL
EXTRA = s08.EXTRA
ST = 'data/interim/rare_batches'
MAX_SENT, MAX_WORDS = 40, 15

SYSTEM = """You study how words are used in Chinese college entrance exam (gaokao) English texts.
For each target word you get its usual Chinese dictionary glosses (for reference only) and every exam sentence
it occurs in, with the word marked like ⟦this⟧.

For each word, first list the senses that actually occur in these sentences (only those), then label each sentence.
Answer in exactly this format and nothing else:
## word
S|1|pos|short Chinese gloss|c
S|2|pos|short Chinese gloss|r
L|id|sense|phrase|confidence
- S lines: number the senses 1, 2, …; pos like n. / v. / adj. / adv.; a short Chinese gloss (2–10 characters) of
  the sense as used here. Last field: c if this is the meaning a Chinese student normally learns first for this
  word (its main, most familiar meaning), r if it is a less familiar meaning.
- L lines: one per sentence id. sense = a number from your S list, or SKIP when the word appears only as a bare
  option in a list of options, or the text is garbled. A single answer option ("C. To protect the plants.") is a
  normal sentence.
- phrase: leave empty unless the word is part of a multi-word expression whose meaning cannot be worked out from
  its parts (strict standard: give up, of course, in charge of). Not phrases: transparent compounds and ordinary
  collocations.
- confidence: h, m or l (may be left empty when h).
Example:
## drift
S|1|v.|漂流；漂移|c
S|2|v.|渐渐（进入某状态）|r
L|1|1||
L|2|2|drift off|m"""


def load():
    E = [r for r in csv.DictReader(open('data/processed/entries_with_defs.csv', encoding='utf-8-sig'))
         if int(r['total_count']) > 0 and int(r['rank']) > 1000]
    words = [r['headword'] for r in E]
    gloss = {r['headword']: re.sub(r'\s+', ' ', r['zh_gloss'].replace('\\r', ' ').replace('\\n', ' '))[:80] for r in E}
    occ = s08.load_occurrences('data/interim/occurrences.tsv', set(words))
    return words, gloss, occ


def requests():
    words, gloss, occ = load()
    done = {os.path.basename(p)[:-5] for p in glob.glob('data/interim/annotations/*.json')}
    pending = set()
    for p in glob.glob(os.path.join(ST, 'batch_*.json')):
        s = json.load(open(p))
        if s['state'] != 'collected':
            pending |= {w for v in s['index'].values() for w in v['words']}
    todo = [w for w in words if occ.get(w) and w not in done and w not in pending]
    reqs, index, cur = [], {}, []

    def flush():
        if not cur:
            return
        cid = f'rare{len(reqs):04d}'
        lines, ids, k = [], [], 0
        for w in cur:
            lines += [f'## {w}', f'(dictionary: {gloss[w]})']
            for r in occ[w]:
                k += 1; ids.append(r['occ_id'])
                lines.append(f"{k}. ({r['year']} {s08.SEC.get(r['section'], r['section'])}) {s08.mark(r['sentence'], r['surface'], r['nth'])}")
            lines.append('')
        index[cid] = {'words': list(cur), 'occ_ids': ids}
        reqs.append({'custom_id': cid, 'params': dict(model=MODEL, max_tokens=22 * k + 60 * len(cur) + 400, system=SYSTEM,
                     messages=[{'role': 'user', 'content': '\n'.join(lines)}], **EXTRA)})
        cur.clear()

    n = 0
    for w in todo:
        m = len(occ[w])
        if cur and (n + m > MAX_SENT or len(cur) >= MAX_WORDS):
            flush(); n = 0
        cur.append(w); n += m
    flush()
    return reqs, index, occ


def parse(text, index, occ):
    """-> {word: (senses [[no, 'pos zh'], ...], common {no: c/r}, labels {occ_id: {...}})}"""
    ids = index['occ_ids']
    out, w = {}, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('##'):
            w = line[2:].strip(); out[w] = ([], {}, {}); continue
        p = [x.strip() for x in line.split('|')]
        if not w or len(p) < 2:
            continue
        if p[0] == 'S' and len(p) >= 4:
            out[w][0].append([p[1], f'{p[2]} {p[3]}'.strip()]); out[w][1][p[1]] = (p[4] if len(p) > 4 else 'c')[:1].lower()
        elif p[0] == 'L' and p[1].isdigit():
            p += [''] * (5 - len(p))
            i = int(p[1])
            if 1 <= i <= len(ids):
                sense = 'SKIP' if p[2].upper() == 'SKIP' else p[2]
                out[w][2][ids[i - 1]] = {'sense': sense, 'new_sense_zh': None, 'phrase': p[3] or None,
                                         'confidence': (p[4] or 'h').lower()[:1]}
    missing = [w for w in index['words'] if w not in out or len(out[w][2]) < len(occ[w])]
    if missing:
        raise ValueError(f'incomplete answer for {missing[:5]}')
    return out


def write(word, senses, common, occs, labels):
    rows = [{'occ_id': r['occ_id'], 'word': word, 'year': r['year'], 'paper': r['paper_id'], 'section': r['section'],
             'surface': r['surface'], 'sentence': r['sentence'], **labels[r['occ_id']]} for r in occs]
    p = os.path.join(s08.OUT, word + '.json')
    json.dump({'word': word, 'model': MODEL, 'senses': senses, 'sense_common': common, 'labels': rows, 'kind': 'rare'},
              open(p + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    os.replace(p + '.tmp', p)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('command', choices=['preview', 'test', 'submit', 'status', 'collect'])
    a = ap.parse_args(); os.makedirs(ST, exist_ok=True); os.makedirs(s08.OUT, exist_ok=True)
    if a.command in ('preview', 'test', 'submit'):
        reqs, index, occ = requests()
        chars = sum(len(r['params']['system']) + len(r['params']['messages'][0]['content']) for r in reqs)
        n = sum(len(v['occ_ids']) for v in index.values()); nw = sum(len(v['words']) for v in index.values())
        print(f'{nw} words, {n} sentences, {len(reqs)} requests; rough estimate ≈ ${(chars / 3.2 * 2 + (n * 10 + nw * 25) * 10) / 1e6 / 2:.2f} (batch)')
        if a.command == 'preview':
            if reqs: print('\n===== USER =====\n' + reqs[0]['params']['messages'][0]['content'][:2000])
            return
        if a.command == 'test':
            r = reqs[0]; msg = s08.client().messages.create(**r['params'])
            text = ''.join(x.text for x in msg.content if getattr(x, 'type', '') == 'text')
            print(text); got = parse(text, index[r['custom_id']], occ)
            print(f"\nparsed {len(got)} words; tokens {msg.usage.input_tokens} in / {msg.usage.output_tokens} out; stop {msg.stop_reason}")
            return
        if not reqs:
            return print('nothing to submit')
        b = s08.client().messages.batches.create(requests=reqs)
        json.dump({'batch_id': b.id, 'created': time.strftime('%Y-%m-%d %H:%M'), 'index': index, 'state': 'submitted'},
                  open(os.path.join(ST, f'batch_{b.id}.json'), 'w'), ensure_ascii=False)
        return print(f'submitted batch {b.id}. Check with: python scripts/08h_rare_words.py status')
    c = s08.client()
    for p in sorted(glob.glob(os.path.join(ST, 'batch_*.json'))):
        s = json.load(open(p)); b = c.messages.batches.retrieve(s['batch_id']); rc = b.request_counts
        if a.command == 'status' or s['state'] == 'collected':
            print(f"{s['batch_id']} ({s['state']}): {b.processing_status} — succeeded {rc.succeeded}, processing {rc.processing}, errored {rc.errored}")
            continue
        if b.processing_status != 'ended':
            print('still', b.processing_status); continue
        occ = load()[2]
        done, bad, usage = 0, [], [0, 0]
        for res in c.messages.batches.results(s['batch_id']):
            info = s['index'][res.custom_id]
            if res.result.type != 'succeeded':
                bad.append(res.custom_id); continue
            msg = res.result.message; usage[0] += msg.usage.input_tokens; usage[1] += msg.usage.output_tokens
            text = ''.join(x.text for x in msg.content if getattr(x, 'type', '') == 'text')
            try:
                got = parse(text, info, occ)
            except ValueError as e:
                bad.append(res.custom_id); print(' ', res.custom_id, e, file=sys.stderr); continue
            for w in info['words']:
                senses, common, labels = got[w]
                write(w, senses, common, occ[w], labels); done += 1
        s['state'] = 'collected'; s['usage'] = usage; json.dump(s, open(p, 'w'), ensure_ascii=False)
        print(f"{done} words written; tokens {usage[0]:,} in / {usage[1]:,} out ≈ ${(usage[0] * 2 + usage[1] * 10) / 1e6 / 2:.2f}"
              + (f"; failed requests {bad} — run submit again for their words" if bad else ''))


if __name__ == '__main__':
    main()
