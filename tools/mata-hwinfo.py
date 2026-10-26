#!/usr/bin/env python3
"""Print the hardware facts the PH-1 port needs from the stock device trees.

  mata-hwinfo.py boot.img            # stock Essential PH-1 boot.img (device trees appended to the kernel)
  mata-hwinfo.py file.dtb            # a single .dtb or concatenated blobs (e.g. tools/extract_appended_dtb.py output)
  mata-hwinfo.py --selftest

Pure Python, no dtc needed. Output is plain text: attach it to an issue or
paste it back so the framebuffer, GIC, UFS, memory, touch controller and key
wiring can be checked against the constants in shim/board.h and
tools/mkadt.py. Nothing in it is secret except, possibly, serial-number
style properties; those are not printed.
"""
import re, struct, sys

FDT_MAGIC = b'\xd0\x0d\xfe\xed'
SKIP_PROPS = re.compile(r'serial|mac-address|bd-address|androidboot')
TOUCH_RE = re.compile(r'touch|synaptics|rmi|focal|goodix|atmel|maxtouch|himax|novatek|cyttsp|ilitek|elan|stm,|fts|\bts\b|sec,|melfas|zinitix', re.I)
INTERESTING_NODE = re.compile(
    r'^(memory|chosen|timer|cpus|cpu@.*|.*ufs.*|interrupt-controller.*|.*gic.*|.*cont_splash.*|.*splash.*|.*framebuffer.*|'
    r'.*pon.*|.*spmi.*|.*gpio-keys.*|.*keys.*|.*pm8998.*|.*pmi8998.*|.*mdss.*|.*dsi.*|.*panel.*|.*i2c.*|.*qupv3.*|.*blsp.*)$', re.I)


class Node:
    def __init__(self, name):
        self.name, self.props, self.children = name, {}, []


def parse(blob):
    magic, total, off_struct, off_str, _, version, _, _, size_str, size_struct = struct.unpack_from('>10I', blob, 0)
    assert blob[:4] == FDT_MAGIC
    pos, end = off_struct, off_struct + size_struct
    root, stack = None, []
    while pos < end:
        tok, = struct.unpack_from('>I', blob, pos); pos += 4
        if tok == 1:
            i = blob.index(b'\0', pos)
            n = Node(blob[pos:i].decode('latin1') or '/')
            pos = (i + 4) & ~3
            if stack:
                stack[-1].children.append(n)
            else:
                root = n
            stack.append(n)
        elif tok == 2:
            stack.pop()
        elif tok == 3:
            ln, nameoff = struct.unpack_from('>II', blob, pos); pos += 8
            j = blob.index(b'\0', off_str + nameoff)
            stack[-1].props[blob[off_str + nameoff:j].decode('latin1')] = blob[pos:pos + ln]
            pos = (pos + ln + 3) & ~3
        elif tok == 9:
            break
    return root


def split_blobs(data):
    """All FDT blobs in data (a lone dtb, a concatenation, or a whole boot.img kernel)."""
    if data[:8] == b'ANDROID!':
        ks, ps = struct.unpack_from('<I', data, 8)[0], struct.unpack_from('<I', data, 36)[0]
        data = data[ps:ps + ks]
    out, pos = [], 0
    while True:
        i = data.find(FDT_MAGIC, pos)
        if i < 0:
            return out
        total, = struct.unpack_from('>I', data, i + 4)
        version, = struct.unpack_from('>I', data, i + 20)
        if 0x100 < total <= len(data) - i and 1 <= version <= 17:
            out.append(data[i:i + total]); pos = i + total
        else:
            pos = i + 4


def strings(v):
    if not v or v[-1:] != b'\0':
        return None
    parts = v[:-1].split(b'\0')
    if all(p and all(32 <= c < 127 for c in p) for p in parts):
        return [p.decode() for p in parts]
    return None


def fmt(name, v, ac=2, sc=2):
    if SKIP_PROPS.search(name):
        return '<hidden>'
    if not v:
        return '<empty>'
    s = strings(v)
    if s:
        return ' '.join(f'"{x}"' for x in s)
    if len(v) % 4:
        return v.hex()
    cells = struct.unpack('>%dI' % (len(v) // 4), v)
    if name == 'reg' and ac + sc and len(cells) % (ac + sc) == 0:
        groups = []
        for k in range(0, len(cells), ac + sc):
            a = int.from_bytes(struct.pack('>%dI' % ac, *cells[k:k + ac]), 'big') if ac else 0
            z = int.from_bytes(struct.pack('>%dI' % sc, *cells[k + ac:k + ac + sc]), 'big') if sc else 0
            groups.append(f'<0x{a:x} 0x{z:x}>')
        return ' '.join(groups)
    return '<' + ' '.join(f'0x{c:x}' if c > 9 else str(c) for c in cells) + '>'


def walk(n, path='', cells=(2, 2)):
    here = path + '/' + n.name if n.name != '/' else ''
    yield here or '/', n, cells
    ac = struct.unpack('>I', n.props['#address-cells'])[0] if '#address-cells' in n.props else cells[0]
    sc = struct.unpack('>I', n.props['#size-cells'])[0] if '#size-cells' in n.props else cells[1]
    for c in n.children:
        yield from walk(c, here, (ac, sc))


def matches(path, n):
    comp = ' '.join(strings(n.props.get('compatible', b'')) or [])
    base = n.name.split('@')[0]
    in_bus = re.search(r'i2c|spi|qupv3|blsp', path, re.I)
    return bool(
        INTERESTING_NODE.match(n.name) or INTERESTING_NODE.match(base)
        or TOUCH_RE.search(comp) or TOUCH_RE.search(n.name)
        or re.search(r'qcom,(spmi|pm8998|pmi8998|ufshc|msm-imem|qpnp-power-on|msm-restart|mdss|spi-geni|i2c-qup|dsi)', comp)
        or (in_bus and re.search(r'/(i2c|spi)[^/]*/[^/]+$', path) and n.name.count('@') == 1 and n.props.get('reg') is not None and len(path.split('/')) > 3))


def report(root, idx, total):
    model = strings(root.props.get('model', b'')) or ['?']
    comp = strings(root.props.get('compatible', b'')) or ['?']
    print('=' * 70)
    print(f'DTB {idx + 1}/{total}: model={model[0]!r} compatible={comp}')
    print('=' * 70)
    seen = 0
    for path, n, cells in walk(root):
        if path == '/' or not matches(path, n):
            continue
        seen += 1
        print(f'\n{path}')
        for k, v in sorted(n.props.items()):
            if k in ('name', 'phandle', 'linux,phandle'):
                continue
            print(f'    {k} = {fmt(k, v, *cells)}')
    print(f'\n({seen} nodes shown)')


def selftest():
    """Round-trip a hand-built blob so the parser is checked without hardware."""
    names, nameoffs = bytearray(), {}

    def pname(n):
        if n not in nameoffs:
            nameoffs[n] = len(names); names.extend(n.encode() + b'\0')
        return nameoffs[n]

    def pad(b): return b + b'\0' * (-len(b) % 4)

    def node(name, props, kids=()):
        out = struct.pack('>I', 1) + pad(name.encode() + b'\0')
        for k, v in props:
            out += struct.pack('>III', 3, len(v), pname(k)) + pad(v)
        for kid in kids:
            out += kid
        return out + struct.pack('>I', 2)

    u = lambda *c: struct.pack('>%dI' % len(c), *c)
    tree = node('', [('#address-cells', u(2)), ('#size-cells', u(2)), ('model', b'Essential PH-1\0'), ('compatible', b'essential,mata\0qcom,msm8998\0')], [
        node('memory@80000000', [('device_type', b'memory\0'), ('reg', u(0, 0x80000000, 0, 0x80000000, 1, 0, 0, 0x80000000))]),
        node('soc', [('#address-cells', u(1)), ('#size-cells', u(1))], [
            node('ufshc@1da4000', [('compatible', b'qcom,ufshc\0'), ('reg', u(0x1da4000, 0x2500))]),
            node('i2c@c175000', [('compatible', b'qcom,i2c-qup\0'), ('reg', u(0xc175000, 0x600))], [
                node('synaptics@2c', [('compatible', b'synaptics,rmi4-i2c\0'), ('reg', u(0x2c)), ('interrupts', u(125, 2))])])])])
    strs = bytes(names)
    off_struct = 40 + 16
    blob = struct.pack('>10I', 0xd00dfeed, 0, off_struct, off_struct + len(tree) + 4, 40, 17, 16, 0, len(strs), len(tree) + 4)
    blob += b'\0' * 16 + tree + struct.pack('>I', 9) + strs
    blob = blob[:4] + struct.pack('>I', len(blob)) + blob[8:]
    assert len(split_blobs(b'xx' + blob + blob)) == 2
    root = parse(blob)
    out = [(p, n) for p, n, _ in walk(root) if matches(p, n)]
    paths = [p for p, _ in out]
    assert '/memory@80000000' in paths and '/soc/ufshc@1da4000' in paths, paths
    assert '/soc/i2c@c175000/synaptics@2c' in paths, paths
    report(root, 0, 1)
    print('selftest ok')


def main():
    if '--selftest' in sys.argv:
        return selftest()
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    blobs = split_blobs(open(args[0], 'rb').read())
    if not blobs:
        sys.exit('no device tree found')
    roots = [parse(b) for b in blobs]
    pick = [i for i, r in enumerate(roots)
            if re.search(r'mata|essential', ' '.join((strings(r.props.get('model', b'')) or []) + (strings(r.props.get('compatible', b'')) or [])), re.I)]
    if '--all' in sys.argv or not pick:
        pick = list(range(len(roots)))
    print(f'{len(roots)} device trees in {args[0]}; showing {len(pick)}', file=sys.stderr)
    for i in pick:
        report(roots[i], i, len(roots))


main()
