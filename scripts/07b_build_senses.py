# -*- coding: utf-8 -*-
"""Merge hand-written sense files into one table.

usage: 07b_build_senses.py data/manual/senses data/pilot/samples_1_1000.json data/processed/senses.csv

Sense files (data/manual/senses/*.json) map a word to a list of
  [pos, zh, en, n, example]
where example is either an index into that word's sample in samples_*.json,
a literal [sentence, source] pair, or null. n is the number of sampled
sentences that use the sense, so it is a sample count, not a full count.
A file may hold "__sample_size__": {word: N} when its counts come from a
different sample (the pilot does this).
Senses, wording and the choice of examples are original to this project (CC BY-SA 4.0).
"""
import csv, glob, json, os, re, sys

SEC = {'list': '听力', 'read': '阅读', 'cloz': '完形', 'gram': '语法填空', 'seve': '七选五',
       'writ': '写作', 'sing': '单选', 'corr': '改错'}

def clean(s):
    s = re.sub(r'\s*_{2,}\s*\d+\s*_{2,}\s*', ' ', s)          # seven-choice gap markers "____ 36 ____"
    s = re.sub(r'^\s*\d+\s{2,}', '', s)                        # leading item numbers "37    We ..."
    s = re.sub(r'^\s*[A-G]\.\s+(?=[A-Z])', '', s)               # a single answer option "C. To ..."
    s = re.sub(r'^\s*[:：]\s*', '', s)
    s = re.sub(r'^\s*(?:[A-Z]|Man|Woman|Boy|Girl)\s*[:：]\s*', '', s)   # listening speaker labels "W: "
    s = re.sub(r'^\s*\d{1,2}\s*[.、]\s*(?=[A-Z])', '', s)                  # question numbers "17 Where ..." / "1.Where"
    s = re.sub(r'^\s*\d{1,2}\s+(?=[A-Z])', '', s)
    s = re.sub(r'^\s*\d{1,2}\s*[.、]\s*[—-]+\s*', '', s)                 # "35. — Artistic ..."
    s = re.sub(r'^\s*[—-]{1,2}\s*', '', s)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    return s


def usable(s):
    return s and '__' not in s and len(re.findall(r'(?:^|\s)[A-D]\.\s', s)) < 2 and not re.search(r'\s{2,}', s)


def main(sense_dir, samples_path, out):
    samples = json.load(open(samples_path, encoding='utf-8'))
    rows, errors, seen = [], [], {}
    for f in sorted(glob.glob(os.path.join(sense_dir, '*.json'))):
        data = json.load(open(f, encoding='utf-8'))
        sizes = data.pop('__sample_size__', {})
        for w, senses in data.items():
            if w in seen:
                errors.append(f'{w}: defined in both {seen[w]} and {os.path.basename(f)}')
                continue
            seen[w] = os.path.basename(f)
            sm = samples.get(w, {}).get('sents', [])
            size = sizes.get(w, len(sm))
            for i, s in enumerate(senses, 1):
                pos, zh, en, n, ex = (s + [None] * 5)[:5]
                sent = src = ''
                if isinstance(ex, int):
                    if ex >= len(sm):
                        errors.append(f'{w} sense {i}: example index {ex} out of range ({len(sm)})')
                    else:
                        y, sec, _, _, sent, code = (sm[ex] + [''])[:6]
                        src = f'{y} {code} {SEC.get(sec, sec)}'.replace('  ', ' ')
                elif isinstance(ex, list):
                    sent, src = ex
                    parts = src.split()
                    if len(parts) == 2:                      # "2014 阅读" -> keep form "2014 阅读"
                        src = f'{parts[0]} {parts[1]}'
                sent = clean(sent)
                if sent and not usable(sent):
                    errors.append(f'{w} sense {i}: example dropped (blank or options): {sent[:60]}')
                    sent = src = ''
                rows.append({'headword': w, 'sense_no': i, 'pos': pos, 'zh': zh, 'en': en,
                             'sample_n': n, 'sample_size': size, 'example': sent.strip(),
                             'example_src': src, 'file': os.path.basename(f)})
    with open(out, 'w', encoding='utf-8-sig', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)
    for e in errors:
        print('WARN', e, file=sys.stderr)
    print(f'{len(seen)} words, {len(rows)} senses -> {out}')

if __name__ == '__main__':
    main(*sys.argv[1:4])
