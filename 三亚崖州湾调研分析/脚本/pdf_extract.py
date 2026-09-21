"""Stdlib-only PDF text extractor for Identity-H CID PDFs with a ToUnicode CMap.

Reconstructs text lines using Td/TD/Tm/T* positioning so that table rows survive.
"""
import re, sys, zlib, collections

data = open(sys.argv[1], 'rb').read()

# ---------------------------------------------------------------- object scan
# Map "N 0 obj" -> byte offset of its body.
objs = {}
for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', data):
    objs[int(m.group(1))] = m.end()


def raw_obj(num):
    """Return the bytes of object `num` up to its endobj."""
    if num not in objs:
        return b''
    start = objs[num]
    end = data.find(b'endobj', start)
    return data[start:end if end != -1 else len(data)]


def get_stream(num):
    """Decompressed stream bytes of object `num` (FlateDecode or raw)."""
    body = raw_obj(num)
    i = body.find(b'stream')
    if i == -1:
        return b''
    j = i + len(b'stream')
    if body[j:j + 2] == b'\r\n':
        j += 2
    elif body[j:j + 1] in (b'\n', b'\r'):
        j += 1
    k = body.rfind(b'endstream')
    payload = body[j:k if k != -1 else len(body)]
    if b'FlateDecode' in body[:i]:
        try:
            return zlib.decompress(payload)
        except zlib.error:
            # tolerate truncated / trailing-garbage streams
            d = zlib.decompressobj()
            try:
                return d.decompress(payload)
            except zlib.error:
                return b''
    return payload


# ------------------------------------------------------------- ToUnicode CMap
def build_cmap():
    """CID (int) -> unicode str, parsed from the ToUnicode CMap stream."""
    cmap = {}
    # locate the object referenced by /ToUnicode N 0 R
    m = re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R', data)
    if not m:
        return cmap
    cm = get_stream(int(m.group(1)))

    def to_text(h):
        """Hex string -> unicode, decoding UTF-16BE surrogate pairs."""
        b = bytes.fromhex(h.decode('latin-1'))
        try:
            return b.decode('utf-16-be', errors='ignore')
        except Exception:
            return ''

    for blk in re.findall(rb'beginbfchar(.*?)endbfchar', cm, re.S):
        for src, dst in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            cmap[int(src, 16)] = to_text(dst)
    for blk in re.findall(rb'beginbfrange(.*?)endbfrange', cm, re.S):
        # <lo> <hi> <dstStart>
        for lo, hi, dst in re.findall(
                rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            lo_i, hi_i = int(lo, 16), int(hi, 16)
            base = int(dst, 16)
            for k, c in enumerate(range(lo_i, min(hi_i, lo_i + 65535) + 1)):
                cmap[c] = chr(base + k) if base + k < 0x110000 else ''
        # <lo> <hi> [ <d1> <d2> ... ]
        for lo, hi, arr in re.findall(
                rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]', blk, re.S):
            items = re.findall(rb'<([0-9A-Fa-f]+)>', arr)
            for k, it in enumerate(items):
                cmap[int(lo, 16) + k] = to_text(it)
    return cmap


CMAP = build_cmap()

# --------------------------------------------------------------- page streams
def contents_of(page_num):
    """Content-stream object numbers for a /Type /Page object."""
    body = raw_obj(page_num)
    m = re.search(rb'/Contents\s+(\d+)\s+0\s+R', body)
    if m:
        return [int(m.group(1))]
    m = re.search(rb'/Contents\s*\[([^\]]*)\]', body)
    if m:
        return [int(x) for x in re.findall(rb'(\d+)\s+0\s+R', m.group(1))]
    return []


def discover_pages():
    """Page object numbers in document order (via /Kids when available)."""
    order = []
    # locate the /Type /Pages tree root and read its /Kids
    for num in objs:
        body = raw_obj(num)
        if re.search(rb'/Type\s*/Pages\b', body):
            kids = re.search(rb'/Kids\s*\[(.*?)\]', body, re.S)
            if kids:
                order = [int(x) for x in re.findall(rb'(\d+)\s+0\s+R', kids.group(1))]
            break
    if not order:
        # fall back to scanning for page objects in file order
        order = [n for n in sorted(objs)
                 if re.search(rb'/Type\s*/Page\b(?!s)', raw_obj(n))]
    return order


page_contents = []
for pnum in discover_pages():
    page_contents.extend(contents_of(pnum))

# ------------------------------------------------------------ content parsing
STR_RE = re.compile(rb'\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]*>', re.S)


def decode_hexstr(tok):
    """A PDF string token -> unicode via the CID cmap (2-byte codes)."""
    if tok.startswith(b'<'):
        h = re.sub(rb'[^0-9A-Fa-f]', b'', tok)
        if len(h) % 4:
            h = h + b'0' * (4 - len(h) % 4)
        codes = [int(h[i:i + 4], 16) for i in range(0, len(h), 4)]
    else:
        body = tok[1:-1]
        body = re.sub(rb'\\([nrtbf()\\])', lambda m: {
            b'n': b'\n', b'r': b'\r', b't': b'\t', b'b': b'\b',
            b'f': b'\f', b'(': b'(', b')': b')', b'\\': b'\\'}[m.group(1)], body)
        if len(body) % 2:
            body += b'\x00'
        codes = [(body[i] << 8) | body[i + 1] for i in range(0, len(body), 2)]
    return ''.join(CMAP.get(c, '') for c in codes)


NUM = rb'[-+]?[\d.]+'
PDFSTR = rb'(?:\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]*>)'
OPS = re.compile(
    rb'(?P<tm>' + NUM + rb'\s+' + NUM + rb'\s+' + NUM + rb'\s+' + NUM +
    rb'\s+' + NUM + rb'\s+' + NUM + rb'\s+Tm)'
    rb'|(?P<td>' + NUM + rb'\s+' + NUM + rb'\s+(?:TD|Td))'
    rb'|(?P<tf>/\S+\s+(?P<tfsize>' + NUM + rb')\s+Tf)'
    rb'|(?P<tj>' + PDFSTR + rb'\s*Tj)'
    rb'|(?P<tJ>\[(?:[^\[\]\\]|\\.)*\]\s*TJ)', re.S)

COL_GAP = 3.0      # pt of whitespace that separates two table columns
Y_TOL = 1.5        # pt tolerance when clustering glyphs into one row


def is_wide(ch):
    """True for full-width (CJK) glyphs, which advance a full em."""
    return ch and ord(ch[0]) > 0x2E7F


def page_runs(stream):
    """Yield (y, x_start, x_end, text) for every glyph run on the page."""
    x = y = 0.0
    sx, sy = 1.0, 1.0   # text-matrix scale (a, d)
    size = 0.0
    runs = []
    pending = None      # glyph awaiting its advance, set by the following TD

    def flush(adv):
        nonlocal pending
        if pending is not None:
            py, px, pt = pending
            runs.append((py, px, px + adv, pt))
            pending = None

    for m in OPS.finditer(stream):
        if m.group('tm'):
            g = m.group(0).split()
            # a b c d e f Tm  ->  scale from a/d, origin from e/f
            sx, sy = float(g[0]), float(g[3])
            nx, ny = float(g[4]), float(g[5])
            if pending is not None:
                # no TD followed: estimate advance from font size
                em = abs(size * sx)
                flush(em if is_wide(pending[2]) else em / 2)
            x, y = nx, ny
        elif m.group('tf'):
            size = float(m.group('tfsize'))
        elif m.group('td'):
            g = m.group(0).split()
            dx, dy = float(g[0]), float(g[1])
            # Td/TD translate in text space -> scale into device units
            adv = dx * abs(sx)
            flush(adv)
            x += adv
            y += dy * abs(sy)
        elif m.group('tj') or m.group('tJ'):
            if m.group('tj'):
                txt = decode_hexstr(STR_RE.search(m.group(0)).group(0))
            else:
                txt = ''.join(decode_hexstr(t.group(0))
                              for t in STR_RE.finditer(m.group(0)))
            if pending is not None:
                em = abs(size * sx)
                flush(em if is_wide(pending[2]) else em / 2)
            if txt:
                pending = (y, x, txt)
    if pending is not None:
        em = abs(size * sx)
        flush(em if is_wide(pending[2]) else em / 2)
    return runs


def page_lines(stream):
    """Group glyph runs into rows (y ascending, page y-axis is flipped)."""
    runs = page_runs(stream)
    if not runs:
        return []
    # cluster rows by y with a tolerance
    runs.sort(key=lambda r: (r[0], r[1]))
    rows, cur, cur_y = [], [], None
    for r in runs:
        if cur_y is None or abs(r[0] - cur_y) <= Y_TOL:
            cur.append(r)
            cur_y = r[0] if cur_y is None else cur_y
        else:
            rows.append(cur)
            cur, cur_y = [r], r[0]
    if cur:
        rows.append(cur)

    out = []
    for row in rows:
        row.sort(key=lambda r: r[1])
        cells, buf, prev_end = [], [], None
        for (_, xs, xe, t) in row:
            if prev_end is not None and xs - prev_end > COL_GAP:
                cells.append(''.join(buf))
                buf = []
            buf.append(t)
            prev_end = xe
        if buf:
            cells.append(''.join(buf))
        cells = [c.strip() for c in cells if c.strip()]
        if cells:
            out.append(cells)
    return out


if __name__ == '__main__':
    print(f'# cmap entries: {len(CMAP)}', file=sys.stderr)
    print(f'# pages found : {len(page_contents)}', file=sys.stderr)
    total = 0
    with open(sys.argv[2], 'w', encoding='utf-8') as fh:
        for pi, num in enumerate(page_contents, 1):
            s = get_stream(num)
            if not s:
                continue
            for cells in page_lines(s):
                total += 1
                fh.write(f'{pi}\t' + '\t'.join(cells) + '\n')
    print(f'# lines written: {total}', file=sys.stderr)
