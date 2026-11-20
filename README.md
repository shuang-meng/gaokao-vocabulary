# 高考英语词汇表：按真题频次排序

把课标词汇表的 3100 个词，放回 2008–2026 年高考英语全国 I 卷系列的真题里统计：每个词考了多少年、多少次，在真题里怎么用（例句、搭配、词性）。按"出现年数 → 总次数"排序，分章印刷，让学生先从真正高频的词开始背。

## 成品
- `output/gaokao_vocab_full.pdf`：A4 打印版，每页 6–9 个词，共 6 章（核心 / 高频 / 中频 / 常考 / 偶考 / 真题未出现）。
- `data/processed/entries_with_defs.csv`：全部词条数据，可导入 Excel 或 Anki。
- `data/processed/word_freq.csv`：词频明细（分题型、分试卷线、近年频次）。
- `data/processed/coverage_curve.csv`：背完前 N 个词能覆盖真题多少词次。

## 数据来源
见 `ATTRIBUTION.md`。真题原文不在仓库中（版权），需要自行准备，放到 `试卷/`，按 `papers.csv` 的命名规则命名。

## 运行（macOS）
```bash
# 1. 环境（一次性）
brew install poppler pango                    # pdftotext；WeasyPrint 需要 pango
brew install --cask libreoffice               # 转换 .doc 试卷（没有时退回 macOS textutil，未测试）
conda create -n gaokao python=3.12 -y && conda activate gaokao
pip install -r requirements.txt
python -m spacy download en_core_web_sm
# conda 环境里的 WeasyPrint 找不到 Homebrew 的库时（报 cannot load library 'libgobject-2.0-0'）：
conda env config vars set DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"
conda deactivate && conda activate gaokao

# 2. 准备材料
#   试卷/      真题文件，按 papers.csv 命名（不随仓库分发）
#   sources/   kebiao_2017_2025.pdf（课标）、kaogang_3500.pdf（考纲，只用附录的数词/月份/星期）
git clone --depth 1 https://github.com/skywind3000/ECDICT.git ../ECDICT
git clone --depth 1 https://github.com/globalwordnet/english-wordnet.git ../english-wordnet

# 3. 可选：Wiktionary（下载 kaikki.org 的英文 JSONL，约数 GB）
python scripts/05b_extract_wiktionary.py <kaikki.org-dictionary-English.jsonl> data/processed/vocab_kb2025.csv data/external/wiktionary.csv

# 4. 一键运行
bash run_all.sh
```
各步骤的输入输出见 `run_all.sh` 和每个脚本开头的说明。

## 统计口径（摘要）
- 完形和语法填空先用答案回填，再计数；完形选项单独记一栏，不进主词频。
- 解析、范文不计入；人名地名不计入。
- 一年有两份卷子（2008、2021–2023）时，"出现年数"按年份去重。
- 派生词（actually、writer）不算进基础词，只在词条里列出。
- 句素由依存句法自动抽取，有少量误抽，需要人工审读。

## 许可
代码：MIT。词汇表数据与排版成品：CC BY-SA 4.0。
