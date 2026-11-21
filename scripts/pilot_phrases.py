# -*- coding: utf-8 -*-
"""Split annotated occurrences into word senses and phrase entries (pilot, 30 words).

usage: python scripts/pilot_phrases.py data/pilot/full/occ_labeled.csv data/processed/entries_with_defs.csv data/pilot/full/
A phrase rule = (sense ids or None, phrase, Chinese gloss, kind, regex). {s} in the regex is the
surface form of the head word in that sentence. An occurrence becomes a phrase occurrence when its
annotated sense is in the rule's set and the regex matches the sentence (case ignored).
kind: 短语动词 (phrasal verb) / 习语 (idiom or fixed expression) / 复合词 (compound).
"""
import collections, csv, json, re, sys

R = {
 'draw': [({3}, 'draw on', '借鉴；利用', '短语动词', r'\b{s}\s+on\b'),
          ({4}, 'draw near', '（时间）临近', '短语动词', r'\b{s}\s+near\b'),
          ({6}, 'be drawn from', '取自；出自', '短语动词', r'\b{s}\s+(\w+\s+)?from\b'),
          ({1}, 'draw attention to', '引起对…的注意', '习语', r'\b{s}\b.{0,30}\battention\b')],
 'run': [({4}, 'run into', '撞上', '短语动词', r'\b{s}\s+into\b'),
         ({12}, 'run ahead of', '远远超过', '短语动词', r'\b{s}\s+(far\s+)?ahead\b'),
         ({11}, 'run-down', '疲惫的', '复合词', r'\b{s}-down\b'),
         ({9}, 'run a red light', '闯红灯', '习语', r'\b{s}\s+a\s+red\s+light\b'),
         ({1}, 'run away', '逃跑', '短语动词', r'\b{s}\s+away\b')],
 'break': [({4}, 'break up', '（关系）破裂；分手', '短语动词', r'\b{s}\s+up\b'),
           ({5}, 'break down', '（机器）出故障', '短语动词', r'\b{s}[\s-]+down\b'),
           ({11}, 'break down', '拆开', '短语动词', r'\b{s}\s+down\b'),
           ({9}, 'ground-breaking', '开创性的', '复合词', r'ground-{s}'),
           ({10}, 'break sb.\'s heart', '使伤心', '习语', r'\b{s}\b.{0,10}\bheart\b')],
 'set': [({1}, 'set up', '建立；搭起；安装', '短语动词', r'\b{s}\s+(\w+\s+)?up\b'),
         ({5}, 'set out / set off', '出发', '短语动词', r'\b{s}\s+(out|off)\b'),
         ({11}, 'set off', '引发', '短语动词', r'\b{s}\s+off\b'),
         ({4}, 'set ... free', '释放', '习语', r'\b{s}\b.{0,15}\bfree\b'),
         ({7}, 'set the table', '摆餐具', '习语', r'\b{s}\s+the\s+table\b'),
         ({8}, 'set aside', '留出', '短语动词', r'\b{s}\s+aside\b'),
         ({9}, 'set ... apart', '使与众不同', '短语动词', r'\b{s}\b.{0,15}\bapart\b'),
         ({12}, 'set the stage for', '为…做好准备', '习语', r'\b{s}\s+the\s+stage\b'),
         ({15}, 'set foot on', '踏上', '习语', r'\b{s}\s+foot\b'),
         ({13}, 'TV set', '电视机', '复合词', r'(tv\s+|box-){s}|{s}\s+tv')],
 'point': [({2}, 'point out', '指出', '短语动词', r'\b{s}\s+out\b'),
           ({2}, 'point to', '表明；指向', '短语动词', r'\b{s}\s+to\b'),
           ({1}, 'at this / some point', '在这时；在某个时候', '习语', r'\bat\s+(this|some)\s+{s}\b'),
           ({1}, 'turning / starting point', '转折点；起点', '复合词', r'\b(turning|starting)\s+{s}\b'),
           ({4}, 'have a point', '有道理', '习语', r'\b(have|see)\s+(a|your)\s+{s}\b'),
           ({6}, 'make it a point to', '务必', '习语', r'\bmade\s+it\s+a\s+{s}\b')],
 'line': [({4}, 'the bottom line', '要点；底线', '习语', r'\bbottom\s+{s}\b'),
          ({3}, 'starting / finish line', '起跑线；终点线', '复合词', r'\b(starting|finish)\s+{s}\b'),
          ({1}, 'power / railway line', '电线；铁路线', '复合词', r'\b(power|railway|rail|electrical)\s+{s}')],
 'open': [({5}, 'be open to', '愿意接受', '习语', r'\b{s}\s+to\b'),
          ({8}, 'open up', '敞开心扉', '短语动词', r'\b{s}\s+up\b'),
          ({3}, 'open office', '开放式办公室', '复合词', r'\b{s}\s+offices?\b')],
 'lead': [({1}, 'lead to', '导致', '短语动词', r'\b{s}\s+(\w+\s+){0,1}to\b'),
          ({5}, 'lead a ... life', '过…的生活', '习语', r'\b{s}\s+a\b.{0,15}\blife\b'),
          ({10}, 'lead author', '第一作者', '复合词', r'\b{s}\s+author\b')],
 'light': [({3}, 'light up', '（脸）发亮', '短语动词', r'\b{s}\s+up\b'),
           ({5}, 'come to light', '被发现', '习语', r'\bto\s+{s}\b'),
           ({1}, 'traffic / red light', '交通灯；红灯', '复合词', r'\b(traffic|red)\s+{s}')],
 'catch': [({3}, 'be caught in / up in', '陷入；遭遇', '短语动词', r'\b{s}\s+(up\s+in|by|in)\b'),
           ({4}, 'catch up with', '赶上；补上', '短语动词', r'\b{s}\s+up\b'),
           ({7}, 'eye-catching', '引人注目的', '复合词', r'eye-{s}'),
           ({9}, 'be caught out', '被识破', '短语动词', r'\b{s}\s+out\b'),
           ({10}, 'catch fire', '着火', '习语', r'\b{s}\s+fire\b'),
           ({11}, 'catch on', '流行起来', '短语动词', r'\b{s}\s+on\b'),
           ({8}, 'play catch', '玩接球游戏', '习语', r'\bplay\s+{s}\b')],
 'touch': [({2}, 'get / keep in touch', '保持联系', '习语', r'\bin\s+{s}\b'),
           ({3}, 'touch down', '着陆', '短语动词', r'\b{s}\s+down\b'),
           ({6}, 'a touch of', '少许', '习语', r'\ba\s+{s}\s+of\b')],
 'pass': [({5}, 'pass away', '去世', '短语动词', r'\b{s}\s+away\b'),
          ({7}, 'pass up', '放弃（机会）', '短语动词', r'\b{s}\s+up\b'),
          ({1}, 'pass on', '传递', '短语动词', r'\b{s}\s+on\b'),
          ({3}, 'pass by', '经过', '短语动词', r'\b{s}\s+by\b')],
 'key': [({1}, 'the key to', '…的关键', '习语', r'\b{s}\s+to\b')],
 'top': [({4}, 'the cherry on top', '锦上添花', '习语', r'cherry\s+on\s+{s}'),
         ({2}, 'on top of / at the top', '在…顶上', '习语', r'\b(on|at\s+the)\s+{s}\b')],
 'drive': [({3}, 'drive out', '驱逐', '短语动词', r'\b{s}\s+out\b'),
           ({5}, 'drive sb. crazy', '使人发疯', '习语', r'\b{s}\b.{0,20}\bcrazy\b'),
           ({4}, 'data-driven / be driven by', '由…驱动', '复合词', r'-{s}|\b{s}\s+by\b')],
 'stand': [({2}, 'stand for', '代表', '短语动词', r'\b{s}\s+for\b'),
           ({5}, 'stand up', '挺身而出', '短语动词', r'\b{s}\s+up\b'),
           ({6}, 'stand as', '作为…而存在', '短语动词', r'\b{s}\s+as\b'),
           ({4}, 'tray stand', '托盘架', '复合词', r'\btray\s+{s}\b')],
 'hold': [({5, 7}, 'hold back', '忍住；阻碍', '短语动词', r'\b{s}\b.{0,10}\bback\b'),
          ({6}, 'get hold of', '抓住；拿到', '习语', r'\bgot\s+{s}\s+of\b|\bget\s+{s}\s+of\b'),
          ({9}, 'hold on to', '紧抓不放', '短语动词', r'\b{s}\s+on\s+to\b')],
 'face': [({3}, 'face-to-face', '面对面的', '复合词', r'\bface[\s-]+to\b'),
          ({1}, 'be faced with', '面临', '短语动词', r'\b{s}\s+with\b')],
 'carry': [({2}, 'carry out', '开展；实施', '短语动词', r'\b{s}\s+(\w+\s+)?out\b|\b{s}\b.{0,25}\bfurther\b'),
           ({3}, 'carry on', '继续', '短语动词', r'\b{s}\s+on\b'),
           ({6}, 'carry over', '延续到', '短语动词', r'\b{s}\s+over\b'),
           ({4}, 'carry weight', '有分量', '习语', r'\b{s}\b.{0,15}\bweight\b')],
 'return': [({4}, 'in return', '作为回报', '习语', r'\bin\s+{s}\b')],
 'form': [({1}, 'in the form of / in ... form', '以…形式', '习语', r'\bin\s+(the\s+)?(\w+\s+)?{s}\b')],
 'order': [({4}, 'in order to', '为了', '习语', r'\bin\s+{s}\s+to\b'),
           ({3}, 'out of order / in order', '坏了；整齐', '习语', r'\b(out\s+of|in)\s+{s}\b'),
           ({6}, 'in order', '按顺序', '习语', r'\bin\s+{s}\b')],
 'course': [({2}, 'of course', '当然', '习语', r'\bof\s+{s}\b')],
 'miss': [({4}, 'miss out on', '错过（好事）', '短语动词', r'\b{s}\s+out\b'),
          ({5}, 'hit-and-miss', '时好时坏的', '复合词', r'hit-and-{s}')],
 'deal': [({1}, 'deal with', '处理；应对', '短语动词', r'\b{s}\s+with\b'),
          ({3}, 'a big deal', '大事', '习语', r'\bbig\s+{s}\b'),
          ({4}, 'a great deal', '大量', '习语', r'\bgreat\s+{s}\b'),
          ({2}, 'a good deal', '划算的交易', '习语', r'\bgood\s+{s}\b|\bbest\s+{s}s?\b'),
          ({5}, 'the real deal', '真货', '习语', r'\breal\s+{s}\b')],
}


def main(occ_csv, entries_csv, outdir):
    rows = [r for r in csv.DictReader(open(occ_csv, encoding='utf-8-sig')) if r['sense'] != 'X']
    E = list(csv.DictReader(open(entries_csv, encoding='utf-8-sig')))
    out = []
    for r in rows:
        unit = None
        for senses, ph, zh, kind, pat in R.get(r['word'], []):
            if senses is not None and int(r['sense']) not in senses:
                continue
            if re.search(pat.replace('{s}', re.escape(r['surface'].lower())), r['sentence'].lower()):
                unit = (kind, ph, zh)
                break
        r = dict(r, unit_kind=unit[0] if unit else '单词义项', unit=unit[1] if unit else r['word'],
                 unit_zh=unit[2] if unit else r['sense_name'])
        out.append(r)
    xs = [dict(r, unit_kind='', unit='', unit_zh='') for r in csv.DictReader(open(occ_csv, encoding='utf-8-sig')) if r['sense'] == 'X']
    with open(outdir + '/occ_units.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out + xs)

    # phrase entries vs. the word ranking (years appeared, then total count)
    ranking = sorted(((int(e['years_count']), int(e['total_count']), e['headword']) for e in E if e['total_count'] and int(e['total_count']) > 0), reverse=True)
    def eq_rank(y, n):
        return 1 + sum(1 for yy, nn, _ in ranking if (yy, nn) > (y, n))
    ph = collections.defaultdict(list)
    for r in out:
        if r['unit_kind'] != '单词义项':
            ph[(r['unit'], r['unit_zh'], r['unit_kind'], r['word'])].append(r)
    rank = {e['headword']: int(e['rank']) for e in E if e['rank']}
    table = []
    for (u, zh, kind, w), rs in ph.items():
        y = len({r['year'] for r in rs}); n = len(rs)
        lis = sum(1 for r in rs if r['section'] == 'listening')
        table.append({'phrase': u, 'zh': zh, 'kind': kind, 'head': w, 'head_rank': rank[w], 'count': n, 'years': y,
                      'listening': lis, 'equiv_rank': eq_rank(y, n)})
    table.sort(key=lambda t: (-t['years'], -t['count']))
    with open(outdir + '/phrases.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(table[0].keys())); w.writeheader(); w.writerows(table)
    share = collections.defaultdict(lambda: [0, 0])
    for r in out:
        share[r['word']][0] += 1; share[r['word']][1] += r['unit_kind'] != '单词义项'
    json.dump({'phrase_share': share}, open(outdir + '/phrase_share.json', 'w'), ensure_ascii=False)
    tot = sum(v[1] for v in share.values()); allr = sum(v[0] for v in share.values())
    print(f'{len(table)} phrase entries; {tot}/{allr} occurrences ({tot / allr:.1%}) are inside phrases')
    for t in table[:25]:
        print(f"{t['phrase']:28} {t['kind']:5} {t['count']:3}次 {t['years']:2}年  词条排名≈{t['equiv_rank']:5}  (中心词 {t['head']} 排 {t['head_rank']})  听力{t['listening']}")
    print('phrase share by word:', sorted(((round(v[1] / v[0], 2), k) for k, v in share.items()), reverse=True)[:12])


if __name__ == '__main__':
    main(*sys.argv[1:4])
