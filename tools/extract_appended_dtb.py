#!/usr/bin/env python3
"""Pull the appended device trees out of a stock Android boot.img (v0/v1).

  extract_appended_dtb.py boot.img OUT_DTB [--list]

MSM8998 devices such as the Essential PH-1 ship the kernel as Image.gz-dtb:
the (gzipped) kernel followed by one or more concatenated FDT blobs. ABL picks
the one matching the board. This writes every FDT it finds back to back, which
is exactly what shim/build.sh BOARD=mata appends to the shim Image.
"""
import struct, sys

FDT_MAGIC = b'\xd0\x0d\xfe\xed'


def kernel_of(b):
    assert b[:8] == b'ANDROID!', 'not an Android boot image'
    ks, ps = struct.unpack_from('<I', b, 8)[0], struct.unpack_from('<I', b, 36)[0]  # kernel_size, page_size
    return b[ps:ps + ks]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    k = kernel_of(open(sys.argv[1], 'rb').read())
    out, pos, blobs = [], 0, []
    while True:
        i = k.find(FDT_MAGIC, pos)
        if i < 0:
            break
        total = struct.unpack_from('>I', k, i + 4)[0]
        version = struct.unpack_from('>I', k, i + 20)[0]
        if 0x100 < total <= len(k) - i and 1 <= version <= 17:
            blobs.append((i, total))
            pos = i + total
        else:
            pos = i + 4
    if not blobs:
        sys.exit('no appended device tree found (is this a v2 image with a separate dtb? use unpack_bootv2.py)')
    for n, (off, total) in enumerate(blobs):
        print(f'dtb {n}: kernel+0x{off:x}, {total} bytes')
        out.append(k[off:off + total])
    if '--list' not in sys.argv:
        open(sys.argv[2], 'wb').write(b''.join(out))
        print(f'{sys.argv[2]}: {len(blobs)} trees')


main()
