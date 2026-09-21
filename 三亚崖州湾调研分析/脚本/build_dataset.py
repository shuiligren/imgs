"""Validate the extracted rows and emit a clean company dataset."""
import re, csv, collections

USCC = re.compile(r'^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{9}[0-9A-HJ-NPQRTUWXY]$')

rows = []
bad = []
header_rows = 0
with open('sanya_raw.tsv', encoding='utf-8') as fh:
    for ln in fh:
        parts = ln.rstrip('\n').split('\t')
        page, cells = parts[0], parts[1:]
        if not cells:
            continue
        if cells[0] == '序号':
            header_rows += 1
            continue
        if len(cells) == 3 and cells[0].isdigit():
            seq, name, code = cells
            rows.append((int(page), int(seq), name, code))
            if not USCC.match(code):
                bad.append((page, seq, name, code))
        else:
            bad.append((page, '?', '|'.join(cells), 'MALFORMED'))

print('header rows        :', header_rows)
print('parsed records     :', len(rows))
print('problem rows       :', len(bad))
for b in bad[:20]:
    print('   ', b)

seqs = [r[1] for r in rows]
print()
print('seq min/max        :', min(seqs), max(seqs))
print('seq is 1..N cont.  :', seqs == list(range(1, len(seqs) + 1)))

names = [r[2] for r in rows]
codes = [r[3] for r in rows]
print('unique names       :', len(set(names)))
print('unique codes       :', len(set(codes)))
dupn = [k for k, v in collections.Counter(names).items() if v > 1]
dupc = [k for k, v in collections.Counter(codes).items() if v > 1]
print('duplicate names    :', len(dupn), dupn[:5])
print('duplicate codes    :', len(dupc), dupc[:5])

# registration-authority prefix distribution (chars 3-8 of the USCC)
print()
print('USCC region code distribution (top 15):')
for k, v in collections.Counter(c[2:8] for c in codes).most_common(15):
    print(f'   {k}  {v:>6}')

with open('sanya_companies.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(['seq', 'name', 'uscc', 'pdf_page'])
    for page, seq, name, code in rows:
        w.writerow([seq, name, code, page])
print()
print('wrote sanya_companies.csv')
