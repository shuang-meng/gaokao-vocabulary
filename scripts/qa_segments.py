"""QA report for step 2b: words per section, question numbers seen, answers found."""
import csv, glob, os, re, sys
from collections import defaultdict

seg = sys.argv[1]
def rng(nums):
    nums = sorted(set(nums))
    if not nums: return "-"
    out, a, b = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == b + 1: b = n
        else: out.append(f"{a}-{b}" if a != b else str(a)); a = b = n
    out.append(f"{a}-{b}" if a != b else str(a))
    return ",".join(out)

order = ["listening", "single_choice", "reading", "seven", "cloze", "grammar", "correction", "writing"]
print("paper\t" + "\t".join(order) + "\ttranscript_w\tcloze_grammar_answers")
for p in sorted(glob.glob(os.path.join(seg, "*.lines.tsv"))):
    pid = os.path.basename(p).split(".")[0]
    words, qs = defaultdict(int), defaultdict(list)
    tw = 0
    for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"):
        n = len(re.findall(r"[A-Za-z]+", r["text"]))
        words[r["section"]] += n
        if r["kind"] == "transcript": tw += n
        if r["qnum"]: qs[r["section"]].append(int(r["qnum"]))
    ans = [int(r["qnum"]) for r in csv.DictReader(open(p.replace(".lines.", ".answers."), encoding="utf-8"), delimiter="\t")
           if r["section"] in ("cloze", "grammar")]
    cells = [f"{words[s]}w q{rng(qs[s])}" if words[s] else "" for s in order]
    print(pid + "\t" + "\t".join(cells) + f"\t{tw}\t{rng(ans)}")
