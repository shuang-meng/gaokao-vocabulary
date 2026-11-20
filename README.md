# 高考英语词汇表：按真题频次排序

> **English summary.** A frequency-ranked vocabulary list for the Chinese national college entrance exam (gaokao) in English. The 3,100 words of the official 2017/2025 curriculum list are counted against 23 national exam papers (2008–2026, ~79k tokens excluding names): years appeared, total count, part of speech, collocations and real exam sentences. The 1,000 most frequent words cover 85% of exam text; for their 874 content words, senses were written from scratch (Chinese gloss + plain-English definition + one exam sentence per sense), keeping only the senses the exams actually use. Pipeline: Python, spaCy, pdfplumber, WeasyPrint. Code MIT; data CC BY-SA 4.0. Exam papers themselves are not distributed.

把课标词汇表的 3100 个词，放回 2008–2026 年高考英语全国 I 卷系列的真题里统计：每个词考了多少年、多少次，在真题里怎么用（例句、搭配、词性）。按"出现年数 → 总次数"排序，分章印刷，让学生先从真正高频的词开始背。

## 主要结果
| 章 | 排名 | 累计覆盖真题词次 |
|---|---|---|
| 1 核心词 | 1–200 | 64.4% |
| 2 高频词 | 201–500 | 76.4% |
| 3 中频词 | 501–1000 | 85.1% |
| 4 常考词 | 1001–1600 | 89.8% |
| 5 偶考词 | 1601–2552 | 92.2% |
| 6 真题未出现 | 754 词 | — |

覆盖率的分母是不含人名地名的真题词次（79,484；2008 年两卷共用的句子只算一次）。背完前 200 个词，就能认出真题里近三分之二的词次。

## 成品
- `output/gaokao_vocab_full.pdf`：A4 打印版，每页 6–9 个词，共 6 章（核心 / 高频 / 中频 / 常考 / 偶考 / 真题未出现）。
- `data/processed/entries_with_defs.csv`：全部词条数据，可导入 Excel 或 Anki。
- `data/processed/senses.csv`：前 1000 名实词的"真题义项"（876 词、1725 个义项），每个义项有中文、简明英文和一句真题原句。
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
python scripts/05b_extract_wiktionary.py <kaikki 英文 .jsonl 或 .jsonl.gz> data/processed/vocab_kb2025.csv data/external/wiktionary   # 生成 .jsonl 和 .csv

# 4. 一键运行
bash run_all.sh
```
各步骤的输入输出见 `run_all.sh` 和每个脚本开头的说明。

## 真题义项（前 1000 名）
- 每个词从真题中固定抽样 8–12 句（`scripts/07a_sense_samples.py`，可复现），人工判断每句用的是哪个义项，只保留真题用到的义项，按抽样中的出现次数排序。
- 义项写在 `data/manual/senses/*.json`，格式：`"词": [[词性, 中文, 简明英文, 抽样命中数, 例句序号], ...]`。中文和英文释义为本项目自编，未使用商业词典内容。
- `scripts/07b_build_senses.py` 合并为 `data/processed/senses.csv`，排版时用它替换原来的词典释义。
- 局限：排序依据是抽样，不是全量计数；义项尚未经第二人审读。发现错误欢迎提 Issue，或直接改 JSON 提交 Pull Request。

## 统计口径（摘要）
- 完形和语法填空先用答案回填，再计数；完形选项单独记一栏，不进主词频。
- 解析、范文不计入；人名地名不计入。
- 一年有两份卷子（2008、2021–2023）时，"出现年数"按年份去重；两卷共用的句子（2008 年的听力、单选和部分阅读、完形）只计一次（`scripts/02e_dedupe_same_year.py`）。
- 派生词（actually、writer）不算进基础词，只在词条里列出。
- 句素由依存句法自动抽取，有少量误抽，需要人工审读。

## 已知问题
- 2008 年新课标卷没有听力原文；2020 年听力原文不全；2021 年新高考 I 卷为 OCR 版本，有少量错字。
- 少数词形还原误差：如 better/best 同时计入 good 和 well，leaves（离开）计入 leaf。
- 功能词（the、that、do 等 126 个）还没有写义项；记忆法尚未加入。

## 许可
代码：MIT。词汇表数据与排版成品：CC BY-SA 4.0。
