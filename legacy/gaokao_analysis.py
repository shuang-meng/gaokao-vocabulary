# =============================================================
# 高考英语词频分析脚本
# 功能：统计2012-2025年高考英语试卷中考纲词的出现频率
#
# 使用前准备：
#   pip install python-docx
#
# 文件结构（修改下方 VOCAB_FILE 和 EXAM_DIR 为你的实际路径）：
#   VOCAB_FILE  → 高考英语3500词汇表中英文.doc
#   EXAM_DIR    → 存放所有试卷的文件夹
#
# 文件命名规则（只需包含以下关键词即可，顺序不限）：
#   - 年份四位数字：2012、2013 ... 2025
#   - 空白卷关键词：空白 或 真题
#   - 解析卷关键词：解析
#
# 运行方式：
#   python gaokao_analysis.py
#
# 输出文件：
#   results_full.csv    → 所有3500词的完整统计表
#   results_highfreq.csv → 高频词表（可直接用于备考）
# =============================================================

import os
import re
import json
import subprocess
from collections import Counter, defaultdict

# ─────────────────────────────────────────────────────────────
# ★ 修改这两个路径为你本地的实际路径
# ─────────────────────────────────────────────────────────────
VOCAB_FILE = r"vocab.docx"          # 词汇表路径
EXAM_DIR   = r"exams"          # 试卷文件夹路径

# 高频词判定标准（可自行调整）
HIGH_FREQ_MIN_YEARS = 10   # 出现年数 >= 10年
HIGH_FREQ_MIN_COUNT = 25   # 或 总频次 >= 25次
# ─────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════
# 1. 词形还原
#    策略：不规则词用手工词典，规则变化用后缀规则
#    目的：running/ran/runs 都归并到 run，统一计数
# ══════════════════════════════════════════════════════════════

IRREGULAR_FORMS = {
    # be动词
    "was":"be","were":"be","been":"be","is":"be","are":"be","am":"be",
    # 常见不规则动词
    "had":"have","has":"have","having":"have",
    "did":"do","does":"do","doing":"do","done":"do",
    "went":"go","gone":"go","goes":"go","going":"go",
    "saw":"see","seen":"see","sees":"see","seeing":"see",
    "ran":"run","runs":"run","running":"run",
    "came":"come","comes":"come","coming":"come",
    "took":"take","taken":"take","takes":"take","taking":"take",
    "gave":"give","given":"give","gives":"give","giving":"give",
    "got":"get","gotten":"get","gets":"get","getting":"get",
    "made":"make","makes":"make","making":"make",
    "knew":"know","known":"know","knows":"know","knowing":"know",
    "thought":"think","thinks":"think","thinking":"think",
    "said":"say","says":"say","saying":"say",
    "told":"tell","tells":"tell","telling":"tell",
    "found":"find","finds":"find","finding":"find",
    "left":"leave","leaving":"leave",
    "felt":"feel","feels":"feel","feeling":"feel",
    "kept":"keep","keeps":"keep","keeping":"keep",
    "met":"meet","meets":"meet","meeting":"meet",
    "held":"hold","holds":"hold","holding":"hold",
    "brought":"bring","brings":"bring","bringing":"bring",
    "bought":"buy","buys":"buy","buying":"buy",
    "taught":"teach","teaches":"teach","teaching":"teach",
    "caught":"catch","catches":"catch","catching":"catch",
    "built":"build","builds":"build","building":"build",
    "sent":"send","sends":"send","sending":"send",
    "spent":"spend","spends":"spend","spending":"spend",
    "lost":"lose","loses":"lose","losing":"lose",
    "led":"lead","leads":"lead","leading":"lead",
    "stood":"stand","stands":"stand","standing":"stand",
    "understood":"understand","understands":"understand","understanding":"understand",
    "wrote":"write","written":"write","writes":"write","writing":"write",
    "spoke":"speak","spoken":"speak","speaks":"speak","speaking":"speak",
    "broke":"break","broken":"break","breaks":"break","breaking":"break",
    "chose":"choose","chosen":"choose","chooses":"choose","choosing":"choose",
    "drove":"drive","driven":"drive","drives":"drive","driving":"drive",
    "grew":"grow","grown":"grow","grows":"grow","growing":"grow",
    "began":"begin","begun":"begin","begins":"begin","beginning":"begin",
    "fell":"fall","fallen":"fall","falls":"fall","falling":"fall",
    "sat":"sit","sits":"sit","sitting":"sit",
    "paid":"pay","pays":"pay","paying":"pay",
    # 不规则名词复数
    "children":"child","men":"man","women":"woman",
    "mice":"mouse","feet":"foot","teeth":"tooth","geese":"goose",
    "wolves":"wolf","lives":"life","knives":"knife","halves":"half",
    # 形容词/副词比较级最高级
    "better":"good","best":"good","worse":"bad","worst":"bad",
    # 修正重复统计
    "saying":"say","says":"say",
    "thinking":"think","thinks":"think",
    "works":"work",
    "running":"run","runs":"run",
    "finding":"find","finds":"find",
    "learning":"learn","learns":"learn","learned":"learn",
    "feeling":"feel","feels":"feel",
}

def lemmatize(word):
    """将单词还原为原形"""
    w = word.lower().strip("'")
    # 1. 查不规则词典
    if w in IRREGULAR_FORMS:
        return IRREGULAR_FORMS[w]
    # 2. 短词不处理
    if len(w) <= 3:
        return w
    # 3. 规则后缀处理
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"          # studies → study
    if w.endswith("sses") or w.endswith("xes") or w.endswith("ches") or w.endswith("shes"):
        return w[:-2]                 # passes → pass, boxes → box
    if w.endswith("ing") and len(w) > 5:
        stem = w[:-3]
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            return stem[:-1]          # running → run（双写辅音）
        return stem                   # reading → read
    if w.endswith("ed") and len(w) > 4:
        stem = w[:-2]
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            return stem[:-1]          # stopped → stop
        if stem.endswith("e"):
            return stem               # loved → love（已含e）
        return stem                   # worked → work
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]                 # cats → cat
    return w


# ══════════════════════════════════════════════════════════════
# 2. 停用词表
#    过滤掉虚词、功能词，只保留实义词用于统计
# ══════════════════════════════════════════════════════════════

STOPWORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "by","from","up","about","into","through","during","before","after",
    "above","below","between","out","off","over","under","again","further",
    "then","once","here","there","when","where","why","how","all","both",
    "each","few","more","most","other","some","such","no","nor","not","only",
    "own","same","so","than","too","very","just","as","that","this","these",
    "those","it","its","i","you","he","she","we","they","me","him","her",
    "us","them","my","your","his","our","their","what","which","who","whom",
    "whose","would","could","should","may","might","must","shall","will","can",
    "do","does","did","has","have","had","be","been","being","is","are",
    "was","were","am",
    "s","t","ll","ve","re","d","m",  # 缩写残留
    "paragraph","speaker","speakers","passage",  # 题目指令词
}


# ══════════════════════════════════════════════════════════════
# 3. 文件读取
#    .docx 用 python-docx；.doc 用系统工具（antiword 或 LibreOffice）
# ══════════════════════════════════════════════════════════════

def read_file(path):
    """读取 .doc 或 .docx 文件，返回纯文本字符串"""
    ext = os.path.splitext(path)[1].lower()

    # .docx：用 python-docx 直接读
    if ext == ".docx":
        try:
            import docx
            doc = docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            print(f"    [警告] python-docx 读取失败: {e}")

    # .doc：尝试 antiword（需系统安装），或 LibreOffice soffice
    # Windows 上建议安装 LibreOffice，Mac/Linux 用 antiword
    # 尝试 Python 版 antiword
    try:
        import antiword
        text = antiword.process(path)
        if text and len(re.findall(r"[a-zA-Z]{4,}", text)) > 20:
            return text
    except Exception:
        pass

    # 尝试系统版 antiword
    try:
        r = subprocess.run(["antiword", path], capture_output=True, timeout=60)
        text = r.stdout.decode("utf-8", errors="replace")
        if len(re.findall(r"[a-zA-Z]{4,}", text)) > 20:
            return text
    except Exception:
        pass

    print(f"    [警告] 无法读取文件: {os.path.basename(path)}")
    print(f"    提示: .doc 文件需要安装 antiword（Mac/Linux）或 LibreOffice（Windows）")
    return ""


# ══════════════════════════════════════════════════════════════
# 4. 从解析卷提取听力原文
#    解析卷中听力原文用【原文】标记，提取后补充到空白卷语料中
# ══════════════════════════════════════════════════════════════

def extract_listening_text(text):
    """提取解析卷中【原文】标记后的听力对话内容"""
    parts = re.findall(
        r"【原文】(.*?)(?=【|\d{1,2}[.。]|第[一二三四]节|\Z)",
        text,
        re.DOTALL
    )
    return " ".join(parts)


# ══════════════════════════════════════════════════════════════
# 5. 文本清洗与分词
#    去除中文、题号、选项标记，提取英文单词并词形还原
# ══════════════════════════════════════════════════════════════

def clean_and_tokenize(text):
    """清洗文本，返回词形还原后的单词列表（已过滤停用词）"""
    # 去中文字符
    text = re.sub(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+", " ", text)
    # 去选项标记 A. B. C. D.
    text = re.sub(r"\b[A-D]\.\s", " ", text)
    # 去纯数字
    text = re.sub(r"\b\d+\b", " ", text)

    words = []
    for w in re.findall(r"[a-zA-Z']+", text.lower()):
        w = w.strip("'")
        if len(w) < 2:
            continue
        lemma = lemmatize(w)
        if len(lemma) >= 2 and lemma not in STOPWORDS:
            words.append(lemma)
    return words


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("高考英语词频分析")
    print("=" * 60)

    # ── 步骤1：提取3500词汇表 ──────────────────────────────
    print("\n【步骤1】提取3500词汇表...")
    vocab_raw = read_file(VOCAB_FILE)
    vocab_set = set()
    # 词汇表格式：  1. abandon [音标] v. 释义
    for line in vocab_raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        # 兼容两种格式：有序号（1. abandon）或无序号（abandon [音标]...）
        m = re.match(r"^\s*(?:\d+\.\s+)?([a-zA-Z][a-zA-Z\-]*)", line)
        if m:
            word = m.group(1).strip().lower()
            if re.match(r"^[a-z\-]+$", word) and 2 <= len(word) <= 20:
                vocab_set.add(word)
    print(f"  提取到 {len(vocab_set)} 个词条")
    if len(vocab_set) < 100:
        print("  [错误] 词汇表提取失败，请检查 VOCAB_FILE 路径是否正确")
        return

    # ── 步骤2：读取并处理所有试卷 ─────────────────────────
    print(f"\n【步骤2】处理试卷文件夹: {EXAM_DIR}")
    all_files = [f for f in os.listdir(EXAM_DIR)
                 if not f.startswith(".") and not f.startswith("_")]

    # 按年份配对：空白卷 + 解析卷
    file_pairs = defaultdict(dict)
    for f in all_files:
        m = re.search(r"(\d{4})年", f)
        if not m:
            continue
        year = int(m.group(1))
        path = os.path.join(EXAM_DIR, f)
        if "空白" in f or "真题" in f:
            file_pairs[year]["blank"] = path
        elif "解析" in f:
            file_pairs[year]["analysis"] = path

    print(f"  找到 {len(file_pairs)} 个年份: {sorted(file_pairs.keys())}")

    year_words = {}   # year -> [词形还原后的单词列表]
    for year in sorted(file_pairs.keys()):
        pair = file_pairs[year]
        combined_text = ""

        # 读空白卷（主语料：阅读/完形/语法填空/写作原文）
        if "blank" in pair:
            combined_text += read_file(pair["blank"]) + "\n"

        # 从解析卷提取听力原文（补充语料）
        if "analysis" in pair:
            analysis_text = read_file(pair["analysis"])
            listening = extract_listening_text(analysis_text)
            combined_text += listening + "\n"

        words = clean_and_tokenize(combined_text)
        year_words[year] = words
        print(f"  {year}: {len(words):,} 个有效词（含重复）")

    if not year_words:
        print("[错误] 没有成功读取任何试卷，请检查路径和文件格式")
        return

    # ── 步骤3：词频统计 ────────────────────────────────────
    print("\n【步骤3】词频统计...")
    total_counter = Counter()
    year_counter = {}
    for year, words in year_words.items():
        c = Counter(words)
        year_counter[year] = c
        total_counter.update(c)

    total_years = len(year_words)
    print(f"  全部语料共 {sum(total_counter.values()):,} 词次（含重复）")
    print(f"  不重复词形 {len(total_counter):,} 个")

    # ── 步骤4：交叉分析 ───────────────────────────────────
    print("\n【步骤4】与3500词汇表交叉分析...")
    results = []
    for vocab_word in vocab_set:
        lemma = lemmatize(vocab_word)
        # 同时查原形和词根（避免重复计数但保证不漏）
        keys = {vocab_word, lemma}

        total_freq = sum(total_counter.get(k, 0) for k in keys)
        years_appeared = sum(
            1 for y in year_counter
            if any(year_counter[y].get(k, 0) > 0 for k in keys)
        )
        avg_per_year = round(total_freq / total_years, 2)

        results.append({
            "word":         vocab_word,
            "total_freq":   total_freq,
            "years_count":  years_appeared,
            "avg_per_year": avg_per_year,
        })

    # 去重：如果词汇表里同时有 say 和 saying，合并到词根，删除派生词条目
    # 建立词根到词条的映射
    lemma_to_vocab = {}
    for r in results:
        lm = lemmatize(r["word"])
        if lm not in lemma_to_vocab:
            lemma_to_vocab[lm] = r["word"]

    # 标记需要合并的词条（派生词且词根也在词汇表中）
    to_remove = set()
    for r in results:
        lm = lemmatize(r["word"])
        if lm != r["word"] and lm in vocab_set:
            # 把频次合并到词根
            root = next((x for x in results if x["word"] == lm), None)
            if root:
                root["total_freq"] += r["total_freq"]
                root["years_count"] = max(root["years_count"], r["years_count"])
                root["avg_per_year"] = round(root["total_freq"] / total_years, 2)
                to_remove.add(r["word"])

    results = [r for r in results if r["word"] not in to_remove]

    # 排序：先按出现年数降序，再按总频次降序
    results.sort(key=lambda x: (-x["years_count"], -x["total_freq"]))

    # ── 步骤5：划分高频词 ─────────────────────────────────
    appeared   = [r for r in results if r["total_freq"] > 0]
    high_freq  = [r for r in results
                  if r["years_count"] >= HIGH_FREQ_MIN_YEARS
                  or r["total_freq"]  >= HIGH_FREQ_MIN_COUNT]

    print(f"\n  3500词中在高考出现过: {len(appeared)}/{len(vocab_set)} "
          f"({len(appeared)/len(vocab_set)*100:.1f}%)")
    print(f"  从未出现: {len(vocab_set) - len(appeared)} 个")
    print(f"  高频词 (出现≥{HIGH_FREQ_MIN_YEARS}年 或 总频次≥{HIGH_FREQ_MIN_COUNT}次): "
          f"{len(high_freq)} 个")

    # ── 控制台预览 TOP 60 ─────────────────────────────────
    print(f"\n{'─'*68}")
    print(f"TOP 60 高频考纲词")
    print(f"{'─'*68}")
    print(f"{'排名':<5} {'单词':<20} {'总频次':<8} {'出现年数':<10} {'年均':<8} 出现分布")
    print(f"{'─'*68}")
    for i, r in enumerate(results[:60], 1):
        bar = "█" * r["years_count"] + "░" * (total_years - r["years_count"])
        print(f"{i:<5} {r['word']:<20} {r['total_freq']:<8} "
              f"{r['years_count']:<4}/{total_years}  {r['avg_per_year']:<8} {bar}")

    # ── 步骤6：输出 CSV ───────────────────────────────────
    print("\n【步骤6】保存结果...")

    # 完整表：所有3500词
    full_csv = "results_full.csv"
    with open(full_csv, "w", encoding="utf-8-sig") as f:
        f.write("排名,单词,总频次,出现年数,年均频次,高频标记\n")
        for i, r in enumerate(results, 1):
            is_hf = "★高频" if (r["years_count"] >= HIGH_FREQ_MIN_YEARS
                                or r["total_freq"] >= HIGH_FREQ_MIN_COUNT) else ""
            f.write(f"{i},{r['word']},{r['total_freq']},"
                    f"{r['years_count']}/{total_years},{r['avg_per_year']},{is_hf}\n")
    print(f"  → {full_csv}  （{len(results)} 条，所有3500词完整排名）")

    # 高频词表：直接可用于备考
    hf_csv = "results_highfreq.csv"
    with open(hf_csv, "w", encoding="utf-8-sig") as f:
        f.write("排名,单词,总频次,出现年数,年均频次\n")
        for i, r in enumerate(high_freq, 1):
            f.write(f"{i},{r['word']},{r['total_freq']},"
                    f"{r['years_count']}/{total_years},{r['avg_per_year']}\n")
    print(f"  → {hf_csv}  （{len(high_freq)} 条，高频词表）")

    # JSON备份（含每年分项数据，方便后续扩展分析）
    json_file = "results_raw.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "config": {
                "high_freq_min_years": HIGH_FREQ_MIN_YEARS,
                "high_freq_min_count": HIGH_FREQ_MIN_COUNT,
            },
            "summary": {
                "vocab_size":       len(vocab_set),
                "years_analyzed":   sorted(year_words.keys()),
                "total_years":      total_years,
                "words_appeared":   len(appeared),
                "high_freq_count":  len(high_freq),
            },
            "per_year_word_count": {str(y): len(w) for y, w in year_words.items()},
            "all_results":         results,
            "high_freq_words":     high_freq,
        }, f, ensure_ascii=False, indent=2)
    print(f"  → {json_file}  （完整原始数据，含每年分项）")

    print("\n✓ 分析完成！")
    print(f"  下一步建议：打开 {hf_csv}，即为高频词备考列表")


if __name__ == "__main__":
    main()