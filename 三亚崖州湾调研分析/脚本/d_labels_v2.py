"""Validation round: hand labels for sample_D_99991.csv (n=300, fresh seed).

Rules were revised using the first sample (seed 20260217); this round uses an
independent seed so the resulting miss rate is not optimistically biased.

Two thresholds are reported because tier D is, by construction, the set of
names that carry no decisive industry signal:
  STRICT  = 名称中有明确行业词，规则确实该抓到（真漏检）
  LENIENT = STRICT + 仅凭一两个暗示性字（禾/海/深蓝/果）推测的存疑判定
"""
import csv
from d_labels import wilson

# --- clear misses -----------------------------------------------------------
SEED_STRICT = {7, 99, 110, 193, 245}
OCEAN_STRICT = {174, 175}
SUPPORT_STRICT = {24, 26, 104, 114, 145, 188, 233, 300}

# --- borderline: evocative character only, no decisive sector word -----------
SEED_BORDER = {6, 10, 44, 65, 80, 91, 126, 148, 149, 207, 212, 239}
OCEAN_BORDER = {27, 55, 101, 124, 176, 210, 244, 293}
SUPPORT_BORDER = {82, 86, 93, 95, 116, 119, 138, 143, 151, 159, 184, 195,
                  199, 227, 253, 264, 280}

D_TOTAL = 4140
NOTE = {
    233: '海南华大智造科技有限公司 —— 基因测序装备龙头，名称无任何行业词',
    104: '镭测创芯（海南）科技有限公司 —— 激光测量+芯片',
    300: '海南意波量子科技有限公司 —— 量子',
    110: '菽新生物科技（三亚）有限公司 —— “菽”即豆类',
    7:   '中农动科（三亚）技术有限公司 —— 动物科学',
    174: '海南深水能源有限公司 —— 深水即深海油气',
}

if __name__ == '__main__':
    rows = list(csv.DictReader(open('sample_D_99991.csv', encoding='utf-8-sig')))
    n = len(rows)

    core_s = len(SEED_STRICT) + len(OCEAN_STRICT)
    sup_s = len(SUPPORT_STRICT)
    core_l = core_s + len(SEED_BORDER) + len(OCEAN_BORDER)
    sup_l = sup_s + len(SUPPORT_BORDER)

    print(f'验证轮：D 层总数 {D_TOTAL}，抽样 n={n}，seed=99991（与调规则轮不同）\n')
    rowsfmt = [
        ('STRICT  核心赛道漏检', core_s), ('STRICT  支撑赛道漏检', sup_s),
        ('STRICT  合计', core_s + sup_s),
        ('LENIENT 核心赛道漏检', core_l), ('LENIENT 支撑赛道漏检', sup_l),
        ('LENIENT 合计', core_l + sup_l),
    ]
    for label, k in rowsfmt:
        lo, hi = wilson(k, n)
        print(f'{label:<24}{k:>4}/{n}  {k/n*100:5.2f}%  '
              f'95%CI [{lo*100:4.2f}%, {hi*100:5.2f}%]  '
              f'推断 {k/n*D_TOTAL:>4.0f} 家 ({lo*D_TOTAL:.0f}–{hi*D_TOTAL:.0f})')

    print('\n== 与第一轮对比（核心赛道漏检率）==')
    lo0, hi0 = wilson(36, 400)
    lo1, hi1 = wilson(core_s, n)
    print(f'   改规则前  36/400 = 9.00%  CI [{lo0*100:.2f}%, {hi0*100:.2f}%]')
    print(f'   改规则后(STRICT) {core_s}/{n} = {core_s/n*100:.2f}%  '
          f'CI [{lo1*100:.2f}%, {hi1*100:.2f}%]')
    print('   两区间不重叠 -> 改进显著' if hi1 < lo0 else '   两区间重叠 -> 改进不显著')

    print('\n== 名称法天花板的典型案例 ==')
    for i, t in NOTE.items():
        print(f'   #{i:<4}{t}')

    for r in rows:
        i = int(r['idx'])
        if i in SEED_STRICT | OCEAN_STRICT | SUPPORT_STRICT:
            r['label'] = 'MISS_STRICT'
        elif i in SEED_BORDER | OCEAN_BORDER | SUPPORT_BORDER:
            r['label'] = 'MISS_BORDERLINE'
        else:
            r['label'] = 'OK'
    with open('sample_D_99991_labeled.csv', 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('\n已写出 sample_D_99991_labeled.csv')
