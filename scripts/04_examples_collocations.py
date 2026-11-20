"""Step 4: per headword, pick exam example sentences, extract 句素 (collocations), attach derived words.

Usage:
  python scripts/04_examples_collocations.py data/interim/corpus_all.tsv \
      data/processed/vocab_3500.csv data/processed/vocab_supplement.csv data/processed

Inputs also read: data/processed/word_freq.csv, data/processed/offlist_freq.csv
Output: data/processed/entries.csv  (one row per headword, ordered by rank)

Example sentences (max 3):
  source priority  reading / cloze / seven / grammar / writing passages  >  listening  >  questions & options
  length 8–30 words, no blanks or option labels, one sentence per year, most recent years first
句素 (collocations) from the dependency parse, counted across the whole corpus:
  phrasal verb (give up) · verb+prep (depend on) · verb+object (make a decision) · verb+to-do (decide to)
  adj+prep (interested in) · noun+prep (interest in) · adj+noun (a fierce storm)
Derived words (Plan A): off-list words whose base is this headword, shown with counts, NOT added to counts.
"""
import csv, os, re, sys
from collections import Counter, defaultdict
import spacy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vocab_match as vm

corpus_path, vocab_path, supp_path, outdir = sys.argv[1:5]
vm.load(vocab_path, supp_path)

SKIP_COLLOC = {"be", "have", "do", "the", "a", "an", "of", "to", "in", "and", "it", "that", "this",
               "for", "on", "with", "as", "at", "by", "from", "or", "but", "not", "will", "can", "would"}
SEC_WEIGHT = {"reading": 3, "cloze": 3, "seven": 3, "grammar": 3, "writing": 2.5,
              "listening": 2, "correction": 0.5, "single_choice": 0.5}
KIND_WEIGHT = {"passage": 1.0, "passage_filled": 1.0, "transcript": 0.9, "question": 0.3, "option": 0.1}

rows = list(csv.DictReader(open(corpus_path, encoding="utf-8"), delimiter="\t"))
nlp = spacy.load("en_core_web_sm", disable=["ner"])

colloc = defaultdict(Counter)       # headword -> Counter(pattern key)
colloc_show = {}                    # pattern key -> display string (first seen)
cands = defaultdict(list)           # headword -> [(score, year, sentence, paper, section)]


def hw(tok):
    h, _ = vm.match([tok], 0)
    return h


def np_text(tok):
    """object noun with its determiner / adjective, e.g. 'a decision', 'great progress'."""
    left = [c for c in tok.lefts if c.dep_ in ("det", "amod", "compound", "poss", "nummod")]
    left = left[-2:]
    return " ".join([c.text.lower() for c in left] + [tok.text.lower()])


def add(h, key, show):
    if h and h.lower() not in SKIP_COLLOC:
        colloc[h][key] += 1
        colloc_show.setdefault(key, show)


def clean_sentence(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:!?’'”)])", r"\1", s)
    s = re.sub(r"([(“])\s+", r"\1", s)
    s = re.sub(r"(\w)\s*([’'])\s+(m|s|re|ve|ll|d|t)\b", r"\1\2\3", s)      # I’ m -> I’m
    return s


texts = [r["text"] for r in rows]
for r, doc in zip(rows, nlp.pipe(texts, batch_size=64)):
    if r["section"] == "cloze" and r["kind"] == "option":
        continue
    base_score = SEC_WEIGHT.get(r["section"], 1) * KIND_WEIGHT.get(r["kind"], 0.5)
    for sent in doc.sents:
        toks = list(sent)
        heads_in_sent = {}
        i = 0
        while i < len(toks):
            h, n = vm.match(toks, i)
            if h: heads_in_sent.setdefault(h, toks[i])
            i += n
        # ---- collocations ----
        for t in toks:
            th = hw(t)
            if t.pos_ == "VERB":
                for c in t.children:
                    if c.dep_ == "prt":                                   # give up
                        add(th, ("phr", t.lemma_, c.text.lower()), f"{t.lemma_} {c.text.lower()}")
                    elif c.dep_ == "prep" and 0 < c.i - t.i <= 2 and any(g.dep_ == "pobj" for g in c.children):
                        add(th, ("vprep", t.lemma_, c.text.lower()), f"{t.lemma_} {c.text.lower()}")   # depend on
                    elif c.dep_ == "dobj" and c.pos_ == "NOUN":            # make a decision
                        nxt = c.doc[c.i + 1] if c.i + 1 < len(c.doc) else None
                        if nxt is not None and nxt.dep_ == "prep" and nxt.head in (t, c):   # take care of
                            show = f"{t.lemma_} {c.text.lower()} {nxt.text.lower()}"
                            key = ("vop", t.lemma_, c.lemma_, nxt.text.lower())
                        else:
                            show = f"{t.lemma_} + {c.lemma_}"
                            key = ("vobj", t.lemma_, c.lemma_)
                        add(th, key, show); add(hw(c), key, show)
                    elif c.dep_ == "xcomp" and any(a.dep_ == "aux" and a.text.lower() == "to" for a in c.children):
                        add(th, ("vto", t.lemma_), f"{t.lemma_} to do")   # decide to do
            if t.pos_ == "ADJ":
                for c in t.children:
                    if c.dep_ == "prep" and 0 < c.i - t.i <= 2 and any(g.dep_ == "pobj" for g in c.children):
                        add(th, ("aprep", t.lemma_, c.text.lower()), f"{t.text.lower()} {c.text.lower()}")  # interested in
                if t.dep_ == "amod" and t.head.pos_ == "NOUN":                         # fierce storm
                    show = f"{t.lemma_.lower()} + {t.head.lemma_.lower()}"
                    key = ("anoun", t.lemma_, t.head.lemma_)
                    add(th, key, show); add(hw(t.head), key, show)
            if t.pos_ == "NOUN":
                for c in t.children:
                    if c.dep_ == "prep" and c.i - t.i == 1 and c.text.lower() != "of" and any(g.dep_ == "pobj" for g in c.children):
                        add(th, ("nprep", t.lemma_, c.text.lower()), f"{t.lemma_} {c.text.lower()}")   # interest in
        # ---- example candidates ----
        if r["section"] in ("correction", "single_choice"):
            continue        # 改错 contains planted errors; 单选 stems have their blank removed
        text = re.sub(r"^[MW]\s*[:：]\s*", "", clean_sentence(sent.text))
        nw = len(re.findall(r"[A-Za-z]+", text))
        if not (8 <= nw <= 30): continue
        if re.search(r"_{2,}|\b[A-G]\s*[.．]\s|\b\d{1,2}\s*[.．]\s|^[MW]\s*:|\?\s*$", text) and r["kind"] != "transcript":
            continue
        if not re.match(r"^[“\"'A-Z]", text) or not re.search(r"[.!?”\"']$", text):
            continue
        length_pen = abs(nw - 16) / 16
        for h in heads_in_sent:
            cands[h].append((base_score - length_pen, r["year"], text, r["paper_id"], r["section"]))

# ---------------- assemble ----------------
derived = defaultdict(list)
for r in csv.DictReader(open(os.path.join(outdir, "offlist_freq.csv"), encoding="utf-8-sig")):
    for b in vm.derived_base(r["lemma"]):
        derived[vm.heads[b]].append((r["lemma"], int(r["count"])))

freq = list(csv.DictReader(open(os.path.join(outdir, "word_freq.csv"), encoding="utf-8-sig")))
SEC_CN = {"reading": "阅读", "cloze": "完形", "seven": "七选五", "grammar": "语法填空", "writing": "写作",
          "listening": "听力", "correction": "改错", "single_choice": "单选"}
with open(os.path.join(outdir, "entries.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["rank", "headword", "pos", "level", "total_count", "years_count", "since2024_count",
                "example_1", "example_2", "example_3", "collocations", "derived_words"])
    used_global = Counter()        # spread examples: a sentence already shown for 2 words is skipped if possible
    for fr in freq:
        h = fr["headword"]
        picked, used_years, used_text = [], set(), set()
        ordered = sorted(cands.get(h, []), key=lambda x: (x[0] < 2.0, used_global[x[2]] >= 2, -int(x[1]), -x[0]))
        for score, year, text, pid, sec in ordered:  # good passages first, fresh sentences, then recent years
            if year in used_years or text in used_text: continue
            used_global[text] += 1
            picked.append(f"{text} （{year} {pid.split('_')[1]} {SEC_CN.get(sec, sec)}）")
            used_years.add(year); used_text.add(text)
            if len(picked) == 3: break
        top = [(k, c) for k, c in colloc[h].most_common(12) if c >= 2][:5]
        col = "; ".join(f"{colloc_show[k]} ×{c}" for k, c in top)
        der = "; ".join(f"{l} ×{c}" for l, c in sorted(derived.get(h, []), key=lambda x: -x[1])[:4])
        w.writerow([fr["rank"], h, fr["pos"], fr.get("level", ""), fr["total_count"], fr["years_count"], fr["since2024_count"]]
                   + picked + [""] * (3 - len(picked)) + [col, der])
n_ex = sum(1 for h in cands if cands[h])
print(f"headwords with example candidates: {n_ex}; with collocations: {sum(1 for h in colloc if colloc[h])}; "
      f"with derived words: {len(derived)}")
