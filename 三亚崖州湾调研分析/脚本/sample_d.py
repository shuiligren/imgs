"""Draw a reproducible random sample from a tier to estimate the miss rate.

Usage: python3 sample_d.py <tier_letter> <n> <seed>
The validation round MUST use a seed different from the round whose results
were used to revise the rules, otherwise the miss rate is optimistically biased.
"""
import csv, random, sys

tier = sys.argv[1] if len(sys.argv) > 1 else 'D'
n = int(sys.argv[2]) if len(sys.argv) > 2 else 400
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 20260217

rows = [r for r in csv.DictReader(open('sanya_screened.csv', encoding='utf-8-sig'))
        if r['tier'].startswith(tier)]
rows.sort(key=lambda r: int(r['seq']))
random.seed(seed)
n = min(n, len(rows))
samp = random.sample(rows, n)
samp.sort(key=lambda r: int(r['seq']))

fn = f'sample_{tier}_{seed}.csv'
with open(fn, 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(['idx', 'seq', 'name', 'uscc', 'track', 'origin', 'vintage', 'label'])
    for i, r in enumerate(samp, 1):
        w.writerow([i, r['seq'], r['name'], r['uscc'], r['track'],
                    r['origin'], r['vintage'], ''])

print(f'{tier} 层总数 {len(rows)}，抽样 {n}，seed={seed} -> {fn}')
for i, r in enumerate(samp, 1):
    print(f'{i:>3} {r["name"]}')
