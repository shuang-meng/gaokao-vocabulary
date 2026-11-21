# 高考英语词汇表：按真题频次和义项排序

> **English summary.** A vocabulary list for the Chinese national college entrance exam (gaokao) in English, built from the exams themselves. The 3,100 words of the official 2017/2025 curriculum list are counted against 23 national exam papers (2008–2026, ~79k tokens excluding names). Beyond word frequency, every occurrence of every word that appears in the exams (~39,000 occurrences of 2,441 words) was labelled with its **sense** by Claude models, with a second model checking uncertain labels and a human deciding the hardest cases. The book shows, for each word: sense shares, idioms and grammatical phrases, whether the word was a cloze / grammar-fill answer, exam meanings beyond the familiar one (hand-checked), and real exam sentences. Two findings: knowing only the first sense of the top 1,000 words covers 73% of exam usage, not the 85% a word count suggests; and since the 2024 reform a ranking built on older papers still works but needs ~1,600 words to reach the coverage 1,000 words used to give. Code MIT; data CC BY-SA 4.0. Exam papers are not distributed.

把课标词汇表的 3100 个词，放回 2008–2026 年高考英语全国 I 卷系列的真题里统计：每个词考了多少年、多少次；更进一步，**每一次出现用的是哪个意思**、在不在短语里、有没有被当作完形或语法填空的答案。按"出现年数 → 总次数"排序，分章印刷，让学生先从真正高频的词和义项开始背。

## 主要结果

**按单词**
| 章 | 排名 | 累计覆盖真题词次 |
|---|---|---|
| 1 核心词 | 1–200 | 64.4% |
| 2 高频词 | 201–500 | 76.4% |
| 3 中频词 | 501–1000 | 85.1% |
| 4 常考词 | 1001–1600 | 89.8% |
| 5 偶考词 | 1601–2552 | 92.2% |
| 6 真题未出现 | 754 词 | — |

覆盖率的分母是不含人名地名的真题词次（79,484；2008 年两卷共用的句子只算一次）。

**按义项**：认识一个词，通常只认识它的第一个意思。只把用到第一义项的地方算作"读懂"，短语里的用法也不算：

| 背前 N 词 | 按单词 | 只会第一义项 | 会前两个义项 |
|---|---|---|---|
| 500 | 76.4% | 65.5% | 70.9% |
| 1000 | 85.1% | 72.6% | 79.0% |
| 1600 | 89.8% | 76.3% | 83.4% |

**其他发现**
- 一半左右的多义词，第一义项占真题用法的 59% 以上；另有约 160 个词没有一个义项超过一半，必须分义项学。
- 功能词也有义项问题：while 有 40% 是"然而"，since 有 26% 是"因为"，until 有 30% 是 not…until"直到…才"。
- 完形填空的正确答案中，约四分之一排在 1000 名以后，比如 principle、deserve、mature、complain。
- 2024 年新结构以来，单项选择和短文改错取消，写作材料（应用文、读后续写原文）的比重从 2% 升到 11%，选择性必修词的占比从 2.4% 升到 4.1%。只用 2008–2023 年数据排出的前 1000 词，覆盖新卷 88%，覆盖旧卷 93%。要背到约 1600 词，才达到过去背 1000 词的水平。

## 成品
- `output/gaokao_vocab_full.pdf`：A4 打印版，约 420 页。依次是封面（含覆盖率表）、前言（2024 年以来的变化）、6 章正文、附录（熟词生义）。每个词条包括：
  - 义项：按全量次数排序，标出占比；
  - 短语：附中文和出现次数；
  - "考点"标签：当过完形或语法填空的答案；
  - "生义"标签：常见义之外、真题用到的意思；
  - 分布：在短语中的比例、出现的篇数、听力占比、是否集中在单篇文章。
- `data/processed/`（都可以导入 Excel 或 Anki）：
  - `entries_with_defs.csv`：全部词条；`word_freq.csv`：分题型、分试卷线的词频
  - `senses_full.csv`：每个义项的全量次数、占比、年数、篇数，附一句例句（2,420 词，3,961 个义项）
  - `sense_freq.csv`、`word_sense_metrics.csv`：义项频率与每个词的指标（首义项占比、短语占比、篇数、听力占比、最大单篇占比）
  - `phrase_entries.csv`：短语（习语 / 功能短语），附次数、年数，以及"如果把它当成一个词，排第几名"
  - `tested_words.csv`：完形和语法填空的答案词
  - `rare_senses.csv`：熟词生义（368 处，已人工核对）
  - `sense_coverage.csv`：按义项算的覆盖率
  - `trend_words.csv`、`trend_sections.csv`、`trend_holdout.csv`：2024 年前后的比较

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
python scripts/05b_extract_wiktionary.py <kaikki 英文 .jsonl 或 .jsonl.gz> data/processed/vocab_kb2025.csv data/external/wiktionary

# 4. 一键运行（义项标注已存在时自动汇总并按义项排版；标注本身见下一节）
bash run_all.sh
```
各步骤的输入输出见 `run_all.sh` 和每个脚本开头的说明。

## 义项标注（第 8 步，需要 Anthropic API）
API key 只放在环境变量里，比如 `conda env config vars set ANTHROPIC_API_KEY=...`，不要写进任何文件。所有标注都走 Message Batches API（半价），整个项目累计花费约 7 美元。

1. **义项清单**：前 1000 名的实词按抽样句自编义项清单（`data/manual/senses/*.json`）；21 个关键功能词另写一份（`func.json`）。
2. **第一轮标注**：`scripts/08_annotate_senses.py`（Claude Sonnet）逐句给出义项编号、严格意义的短语和把握程度（h/m/l）。1001 名以后的低频词用 `scripts/08h_rare_words.py`：模型先列出这个词在真题里用到的义项，并区分常见义和非常见义，再逐句标注。
3. **校准**：30 个试点词共 953 处人工标注。第一轮与人工的一致率 94.7%（kappa 0.946）；模型说 h 时 99% 正确，说 m 时只有 68%。
4. **第二轮复核**：`scripts/08d_second_pass.py`（Claude Opus）在不看第一轮答案的情况下，重标所有 m/l 的行，并给长尾短语分类。用 135 句人工标注过的难句校准：两轮一致时 96% 正确；分歧时如果 Opus 有把握（h），31 句全对。规则据此确定：两轮一致就接受，Opus 有把握就采用 Opus，其余交给人工。人工判了 145 句，其中 77% 与 Opus 一致，与 Sonnet 一致的只有 17%，所以之后的轮次分歧一律采用 Opus。
5. **归并与清理**（都在 `data/manual/`，人可直接修改）：
   - `new_sense_map.csv`：模型提出的新义项，归入已有义项、新增、改判为短语或删除；
   - `sense_merges.csv`：学生分不出区别的义项合并；
   - `phrase_classes.csv`：短语四分类，人工优先，模型分类作补充；
   - `phrase_aliases.csv`：同一短语的不同写法合并；
   - `phrase_glosses.csv`：短语中文释义，本项目自编；
   - `rare_senses_review.csv`：熟词生义的人工核对记录。
6. **汇总与成品**：`08c_aggregate.py` → `08f_build_full_senses.py` → `09a`–`09e`（考点、覆盖率、熟词生义、2024 年趋势）→ `06_render_print.py`。

**严格短语标准**：只收意思不能从字面推出的习语和短语动词（take place、give up），以及语法和话语块（have to、so that、you know），后者单列为"功能短语"。透明搭配（look at、high school）退回到词义。小词（away、up、out）的判断方法是：动词本义加小词字面意思，如果能拼出句意（take away 拿走），就不算短语。

`scripts/08g_dossier.py` 会生成单词档案 `output/dossier_all.html`，按义项列出每个词在真题里的全部原句，约 3.9 万句。**它包含大量真题原文，只供个人研究，已被 .gitignore 排除，请勿公开。**

## 统计口径（摘要）
- 完形和语法填空先用答案回填，再计数；完形选项单独记一栏，不进主词频。
- 解析、范文不计入；人名地名不计入。
- 一年有两份卷子（2008、2021–2023）时，"出现年数"按年份去重；两卷共用的句子只计一次（`scripts/02e_dedupe_same_year.py`）。
- 派生词（actually、writer）不算进基础词，只在词条里列出。
- 义项占比的分母是这个词全部标注过的出现，包括短语里的出现。
- 2024 年前后比较时只用正文，不含题干和选项，因为不少年份的听力题干和选项没有收录。判定"增多"的条件是：对数似然检验 p < 0.01，频率至少翻倍，并且在 2024–2026 年中至少两年出现。
- 句素由依存句法自动抽取，有少量误抽，需要人工审读。

## 已知问题
- 2008 年新课标卷没有听力原文；2020 年听力原文不全；2021 年新高考 I 卷为 OCR 版本，有少量错字；多数年份缺少听力题干和选项。
- 少数词形还原误差：如 better/best 同时计入 good 和 well。
- 义项标注主要由模型完成。抽查和校准显示准确率在九成以上，但没有逐句人工审读；熟词生义附录已逐条人工核对。account 的"占比例"和"解释"两个义项还没拆开。
- 2024 年以来只有 3 份试卷，话题变化只作提示，不作结论。
- 句素未经人工审读；记忆法尚未加入。发现错误欢迎提 Issue，或直接修改 `data/manual/` 下的文件提交 Pull Request。

## 许可
代码：MIT。词汇表数据与排版成品：CC BY-SA 4.0。
