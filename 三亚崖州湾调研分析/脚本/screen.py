"""Tag the Sanya company list into a research sampling frame.

Input : sanya_companies.csv  (seq, name, uscc, pdf_page)
Output: sanya_screened.csv   (all 15,041 records, fully tagged)
        sanya_shortlist.csv  (priority interview candidates, ranked)

Derived variables of note
-------------------------
origin      首次登记地。统一社会信用代码第 3-8 位是登记机关行政区划代码，
            该代码在企业迁址后【不变】，因此它标识的是"出生地"而非现住所。
            这使其可用于区分「本地新设」与「外地迁入」。
vintage     注册年代近似。第 9-17 位为组织机构代码：纯数字为 2015 年前的
            旧版代码（老企业）；"MA" 开头为 2015 年后新版，且 MA5→MAK
            大致按时间递增。仅为序数近似，不可当精确成立日期使用。
"""
import csv, re, collections

# ----------------------------------------------------------------- taxonomies
# Track 1a: 育种科技（南繁核心）—— 研究问题真正指向的对象
SEED = ['种业', '种子', '育种', '制种', '种苗', '种源', '物种', '作物',
        '农科', '农业科技', '农业技术', '农业生物', '园艺', '水稻', '玉米',
        '大豆', '棉花', '蔬菜', '果蔬', '热带作物', '南繁', '基因', '分子',
        '生物育种', '植物', '植保', '农品', '农高', '福农', '高科农']
# Track 1b: 泛农业经营（种植/养殖/农资/林畜）—— 与育种科技分开，避免混为一谈
AGRI_BROAD = ['农业', '农资', '农产', '林业', '畜牧', '养殖', '果业',
              '粮', '椰子', '热带', '橡胶', '芒果', '花卉', '苗木',
              '肥料', '饲料', '兽药', '垦地', '农场']
OCEAN = ['深海', '海洋', '水下', '潜水', '声学', '水声', '海工', '海洋工程',
         '船舶', '船务', '舰', '海事', '港航', '潜航', '浮标', '海底',
         '珊瑚', '渔业', '水产', '海上风电']
SUPPORT = ['检测', '检验', '仪器', '仪表', '试验', '计量', '传感', '装备',
           '精密', '新材料', '芯片', '半导体', '电子科技', '自动化',
           '机器人', '无人机', '飞行器', '遥感', '测绘', '导航', '导控',
           '北斗', '卫星', '空天', '航天', '算法', '人工智能', '卷积',
           '智能装备', '智能制造', '机械制造', '液压', '生物医药',
           '医疗科技', '医疗器械', '环保科技', '能源科技', '新能源',
           '储能', '智慧能源', '软件', '大数据', '数据技术', '地质',
           '硅', '细胞']
# commercial / service / non-research forms
EXCLUDE = ['贸易', '商贸', '供应链', '进出口', '免税', '零售', '批发',
           '餐饮', '酒店', '民宿', '旅游', '文旅', '旅行社', '房地产',
           '置业', '物业', '装饰', '装修', '建筑', '建设工程', '劳务',
           '人力资源', '广告', '传媒', '文化', '影业', '演艺', '电商',
           '电子商务', '直播', '咨询', '企业管理', '财务', '税务', '法律',
           '教育', '培训', '健身', '美容', '家政', '物流', '仓储', '运输',
           '食品', '茶业', '医药', '眼镜', '服务有限公司', '商务服务']
HOLDING = ['投资', '资本', '基金', '股权', '控股', '资产管理', '创业投资',
           '产业投资', '股权投资']
FINANCE = ['银行', '保险', '证券', '信托', '担保', '小额贷款', '典当',
           '支行', '分行']
STATE = ['国投', '国资', '国有资本', '发展控股', '中国', '中科', '中农',
         '中种', '中核', '招商局', '国家', '城投', '交投', '农垦', '省属']
# Named seed/breeding industry leaders. A hit here forces the core track even
# when the company name carries no generic track keyword
# (e.g. 隆平生物技术（海南）有限公司 contains none of 种业/种子/育种).
# NOTE: '华智' 与 '瑞丰' 已剔除——二者在本名录中只产生子串误匹配
# （信[华智]能 / 明[华智]能 / 普[瑞丰]智），无一条是真正的华智生物或瑞丰生物。
NAMED_SEED = ['中国种子', '中种', '隆平', '先正达', '大北农', '垦丰', '荃银',
              '九圣禾', '登海', '丰乐', '中农发', '农发种业', '舜丰',
              '博瑞迪', '齐禾生科', '华智生物', '国投种业']
NAMED_OCEAN = ['招商局深海', '深海所', '中船', '中海油', '海油', '中交',
               '哈工程', '深之蓝', '鳍源']
# thematic anchors: policy / park / flagship-programme salience
THEME_ANCHORS = ['南繁', '崖州湾', '深海', '耐盐碱', '科技城', '种子实验室',
                 '遥感', '招商局', '实验室', '研究院', '研究所']
ANCHORS = NAMED_SEED + NAMED_OCEAN + THEME_ANCHORS + ['深之蓝']

BRANCH = re.compile(r'(分公司|分行|支行|办事处|分中心|代表处|营业店|营业部|分店|分所)$')
PARTNER = re.compile(r'合伙企业|有限合伙|普通合伙')
SOLE = re.compile(r'个人独资')

HAINAN_PROV = '460000'
SANYA = ('460200', '460202', '460203', '460204', '460205')
HAIKOU = ('460100', '460105', '460106', '460107', '460108')


def hits(name, words):
    return [w for w in words if w in name]


def origin_of(code):
    """First-registration locus implied by USCC chars 3-8 (stable across moves)."""
    r = code[2:8]
    if r == HAINAN_PROV:
        return '海南省级登记', '本地(省级)'
    if r in SANYA:
        return '三亚市/区登记', '本地(三亚)'
    if r in HAIKOU:
        return '海口登记', '省内迁入/外设'
    if r.startswith('46'):
        return '海南其他市县登记', '省内迁入/外设'
    return f'省外登记({r})', '省外迁入/外设'


VINT_ORDER = ['旧版(2015前)', 'MA5', 'MA7', 'MA9', 'MAA', 'MAC', 'MAD',
              'MAE', 'MAG', 'MAJ', 'MAK', 'MA其他']


def vintage_of(code):
    """Coarse registration-vintage proxy from the organisation-code segment."""
    org = code[8:11]
    if org[:2] != 'MA':
        return '旧版(2015前)'
    tag = org[:3]
    return tag if tag in VINT_ORDER else 'MA其他'


# Batch-registration signature: 「三亚市/海南 + 2-3 个人名样字 + 网络/信息科技」.
# These appear in long runs of near-identical names and are the visible face of
# registration-driven growth in a 注册企业名录.
BATCH = re.compile(r'^(三亚市|三亚|海南|三亚崖州)[^（()]{2,3}(网络科技|信息科技|科技)'
                   r'有限(责任)?公司$')
GENERIC = re.compile(r'(网络科技|信息科技|信息技术|数字科技|科技)'
                     r'有限(责任)?公司$|科技合伙企业')


def classify(name):
    s, o, sp = hits(name, SEED), hits(name, OCEAN), hits(name, SUPPORT)
    ab = hits(name, AGRI_BROAD)
    ex, hd, fi = hits(name, EXCLUDE), hits(name, HOLDING), hits(name, FINANCE)
    # named industry leaders override keyword logic entirely
    ns, no = hits(name, NAMED_SEED), hits(name, NAMED_OCEAN)
    if ns and not fi:
        return '南繁种业', sorted(set(s + ns)), o, sp, ex, hd, fi, ab
    if no and not fi:
        return '深海海洋', s, sorted(set(o + no)), sp, ex, hd, fi, ab
    if fi:
        return '金融机构', s, o, sp, ex, hd, fi, ab
    # a core-track keyword wins only if the name is not dominated by trade/service words
    if s and not ex:
        return '南繁种业', s, o, sp, ex, hd, fi, ab
    if o and not ex:
        return '深海海洋', s, o, sp, ex, hd, fi, ab
    if sp and not ex:
        return '科技配套', s, o, sp, ex, hd, fi, ab
    if ab and not ex:
        return '泛农业经营', s, o, sp, ex, hd, fi, ab
    if (s or o or sp or ab) and ex:
        return '赛道词但经营词冲突', s, o, sp, ex, hd, fi, ab
    if ex or hd:
        return '非目标', s, o, sp, ex, hd, fi, ab
    if BATCH.match(name):
        return '批量注册特征', s, o, sp, ex, hd, fi, ab
    if GENERIC.search(name):
        return '泛科技无行业信号', s, o, sp, ex, hd, fi, ab
    return '待判定', s, o, sp, ex, hd, fi, ab


rows = list(csv.DictReader(open('sanya_companies.csv', encoding='utf-8-sig')))
out = []
for r in rows:
    name, code = r['name'], r['uscc']
    track, s, o, sp, ex, hd, fi, ab = classify(name)

    form = '独立法人'
    if BRANCH.search(name):
        form = '分支机构'
    elif PARTNER.search(name):
        form = '合伙企业'
    elif SOLE.search(name):
        form = '个人独资'

    reg_label, origin = origin_of(code)
    vintage = vintage_of(code)
    anchor, state = hits(name, ANCHORS), hits(name, STATE)

    flags = []
    if form == '分支机构':
        flags.append('分支机构(非独立法人)')
    if form in ('合伙企业', '个人独资'):
        flags.append(f'{form}(常为持股/通道载体)')
    if track == '赛道词但经营词冲突':
        flags.append('科技名称与经营词冲突')
    if hd and not (s or o or sp):
        flags.append('纯投资/控股载体')
    if origin.startswith('省外'):
        flags.append('首次登记在省外(迁入或外地主体设点)')

    core = track in ('南繁种业', '深海海洋')
    score = 0
    if track == '南繁种业':
        score += 50
    elif track == '深海海洋':
        score += 48
    elif track == '科技配套':
        score += 25
    elif track == '泛农业经营':
        score += 18
    if form == '独立法人':
        score += 10
    if anchor:
        score += 18
    if state:
        score += 8
    if origin.startswith('本地'):
        score += 6
    score -= 12 * len(flags)

    if core and form == '独立法人' and not flags:
        tier = 'A 核心赛道-优先访谈'
    elif core:
        tier = 'B 核心赛道-需核实'
    elif track in ('科技配套', '泛农业经营') and form == '独立法人':
        tier = 'C 支撑/泛赛道-备选'
    elif track == '批量注册特征':
        tier = 'F 批量注册特征-单独成组'
    elif track in ('待判定', '泛科技无行业信号'):
        tier = 'D 名称无行业信号'
    else:
        tier = 'E 非目标/对照组池'

    out.append({
        'seq': r['seq'], 'name': name, 'uscc': code, 'pdf_page': r['pdf_page'],
        'tier': tier, 'track': track, 'form': form,
        'reg_authority': reg_label, 'origin': origin, 'vintage': vintage,
        'seed_kw': '|'.join(s), 'ocean_kw': '|'.join(o), 'support_kw': '|'.join(sp),
        'exclude_kw': '|'.join(ex), 'holding_kw': '|'.join(hd),
        'anchor_kw': '|'.join(anchor), 'state_kw': '|'.join(state),
        'risk_flags': '; '.join(flags), 'score': score,
    })

FIELDS = list(out[0].keys())
with open('sanya_screened.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(out)

short = sorted([r for r in out if r['tier'][0] in 'ABC'], key=lambda r: -r['score'])
with open('sanya_shortlist.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(short)

# -------------------------------------------- funding side / institutional side
# Park platforms, state capital vehicles and research bodies are NOT part of the
# enterprise sample; they are the counterparties to interview about the fund.
PARK = re.compile(r'(崖州湾|科技城|南繁科技城|深海科技城)'
                  r'.*(科技城开发|开发建设|投资控股|控股集团|创业投资|'
                  r'产业发展|产业园|产业投资|孵化器|创新发展中心|运营管理)')
RESEARCH = re.compile(r'(研究院|研究所|实验室|工程中心|技术中心|创新中心|孵化器)')
FUND_VEHICLE = re.compile(r'(基金管理|私募|创业投资|股权投资|产业投资)')


def inst_role(name, form):
    roles = []
    if (form != '分支机构' and PARK.search(name)
            and any(k in name for k in ('崖州湾', '科技城', '南繁', '深海'))):
        roles.append('园区/产业平台')
    if RESEARCH.search(name):
        roles.append('科研/孵化载体')
    if FUND_VEHICLE.search(name):
        roles.append('基金/投资管理人')
    if any(k in name for k in ('农垦', '国投', '国资', '城投', '发展控股', '招商局')):
        roles.append('国有资本平台')
    return roles


inst = []
for r in out:
    roles = inst_role(r['name'], r['form'])
    if roles:
        d = dict(r)
        d['inst_role'] = '; '.join(roles)
        inst.append(d)
inst.sort(key=lambda r: (r['inst_role'], r['name']))
with open('sanya_institutions.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS + ['inst_role'])
    w.writeheader()
    w.writerows(inst)

# ------------------------------------------------------------------- reporting
n = len(out)


def dist(key, top=None, order=None):
    c = collections.Counter(r[key] for r in out)
    items = [(k, c[k]) for k in order if k in c] if order else c.most_common(top)
    for k, v in items:
        print(f'   {k:<24}{v:>6}  {v/n*100:5.2f}%')


print(f'总记录 {n}\n')
print('== 优先级分层 ==');   dist('tier', order=sorted({r['tier'] for r in out}))
print('\n== 赛道分布 ==');   dist('track')
print('\n== 主体形态 ==');   dist('form')
print('\n== 首次登记地（迁入判别）==');  dist('origin')
print('\n== 注册年代近似 ==');  dist('vintage', order=VINT_ORDER)
print(f'\nshortlist 条数 {len(short)}  (A/B/C 三层)')
print('\n== A 层 Top 40 ==')
for r in [x for x in short if x['tier'][0] == 'A'][:40]:
    print(f"   {r['score']:>3} [{r['track']}] {r['name']}  ({r['origin']}/{r['vintage']})")
print(f'\n== 资金侧/机构侧对象 {len(inst)} 家 ==')
for k, v in collections.Counter(r['inst_role'] for r in inst).most_common():
    print(f'   {k:<34}{v:>5}')
print('\n-- 园区/产业平台（全部）--')
for r in inst:
    if '园区/产业平台' in r['inst_role']:
        print(f"   {r['name']}  ({r['origin']}/{r['vintage']})")
print('\n-- 基金/投资管理人（前 20）--')
for r in [x for x in inst if '基金/投资管理人' in x['inst_role']][:20]:
    print(f"   {r['name']}")

print('\n== 核心赛道 × 首次登记地 交叉 ==')
cross = collections.Counter(
    (r['track'], r['origin']) for r in out if r['track'] in ('南繁种业', '深海海洋'))
for k, v in sorted(cross.items()):
    print(f'   {k[0]:<8}{k[1]:<16}{v:>5}')
