"""Step 3: lemmatise the exam corpus, match tokens to the syllabus list, count frequencies.

Usage:
  python scripts/03_count_frequency.py data/interim/corpus_all.tsv \
      data/processed/vocab_3500.csv data/processed/vocab_supplement.csv data/processed

Counting rules (see 需求与口径基线):
  * every row counts EXCEPT cloze options (kind=option in section=cloze); those are counted
    separately in `cloze_option_count`
  * cloze / grammar passages are the answer-filled versions
  * proper nouns (PROPN) only match the supplement list (countries, months, weekdays) so that
    names such as Bill / Rose / Mark do not inflate bill / rose / mark
  * matching order: multiword headword -> spaCy lemma (if it is a headword) -> irregular/US/plural
    form table -> surface -> rule-based stems (to correct small-model lemma errors)

Outputs (data/processed/):
  word_freq.csv        one row per headword (main list + supplement), with counts and ranks
  offlist_freq.csv     frequent lemmas not in the syllabus list (超纲词)
  coverage_curve.csv   top-N headwords -> share of exam tokens covered
and data/interim/occurrences.tsv (token-level hits with sentence ids; contains exam text, git-ignored)
"""
import csv, re, sys
from collections import Counter, defaultdict
import spacy

corpus_path, vocab_path, supp_path, outdir = sys.argv[1:5]
interim = corpus_path.rsplit("/", 1)[0]

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vocab_match as vm
vm.load(vocab_path, supp_path)
heads, info, form_map, match, derived_base, FUNCTION_POS = (
    vm.heads, vm.info, vm.form_map, vm.match, vm.derived_base, vm.FUNCTION_POS)

# ---------------- corpus ----------------
rows = list(csv.DictReader(open(corpus_path, encoding="utf-8"), delimiter="\t"))
nlp = spacy.load("en_core_web_sm", disable=["ner"])

counts = Counter(); years = defaultdict(set); papers = defaultdict(set)
sec_counts = defaultdict(Counter); line_counts = defaultdict(Counter)
cloze_opt = Counter(); off = Counter(); off_years = defaultdict(set)
token_total = Counter()            # 'all' and 'content' token totals (counted rows only)
hit_tokens = defaultdict(Counter)  # headword -> {'all': n, 'content': n}
occ = open(f"{interim}/occurrences.tsv", "w", encoding="utf-8", newline="")
occw = csv.writer(occ, delimiter="\t")
occw.writerow(["headword", "surface", "upos", "paper_id", "year", "line_code", "section", "kind", "sent_id", "sentence"])
sent_id = 0


texts = [r["text"] for r in rows]
for r, doc in zip(rows, nlp.pipe(texts, batch_size=64)):
    is_cloze_opt = r["section"] == "cloze" and r["kind"] == "option"
    for sent in doc.sents:
        sent_id += 1
        toks = [t for t in sent]
        i = 0
        while i < len(toks):
            t = toks[i]
            if not re.search(r"[A-Za-z]", t.text) or (len(t.text) == 1 and t.text not in "aAI"):
                i += 1; continue
            if re.fullmatch(r"[A-G]", t.text) and i + 1 < len(toks) and toks[i + 1].text in (".", "．"):
                i += 1; continue                                  # option labels 'A.'
            if t.text in ("Text", "Passage") and i + 1 < len(toks) and re.fullmatch(r"\d+|[A-E]", toks[i + 1].text):
                i += 2; continue                                  # 'Text 1' / 'Passage B' labels
            h, n = match(toks, i)
            content = t.pos_ not in FUNCTION_POS
            if is_cloze_opt:
                if h: cloze_opt[h] += 1
                i += n; continue
            if t.pos_ != "PROPN":
                token_total["all"] += 1
                if content: token_total["content"] += 1
            if h:
                counts[h] += 1; years[h].add(r["year"]); papers[h].add(r["paper_id"])
                sec_counts[h][r["section"]] += 1; line_counts[h][r["line_code"]] += 1
                if t.pos_ != "PROPN":
                    hit_tokens[h]["all"] += 1
                    if content: hit_tokens[h]["content"] += 1
                if r["year"] >= "2016": line_counts[h]["since2016"] += 1
                if r["year"] >= "2024": line_counts[h]["since2024"] += 1
                occw.writerow([h, " ".join(x.text for x in toks[i:i + n]), t.pos_, r["paper_id"], r["year"],
                               r["line_code"], r["section"], r["kind"], sent_id, sent.text.strip()])
            elif t.pos_ not in ("PROPN",) and t.pos_ not in FUNCTION_POS and t.is_alpha:
                off[t.lemma_.lower()] += 1; off_years[t.lemma_.lower()].add(r["year"])
            i += n
occ.close()

# ---------------- outputs ----------------
SECTIONS = ["reading", "listening", "cloze", "seven", "grammar", "single_choice", "correction", "writing"]
LINES = ["DG1", "XKB", "QG1", "YI", "XG1"]
all_years = sorted({r["year"] for r in rows})
ranked = sorted(info, key=lambda h: (-len(years[h]), -counts[h], h.lower()))
rank_by_count = {h: i + 1 for i, h in enumerate(sorted(info, key=lambda h: (-counts[h], h.lower())))}
with open(f"{outdir}/word_freq.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["rank", "rank_by_count", "headword", "list", "category", "pos", "level", "total_count",
                "years_count", "years_total", "papers_count", "since2016_count", "since2024_count",
                "cloze_option_count", "coverage_hits"] + [f"sec_{s}" for s in SECTIONS] + [f"line_{l}" for l in LINES]
               + ["years"])
    for i, h in enumerate(ranked, 1):
        w.writerow([i, rank_by_count[h], h, info[h]["list"], info[h]["category"], info[h]["pos"], info[h].get("level", ""),
                    counts[h], len(years[h]), len(all_years), len(papers[h]),
                    line_counts[h]["since2016"], line_counts[h]["since2024"], cloze_opt[h], hit_tokens[h]["all"]]
                   + [sec_counts[h][s] for s in SECTIONS] + [line_counts[h][l] for l in LINES]
                   + [" ".join(sorted(years[h]))])

with open(f"{outdir}/offlist_freq.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["lemma", "count", "years_count", "possible_base_in_list"])
    for lem, c in off.most_common():
        if c >= 2: w.writerow([lem, c, len(off_years[lem]), ";".join(heads[b] for b in derived_base(lem))])

# coverage: rank headwords by total count; cumulative share of non-PROPN tokens they cover
with open(f"{outdir}/coverage_curve.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["top_n", "share_all_tokens", "top_n_content", "share_content_tokens"])
    by_all = sorted(info, key=lambda h: -hit_tokens[h]["all"])
    by_con = sorted(info, key=lambda h: -hit_tokens[h]["content"])
    cum_a = cum_c = 0
    marks = set(list(range(50, 501, 50)) + list(range(600, 3701, 100)))
    for n in range(1, len(info) + 1):
        cum_a += hit_tokens[by_all[n - 1]]["all"]; cum_c += hit_tokens[by_con[n - 1]]["content"]
        if n in marks or n == len(info):
            w.writerow([n, round(cum_a / token_total["all"], 4), n,
                        round(cum_c / token_total["content"], 4)])

import json
json.dump({"tokens_all": token_total["all"], "tokens_content": token_total["content"],
           "papers": len({r["paper_id"] for r in rows}), "years": len(all_years)},
          open(f"{outdir}/token_totals.json", "w"), ensure_ascii=False, indent=1)
matched = sum(1 for h in info if counts[h])
print(f"tokens(all, non-PROPN)={token_total['all']}  content={token_total['content']}")
print(f"headwords seen: {matched}/{len(info)}  never seen: {len(info) - matched}")
print(f"syllabus coverage of all tokens: {sum(v['all'] for v in hit_tokens.values()) / token_total['all']:.3f}")
