# -*- coding: utf-8 -*-
"""Definition-upgrade pilot: 30 polysemous words from chapter 2.

Senses are hand-written (our own wording). Each one is matched to a real exam
sentence taken from pilot_input.json. `n` is the number of sentences in the
sample of 12-14 that use this sense. It is a sample count, not a full count.
Writes pilot_entries.csv and pilot_compare.html.
"""
import csv, json, sys, html

SEC = {'list': '听力', 'read': '阅读', 'cloz': '完形', 'gram': '语法填空',
       'seve': '七选五', 'writ': '写作', 'corr': '改错'}

# word: [(pos, zh, en, n, year, key_substring), ...]
P = {
'draw': [
 ('v.', '吸引（注意、兴趣）', 'to make someone notice or come to something', 6, 2021, 'Drawing public attention'),
 ('v.', '画', 'to make a picture with a pen or pencil', 2, 2014, 'draw a picture'),
 ('v.', '借鉴；利用 (draw on)', 'to use something you have, such as knowledge or experience', 2, 2023, 'draw on an experiment'),
 ('v.', '（时间）临近 (draw near)', 'to come closer in time', 1, 2025, 'drew near'),
 ('v.', '提取（钱）', 'to take money out of a bank', 1, 2009, 'draw some money')],
'run': [
 ('v./n.', '跑；跑步', 'to move fast on your feet', 7, 2024, 'I ran back'),
 ('v.', '经营；管理', 'to be in charge of a business or activity', 3, 2020, 'run her own business'),
 ('v.', '（液体）流', 'to flow', 1, 2017, 'run down'),
 ('v.', '撞上 (run into)', 'to hit something by accident while moving', 1, 2010, 'ran into a lorry')],
'break': [
 ('n.', '休息；假期', 'a short rest, or a holiday from school or work', 3, 2025, 'Need a break'),
 ('v.', '打破（纪录）；违反（规则）；改掉（习惯）', 'to do better than a record, or not follow a rule or habit', 3, 2022, 'world record'),
 ('v.', '破解（密码）', 'to find the meaning of a secret code', 2, 2016, 'break a code'),
 ('v.', '（关系）破裂 (break up)', 'to end a relationship', 2, 2021, 'fade or break'),
 ('v.', '（机器）出故障 (break down)', 'to stop working', 1, 2014, 'broke down')],
'set': [
 ('v.', '建立；搭起 (set up)', 'to start something, or put something in place so it is ready', 2, 2015, 'sets up its tents'),
 ('v.', '确定；设定（日期、目标）', 'to decide a date, goal or rule', 3, 2017, 'set April 30 as'),
 ('n.', '一套；一组', 'a group of things that belong together', 2, 2021, 'specific set of skills'),
 ('v.', '释放 (set ... free)', 'to let a person or animal go', 2, 2008, 'set fish free'),
 ('v.', '出发 (set out / set off)', 'to begin a journey', 1, 2026, 'Slovik set'),
 ('v.', '放置；拉上（刹车）', 'to put something in a place or position', 1, 2016, 'set the brake')],
'point': [
 ('n.', '（某个）时刻；阶段 (starting / turning point)', 'a particular moment or stage', 3, 2023, 'turning point'),
 ('v.', '指出 (point out)；表明 (point to)', 'to show or tell that something is true or important', 3, 2008, 'points out'),
 ('n.', '（比赛）分', 'a unit used to count the score in a game', 2, 2025, 'two points'),
 ('n.', '要点；道理', 'the main idea, or a good reason in an argument', 2, 2024, 'You have a point')],
'head': [
 ('v.', '前往；朝…走 (head for / home / off)', 'to go towards a place', 6, 2017, 'headed home'),
 ('n.', '头；头脑', 'the top part of the body; your mind', 4, 2014, 'inside our own head'),
 ('n.', '负责人；领导', 'the person in charge of a group', 1, 2014, 'department heads')],
'line': [
 ('n.', '线路（电线、铁路、电话线）', 'a wire, cable or track that carries power, trains or calls', 4, 2022, 'electrical lines'),
 ('n.', '队；一排', 'people or things in a row, one behind another', 3, 2025, 'line is getting longer'),
 ('n.', '（起跑、终点）线', 'a mark on the ground where a race starts or ends', 2, 2022, 'starting line'),
 ('n.', '要点 (the bottom line)', 'the most important fact', 1, 2020, 'bottom line')],
'open': [
 ('adj./v.', '营业；开门', 'ready for customers or visitors', 5, 2020, 'office is open Monday'),
 ('v.', '打开；张开', 'to move something so it is no longer closed', 3, 2024, 'sepals open'),
 ('adj.', '开放式的；露天的', 'without walls or a cover', 2, 2021, 'an open office'),
 ('v.', '开创；带来（新方式）', 'to make something new possible', 1, 2017, 'it opens'),
 ('adj.', '愿意接受的 (be open to)', 'willing to listen to or try new things', 1, 2009, 'open')],
'lead': [
 ('v.', '导致 (lead to)', 'to cause something to happen', 3, 2022, 'led to new speech'),
 ('v.', '领导；主持（研究、团队）', 'to be in charge of a group or project', 3, 2023, 'study led by'),
 ('v.', '带领；引导', 'to show someone the way, or make them go somewhere', 2, 2025, 'lead the opponent'),
 ('v.', '领先', 'to be first or ahead in a race or competition', 1, 2023, 'led the competition'),
 ('v.', '过（某种生活）(lead a ... life)', 'to live in a particular way', 1, 2009, 'lead a city life')],
'light': [
 ('n.', '灯；光', 'a lamp, or the brightness that lets you see', 7, 2016, 'bright lights on'),
 ('v.', '照亮；点燃', 'to make something bright, or start a fire', 2, 2020, 'light the rooms'),
 ('v.', '（脸）发亮 (light up)', 'to look suddenly happy', 1, 2015, 'lit up'),
 ('adj.', '（颜色）浅的', 'pale, not dark', 1, 2009, 'lighter'),
 ('n.', '被发现 (come to light)', 'to become known', 1, 2026, 'come to light')],
'catch': [
 ('v.', '赶上（车、船、飞机）', 'to get on a train, bus or plane in time', 4, 2012, 'catch the nine'),
 ('v.', '抓住；接住', 'to take hold of something that is moving', 2, 2008, 'catching a fish'),
 ('v.', '遭遇；陷入 (be caught in / up in)', 'to be stopped or trapped by something', 2, 2016, 'caught by a hurricane'),
 ('v.', '追上；补上 (catch up with)', 'to reach the same level as others', 1, 2022, 'catch up with'),
 ('v.', '察觉（气味、声音）', 'to notice a smell or sound', 1, 2021, 'caught the smell')],
'touch': [
 ('v.', '触摸；接触', 'to put your hand or body on something', 3, 2012, 'touch each other'),
 ('n.', '联系 (get / keep in touch)', 'communication with someone', 3, 2025, 'get in touch with my brother'),
 ('v.', '着陆 (touch down)', 'to land on the ground', 2, 2015, 'touched down'),
 ('v.', '感动', 'to make someone feel strong emotion', 1, 2023, 'touch me musically'),
 ('n.', '触觉', 'the sense that tells you how things feel', 1, 2013, 'sense of touch'),
 ('n.', '少许 (a touch of)', 'a small amount', 1, 2023, 'touch of sweetness')],
'pass': [
 ('v.', '传递；传染', 'to give something to another person', 3, 2021, 'pass on a message'),
 ('v.', '通过（考试、法律）', 'to succeed in a test; to make a law official', 3, 2019, 'pass exams'),
 ('v.', '经过', 'to go past someone or something', 2, 2023, 'pass the bookstore'),
 ('v.', '（时间）流逝', 'when time goes by', 1, 2022, 'days passed'),
 ('v.', '去世 (pass away)', 'to die', 1, 2025, 'passed away'),
 ('n.', '通行证；票', 'a ticket that lets you enter or travel', 1, 2022, 'year-long pass'),
 ('v.', '放弃（机会）(pass up)', 'to not take a chance', 1, 2013, 'pass up')],
'key': [
 ('adj./n.', '关键（的）(the key to)', 'very important; the thing that makes something possible', 7, 2008, 'key to settling'),
 ('n.', '钥匙', 'a piece of metal used to open a lock', 2, 2022, 'room key'),
 ('n.', '（键盘的）键', 'a button you press on a keyboard', 2, 2019, 'pressure on keys')],
'top': [
 ('adj.', '最高的；顶级的', 'highest, best or most important', 6, 2016, 'top attraction'),
 ('n.', '顶部；山顶', 'the highest part of something', 5, 2009, 'top of the Voges')],
'drive': [
 ('v.', '开车', 'to control a car and make it move', 10, 2017, 'drive to the airport'),
 ('n.', '车程', 'a trip in a car', 1, 2022, "hour’s drive"),
 ('v.', '驱赶 (drive out)', 'to force someone or something to leave', 1, 2011, 'driven out')],
'stand': [
 ('v.', '站；站立', 'to be on your feet', 6, 2022, 'standing by himself'),
 ('v.', '代表 (stand for)', 'to be a sign or short form of something', 1, 2016, 'stand for other words'),
 ('n.', '摊位', 'a small table or shop for selling things', 2, 2015, 'Farm’s stand'),
 ('n.', '架子', 'a piece of furniture that holds things', 2, 2008, 'tray stand has been')],
'train': [
 ('n.', '火车', 'vehicles on a railway that carry people or goods', 9, 2015, 'your train leaving'),
 ('v.', '训练；培训', 'to teach or practise a skill', 3, 2020, 'train your brain')],
'hold': [
 ('v.', '举办；举行', 'to have a meeting, event or competition', 4, 2023, 'Competition held'),
 ('v.', '拿着；抱着', 'to have something in your hands or arms', 3, 2016, 'held a lively'),
 ('v.', '容纳', 'to have space for a number of people or things', 1, 2021, 'Circus Maximus hold'),
 ('v.', '吸引住（注意力）', 'to keep someone interested', 1, 2024, "hold students' attention"),
 ('v.', '忍住 (hold back)', 'to stop yourself from showing a feeling', 1, 2010, 'hold back tears'),
 ('n.', '抓住 (get hold of)', 'to take something in your hand, or find it', 1, 2016, 'got hold of')],
'face': [
 ('v.', '面对；面临', 'to have to deal with a problem or difficulty', 7, 2024, 'faced such challenges'),
 ('n.', '脸', 'the front of the head', 3, 2008, 'my face was on fire'),
 ('adj.', '面对面的 (face-to-face)', 'when people meet in person', 2, 2022, 'face-to-face time')],
'fine': [
 ('adj.', '好的；健康的；没问题', 'well, healthy or good enough', 5, 2024, 'Fiona is fine'),
 ('adj.', '细微的；薄的', 'very thin or very small and exact', 2, 2026, 'fine detail'),
 ('adj.', '精美的；优质的', 'of high quality', 1, 2015, 'fine selection')],
'carry': [
 ('v.', '携带；搬运', 'to hold something and take it with you', 5, 2021, 'carried the breakfast'),
 ('v.', '开展；实施 (carry out)', 'to do a plan, task or experiment', 2, 2023, 'carrying out your own'),
 ('v.', '继续 (carry on)', 'to continue doing something', 1, 2010, 'carry on'),
 ('v.', '承担；具有（分量）', 'to have a load, duty or importance', 2, 2022, 'carry even more weight')],
'return': [
 ('v.', '返回；回到', 'to go or come back', 6, 2020, 'Returning to a book'),
 ('n.', '返回；回归', 'the act of coming back', 3, 2022, 'return to Auburn'),
 ('v.', '归还', 'to give something back', 1, 2023, 'return to you'),
 ('n.', '回报 (in return)', 'something given back for what you did', 1, 2015, 'in return')],
'form': [
 ('n.', '形式；类型 (in the form of)', 'a type or way that something exists', 4, 2024, 'in the form of'),
 ('v.', '形成；组成', 'to make something, or come into being', 4, 2023, 'formed their own'),
 ('n.', '形态；姿势', 'the shape or way of moving', 2, 2020, 'strange form that makes'),
 ('v.', '成立（组织）', 'to start a club or group', 1, 2011, 'was formed six months ago')],
'order': [
 ('v.', '点（餐）；订购', 'to ask for food, drinks or goods', 5, 2017, 'going to order'),
 ('n.', '订单；点的东西', 'something you have asked to buy', 3, 2025, 'finishing an order'),
 ('n.', '状态 (in order 整齐 / out of order 坏了)', 'tidy or working (in order); broken (out of order)', 2, 2017, 'out of order'),
 ('conj.', '为了 (in order to)', 'so that you can do something', 0, None, None)],
'course': [
 ('n.', '课程', 'a set of classes in one subject', 7, 2017, 'one-month course'),
 ('adv.', '当然 (of course)', 'used to say yes or that something is clear', 5, 2024, 'Of course, a dictionary')],
'sound': [
 ('n.', '声音；语音', 'something you hear', 7, 2009, 'sound of a mother'),
 ('v.', '听起来', 'to seem, from what you hear or read', 5, 2021, 'harder than it sounds')],
'plant': [
 ('n.', '植物', 'a living thing that grows in soil', 11, 2023, 'indoor plants are easy'),
 ('n.', '工厂；处理厂', 'a factory or place where something is made or treated', 1, 2025, 'treatment plants'),
 ('v.', '种植', 'to put a seed or plant in the ground', 1, 2011, 'planted it')],
'miss': [
 ('v.', '错过；缺席', 'to not catch, see or attend something', 4, 2022, 'miss your flight'),
 ('v.', '丢失；缺少 (be missing)', 'to be lost or not there', 4, 2025, 'suitcase is missing'),
 ('v.', '想念；怀念', 'to feel sad because someone or something is not with you', 3, 2024, 'misses her grandma'),
 ('v.', '错过（好处）(miss out on)', 'to not get a good thing that others get', 1, 2024, 'missing out on')],
'deal': [
 ('v.', '处理；应对 (deal with)', 'to take action to solve a problem', 6, 2012, 'dealing with stress'),
 ('n.', '交易；划算的买卖 (a good deal)', 'a business agreement, or something bought at a good price', 4, 2013, 'good deal is something'),
 ('n.', '大事 (a big deal)', 'something important', 2, 2026, 'big deal'),
 ('n.', '大量 (a great deal)', 'a lot', 1, 2012, 'great deal is going on')],
}

ORDER_NOTE = {'order': '"in order to" 在抽样句里没出现，但它是固定短语，所以作为补充义项保留；需要统计全部用例确认。'}

def main(pilot_json, entries_csv, out_csv, out_html):
    d = json.load(open(pilot_json, encoding='utf-8'))
    cur = {r['headword']: r for r in csv.DictReader(open(entries_csv, encoding='utf-8-sig'))}
    rows, missing = [], []
    for w, senses in P.items():
        v = d[w]
        for i, (pos, zh, en, n, yr, key) in enumerate(senses, 1):
            ex, sec = '', ''
            if key:
                hit = [s for s in v['sentences'] if (yr is None or str(s[0]) == str(yr)) and key.lower() in s[4].lower()]
                if not hit:
                    missing.append((w, key))
                else:
                    ex, sec = hit[0][4].strip(), SEC.get(hit[0][1][:4], hit[0][1])
            rows.append({'rank': v['rank'], 'headword': w, 'count': v['count'], 'years': v['years'],
                         'sense_no': i, 'pos': pos, 'zh': zh, 'en': en, 'sample_n': n,
                         'sample_size': len(v['sentences']), 'example': ex,
                         'example_src': f'{yr} {sec}' if ex else '', 'note': ORDER_NOTE.get(w, '') if i == len(senses) else ''})
    if missing:
        print('MISSING examples:', missing, file=sys.stderr)
    with open(out_csv, 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)

    e = html.escape
    parts = ['''<!doctype html><html><head><meta charset="utf-8"><title>释义升级试点</title><style>
@page{size:A4;margin:14mm}body{font-family:"Times New Roman","Songti SC","Noto Serif CJK SC",serif;font-size:10pt;color:#222}
h1{font-size:15pt}table{border-collapse:collapse;width:100%;margin:0 0 10px;page-break-inside:avoid}
td{border:1px solid #bbb;vertical-align:top;padding:4px 6px}td.old{width:38%;color:#666;font-size:8.5pt}
.w{font-size:12.5pt;font-weight:bold}.meta{color:#888;font-size:8.5pt}.s{margin:0 0 4px}.ex{font-style:italic;color:#333;font-size:9pt}
.n{color:#a33;font-size:8pt}</style></head><body><h1>释义升级试点：第 2 章 30 个多义词</h1>
<p>左栏为现有词条（ECDICT 中文释义加 WordNet 英文释义），右栏为新写法：只保留真题实际用到的义项，按抽样句中的出现次数排序。每个义项都配一个真题例句，英文释义是我们自己写的简明英语。红字 n/N 表示抽样 N 句中有 n 句用的是这个义项。</p>''']
    for w, senses in P.items():
        c = cur.get(w, {}); v = d[w]
        old = f"<b>中：</b>{e(c.get('zh_gloss',''))}<br><b>英：</b>{e(c.get('en_definitions',''))}"
        new = []
        for r in [r for r in rows if r['headword'] == w]:
            new.append(f"<div class='s'><b>{r['sense_no']}. {e(r['pos'])} {e(r['zh'])}</b> <span class='n'>{r['sample_n']}/{r['sample_size']}</span><br>{e(r['en'])}"
                       + (f"<br><span class='ex'>{e(r['example'])}</span> <span class='meta'>（{e(r['example_src'])}）</span>" if r['example'] else '')
                       + (f"<br><span class='meta'>注：{e(r['note'])}</span>" if r['note'] else '') + '</div>')
        parts.append(f"<table><tr><td colspan=2><span class='w'>{w}</span> <span class='meta'>排名 {v['rank']} · {v['count']} 次 / {v['years']} 年 · {e(v['exam_pos'])} · 搭配 {e(c.get('collocations',''))}</span></td></tr>"
                     f"<tr><td class='old'>{old}</td><td>{''.join(new)}</td></tr></table>")
    parts.append('</body></html>')
    open(out_html, 'w', encoding='utf-8').write('\n'.join(parts))
    print(f'wrote {len(rows)} senses for {len(P)} words')

if __name__ == '__main__':
    main(*sys.argv[1:5])
