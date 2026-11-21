# -*- coding: utf-8 -*-
"""Step 9a: "tested words" — words that were the correct answer of a cloze (完形) or grammar-fill (语法填空) blank.

A word that appears in a passage is read; a word that is the answer of a blank is what the examiner chose to test.
usage: python scripts/09a_tested_words.py
Inputs : data/interim/segments/<paper>.lines.tsv / .answers.tsv (step 2b), data/processed/vocab_kb2025*.csv
Output : data/processed/tested_words.csv — headword, cloze_answer, cloze_years, cloze_distractor, grammar_answer,
         grammar_years, tested_years, answers (year:blank list). No exam sentences.
A blank shared by both 2008 papers counts once (same year, same answer word).
"""
import collections, csv, glob, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
import vocab_match as vm

SEG = 'data/interim/segments'
OPT = re.compile(r"([A-D])\s*[.．、]\s*(.*?)(?=\s+[A-D]\s*[.．、]|\s*$)")


def head(word):
    w = word.lower().strip(" .,;'\"’“”")
    if not w:
        return None
    if w in vm.heads:
        return vm.heads[w]
    if w in vm.form_map:
        return vm.form_map[w]
    for c in vm.stems(w):
        if c in vm.heads:
            return vm.heads[c]
        if c in vm.form_map:
            return vm.form_map[c]
    d = vm.derived_base(w)
    return vm.heads[d[0]] if d else None


def main():
    vm.load('data/processed/vocab_kb2025.csv', 'data/processed/vocab_kb2025_supplement.csv')
    ans_c, ans_g, dis = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
    where = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(SEG, '*.lines.tsv'))):
        pid = os.path.basename(p).split('.')[0]; year = pid[:4]
        ans = collections.defaultdict(dict)
        for r in csv.DictReader(open(os.path.join(SEG, pid + '.answers.tsv'), encoding='utf-8'), delimiter='\t'):
            ans[int(r['qnum'])][r['section']] = r['answer'].strip()
        options, cur = collections.defaultdict(dict), None
        for r in csv.DictReader(open(p, encoding='utf-8'), delimiter='\t'):
            if r['section'] == 'cloze' and r['kind'] in ('option', 'question'):
                if r['qnum']:
                    cur = int(r['qnum'])
                if cur is not None:
                    for letter, txt in OPT.findall(re.sub(rf"^\s*{cur}\s*[.．、]?", "", r['text'])):
                        options[cur].setdefault(letter, txt.strip())
        for n, opts in options.items():
            letter = ans.get(n, {}).get('cloze') or next((v for v in ans.get(n, {}).values() if re.fullmatch('[A-D]', v)), None)
            for L, txt in opts.items():
                words = [h for h in (head(t) for t in re.findall(r"[A-Za-z][A-Za-z'-]*", txt)) if h]
                for h in words[:1] if len(words) == 1 else words:
                    key = (year, f'{n}{L}', txt.lower())
                    (ans_c if L == letter else dis)[h].add(key)
                    if L == letter:
                        where[h].add(f'{year}:完形{n}')
        for n, d in ans.items():                      # grammar answers are written words, not letters
            a = d.get('grammar')
            if not a or re.fullmatch('[A-G]', a):
                continue
            first = re.split(r'/|##|\|', a)[0]
            for t in re.findall(r"[A-Za-z][A-Za-z'-]*", first):
                h = head(t)
                if h:
                    ans_g[h].add((year, str(n), t.lower())); where[h].add(f'{year}:语法{n}')
    words = set(ans_c) | set(ans_g)
    rows = []
    for h in words:
        rows.append({'headword': h, 'cloze_answer': len({(y, t) for y, _, t in ans_c[h]}),
                     'cloze_years': len({y for y, _, _ in ans_c[h]}),
                     'cloze_distractor': len({(y, t) for y, _, t in dis[h]}),
                     'grammar_answer': len({(y, n) for y, n, _ in ans_g[h]}),
                     'grammar_years': len({y for y, _, _ in ans_g[h]}),
                     'tested_years': len({y for y, _, _ in ans_c[h] | ans_g[h]}),
                     'answers': ' '.join(sorted(where[h]))})
    rows.sort(key=lambda r: (-r['tested_years'], -(r['cloze_answer'] + r['grammar_answer'])))
    with open('data/processed/tested_words.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} tested words ({sum(r['cloze_answer'] > 0 for r in rows)} as cloze answers, "
          f"{sum(r['grammar_answer'] > 0 for r in rows)} as grammar answers)")
    print('most tested:', ', '.join(f"{r['headword']}({r['tested_years']}y)" for r in rows[:25]))


if __name__ == '__main__':
    main()
