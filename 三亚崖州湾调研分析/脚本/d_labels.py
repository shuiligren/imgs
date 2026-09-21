"""Hand labels for the 400-firm tier-D sample, plus miss-rate estimation.

Labels assigned by reading each company name (idx refers to d_sample.csv):
  SEED    = 应归南繁种业，规则漏检
  OCEAN   = 应归深海海洋，规则漏检
  SUPPORT = 应归科技配套，规则漏检
  (未列出的 idx 视为 D 层判定正确：非目标，或名称确实无行业信号)
"""
import csv, math

SEED = {25, 32, 39, 47, 48, 57, 59, 99, 105, 117, 122, 140, 143, 151, 156,
        175, 183, 209, 224, 225, 234, 236, 254, 269, 276, 280, 285, 303,
        316, 322, 329, 342, 348, 372, 398}
OCEAN = {192}
SUPPORT = {16, 23, 110, 113, 126, 157, 165, 177, 179, 181, 182, 193, 246,
           255, 304, 305, 311, 315, 367, 369, 371, 377, 381}
# borderline calls, recorded so the judgement is auditable rather than hidden
BORDERLINE = {25, 59, 117, 143, 113, 193, 372}


def wilson(k, n, z=1.96):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


if __name__ == '__main__':
    rows = list(csv.DictReader(open('d_sample.csv', encoding='utf-8-sig')))
    n = len(rows)
    D_TOTAL = 6884

    core = len(SEED) + len(OCEAN)
    sup = len(SUPPORT)
    tot = core + sup

    print(f'D 层总数 {D_TOTAL}，抽样 n={n}\n')
    for label, k in (('核心赛道漏检 (南繁种业+深海海洋)', core),
                     ('  其中 南繁种业', len(SEED)),
                     ('  其中 深海海洋', len(OCEAN)),
                     ('支撑赛道漏检 (科技配套)', sup),
                     ('合计漏检 (应进 A/B/C)', tot)):
        lo, hi = wilson(k, n)
        est = k / n * D_TOTAL
        print(f'{label:<34} {k:>3}/{n}  {k/n*100:5.2f}%  '
              f'95%CI [{lo*100:4.2f}%, {hi*100:4.2f}%]  '
              f'推断约 {est:>5.0f} 家 (区间 {lo*D_TOTAL:.0f}–{hi*D_TOTAL:.0f})')
    print(f'\n其中判定存疑（borderline）{len(BORDERLINE)} 条，已单列备复核')

    # write labels back for auditability
    for r in rows:
        i = int(r['idx'])
        r['label'] = ('SEED' if i in SEED else 'OCEAN' if i in OCEAN
                      else 'SUPPORT' if i in SUPPORT else '')
        r['borderline'] = 'Y' if i in BORDERLINE else ''
    with open('d_sample_labeled.csv', 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('已写出 d_sample_labeled.csv')
