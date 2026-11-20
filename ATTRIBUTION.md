# 数据来源与许可 / Sources and licences

本项目的代码以 MIT 许可发布；生成的词汇表数据（data/processed/ 下的 CSV 及排版成品）以 CC BY-SA 4.0 发布。

| 数据 | 来源 | 许可 | 用途 |
|---|---|---|---|
| 词汇表 | 《普通高中英语课程标准（2017年版2025年修订）》附录2 词汇表，中华人民共和国教育部制定 | 政府发布的课程文件 | 词头与级别（义务教育 / 必修 / 选择性必修） |
| 数词、月份、星期 | 普通高等学校招生全国统一考试大纲（英语）附录5 | 政府发布的考试文件 | 课标词表未单列的基础词 |
| 中文释义、音标、柯林斯星级、牛津3000标记、词形变化、词根词缀 | ECDICT, https://github.com/skywind3000/ECDICT | MIT | 第5步 |
| 英文释义及例句 | Open English WordNet, https://github.com/globalwordnet/english-wordnet | CC BY 4.0 | 第5步 |
| 词源、IPA（可选） | Wiktionary，经 wiktextract / kaikki.org 提取 | CC BY-SA 4.0 | 第5b步 |
| 真题义项、简明英文释义 | 本项目自编（`data/manual/senses/`） | CC BY-SA 4.0 | 第5b步 |
| 词形还原、句法分析 | spaCy en_core_web_sm | MIT | 第3–4步 |
| 真题例句 | 历年高考英语全国卷（短句引用，注明年份与卷别） | 原文版权归命题方；仓库不包含试卷全文 | 第4步 |
