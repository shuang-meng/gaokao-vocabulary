"""Shared vocabulary loading and token -> headword matching (steps 3 and 4).

    import vocab_match as vm
    vm.load("data/processed/vocab_3500.csv", "data/processed/vocab_supplement.csv")
    headword, span = vm.match(tokens, i)       # tokens: list of spaCy tokens
"""
import csv, re

heads, info, form_map, multi, supp_keys = {}, {}, {}, {}, set()
propn_heads = {}     # capitalised headword when a lowercase twin exists (China / china)


def load(vocab_path, supp_path):
    global supp_keys
    for r in csv.DictReader(open(vocab_path, encoding="utf-8-sig")):
        h = r["headword"]; key = h.lower()
        if key in heads and heads[key] != h:      # case twins: AD/ad, China/china, Miss/miss
            cap, low_ = (h, heads[key]) if h != key else (heads[key], h)
            propn_heads[key] = cap; heads[key] = low_
            info[h] = {"id": r["id"], "pos": r.get("pos", ""), "list": "main", "category": "",
                       "level": r.get("level", "")}
            continue
        heads[key] = h
        info[h] = {"id": r["id"], "pos": r.get("pos", ""), "list": "main", "category": "",
                   "level": r.get("level", "")}
        for f in filter(None, r["forms"].split(";")):
            form_map.setdefault(f.lower(), h)
    for r in csv.DictReader(open(supp_path, encoding="utf-8-sig")):
        w = r["word"]; key = w.lower()
        if key in heads: continue
        heads[key] = w
        info[w] = {"id": "", "pos": "", "list": "supplement", "category": r["category"], "level": ""}
    supp_keys = {k for k, h in heads.items() if info[h]["list"] == "supplement"}
    import unicodedata
    for key, h in list(heads.items()):                    # café -> also match 'cafe'
        plain = unicodedata.normalize("NFKD", key).encode("ascii", "ignore").decode()
        if plain != key: form_map.setdefault(plain, h)
    for key, h in list(heads.items()):
        toks = tuple(re.split(r"[\s\-]+", key))
        if len(toks) > 1:
            multi[toks] = h
    for f, h in list(form_map.items()):
        toks = tuple(re.split(r"[\s\-]+", f))
        if len(toks) > 1:
            multi.setdefault(toks, h)


CONTRACT = {"n't": "not", "'s": None, "'re": "be", "'m": "be", "'ve": "have", "'ll": "will",
            "'d": None, "ca": "can", "wo": "will", "sha": "shall"}
INFLECTED = {"VBG", "VBD", "VBN", "VBZ", "NNS", "JJR", "JJS", "RBR", "RBS"}


def stems(w):
    out = []
    if w.endswith("ing") and len(w) > 5:
        b = w[:-3]; out += [b + "e", b] + ([b[:-1]] if len(b) > 2 and b[-1] == b[-2] else [])
    if w.endswith("ied"): out.append(w[:-3] + "y")
    if w.endswith("ed") and len(w) > 4:
        b = w[:-2]; out += [w[:-1], b] + ([b[:-1]] if len(b) > 2 and b[-1] == b[-2] else [])
    if w.endswith("ies"): out.append(w[:-3] + "y")
    if w.endswith("es"): out.append(w[:-2])
    if w.endswith("s") and not w.endswith("ss"): out.append(w[:-1])
    for suf in ("er", "est"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            b = w[: -len(suf)]; out += [b, b + "e"] + ([b[:-1] + "y"] if b.endswith("i") else []) \
                + ([b[:-1]] if len(b) > 2 and b[-1] == b[-2] else [])
    return out


def derived_base(w):
    """Possible syllabus base for a derived word (actually->actual, writer->write). Not counted."""
    cands = []
    rules = [("ily", "y"), ("ly", ""), ("ly", "le"), ("ally", ""), ("ness", ""), ("iness", "y"),
             ("ment", ""), ("er", ""), ("er", "e"), ("or", ""), ("or", "e"), ("ist", ""),
             ("ful", ""), ("less", ""), ("ity", ""), ("ion", ""), ("ion", "e"), ("ation", "e"),
             ("ing", ""), ("ing", "e"), ("al", ""), ("ic", ""), ("ous", ""), ("ive", ""), ("ive", "e")]
    for suf, add in rules:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            b = w[: -len(suf)] + add
            cands.append(b)
            if len(b) > 3 and b[-1] == b[-2]: cands.append(b[:-1])
    for pre in ("un", "dis"):          # in-/re-/over- gave false hits (indoor->door, release->lease)
        if w.startswith(pre) and len(w) - len(pre) >= 3: cands.append(w[len(pre):])
    return [c for c in cands if c in heads]


FUNCTION_POS = {"DET", "ADP", "PRON", "CCONJ", "SCONJ", "AUX", "PART", "NUM", "INTJ"}


def match(tokens, i):
    """Return (headword, span_len) for token i, or (None, 1)."""
    for n in (3, 2):
        if i + n <= len(tokens):
            key = tuple(t.text.lower() for t in tokens[i:i + n] if t.text != "-")
            if key in multi:
                return multi[key], n
            # hyphenated: ice - cream
            if n == 3 and tokens[i + 1].text == "-":
                key2 = (tokens[i].text.lower(), tokens[i + 2].text.lower())
                if key2 in multi: return multi[key2], 3
                joined = f"{key2[0]}-{key2[1]}"
                if joined in heads: return heads[joined], 3
    t = tokens[i]
    low, lem = t.text.lower(), t.lemma_.lower()
    if low in CONTRACT:
        c = CONTRACT[low]
        if c is None:
            return (heads.get(lem) if lem in ("be", "have", "would") else None), 1
        return heads.get(c), 1
    if t.pos_ == "PROPN":
        if low in propn_heads: return propn_heads[low], 1
        if low in supp_keys: return heads[low], 1
        if low in form_map and form_map[low].lower() in supp_keys: return form_map[low], 1
        return None, 1
    if lem in heads and lem != low: return heads[lem], 1    # contextual lemma first (lives: live/life)
    if low in form_map: return form_map[low], 1
    if lem in heads: return heads[lem], 1
    if low in heads: return heads[low], 1
    if t.tag_ in INFLECTED:                       # small-model lemma errors: hoping -> 'hop'
        for c in stems(low):
            if c in heads: return heads[c], 1
            if c in form_map: return form_map[c], 1
    if low.rstrip(".") + "." in heads: return heads[low.rstrip(".") + "."], 1   # Mr / Mr.
    return None, 1


