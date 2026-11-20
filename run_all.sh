#!/usr/bin/env bash
# 从头跑完整个流程。用法：bash run_all.sh
# 先按 README 准备好：试卷/、sources/ 里的两个 PDF、../ECDICT、../english-wordnet
set -euo pipefail
cd "$(dirname "$0")"

# macOS: SIP strips DYLD_* variables when /bin/bash starts, so WeasyPrint (step 6) cannot find
# Homebrew's pango/gobject. Re-export the Homebrew library path inside the script.
if [[ "$(uname)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
  export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
fi

KB_PDF="sources/kebiao_2017_2025.pdf"        # 《普通高中英语课程标准（2017年版2025年修订）》
KG_PDF="sources/kaogang_3500.pdf"            # 考试大纲 3500 词（只用附录里的数词/月份/星期）
ECDICT="../ECDICT"
OEWN="../english-wordnet/src/yaml"
WIKT="data/external/wiktionary.csv"          # 可选：scripts/05b 在本机生成
P=data/processed; I=data/interim
mkdir -p $P $I output

echo "== 1 词表"
python scripts/01d_parse_curriculum_vocab.py "$KB_PDF" $P/vocab_kb2025.csv $P/vocab_kb2025_countries.csv
python scripts/01c_parse_vocab_supplement.py "$KG_PDF" $P/vocab_supplement.csv
python scripts/01e_build_supplement_kb2025.py $P/vocab_kb2025_countries.csv $P/vocab_supplement.csv $P/vocab_kb2025_supplement.csv

echo "== 2 真题清洗"
python scripts/02a_convert_papers.py 试卷 $I/raw_text
python scripts/02b_segment_papers.py $I/raw_text $I/segments
python scripts/02c_fill_blanks.py $I/segments $I/corpus > $I/fill_report.tsv
python scripts/02d_build_corpus.py $I/corpus papers.csv $I/corpus_all.tsv
python scripts/qa_segments.py $I/segments > $I/segment_report.tsv

echo "== 3 词频"
V="$P/vocab_kb2025.csv $P/vocab_kb2025_supplement.csv"
python scripts/03_count_frequency.py $I/corpus_all.tsv $V $P
echo "== 4 例句与句素"
python scripts/04_examples_collocations.py $I/corpus_all.tsv $V $P
echo "== 5 释义"
python scripts/05_add_definitions.py $P/entries.csv "$ECDICT/ecdict.csv" "$OEWN" "$ECDICT/wordroot.txt" $P/entries_with_defs.csv $( [ -f "$WIKT" ] && echo "$WIKT" )
echo "== 5b 义项（人工编写，data/manual/senses/）"
python scripts/07a_sense_samples.py $I/occurrences.tsv $P/entries_with_defs.csv $I/sense_samples_1_1000.json 1 1000
python scripts/07b_build_senses.py data/manual/senses $I/sense_samples_1_1000.json $P/senses.csv
echo "== 6 排版"
python scripts/06_render_print.py $P/entries_with_defs.csv $P/token_totals.json output/gaokao_vocab_full --senses $P/senses.csv
echo "完成：output/gaokao_vocab_full.pdf"
