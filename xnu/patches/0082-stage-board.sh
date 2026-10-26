#!/bin/bash
# dxb runs patches/*.sh from the XNU source root before applying *.patch.
# Optional: PH1_FB_PHYS=0x........ overrides the bootloader splash framebuffer
# address compiled into the early boot code (default 0x9d400000, taken from the
# msm8998 reference device trees; check it against your PH-1's live FDT).
set -euo pipefail

[[ "${MACHINE_CONFIG:-}" == SWEET ]] || exit 0
[[ -n "${PH1_FB_PHYS:-}" ]] || exit 0
[[ "$PH1_FB_PHYS" =~ ^0x[0-9a-fA-F]{8,9}$ ]] || { echo "bad PH1_FB_PHYS=$PH1_FB_PHYS" >&2; exit 1; }

printf '#define PH1_FB_PHYS %s\n' "$PH1_FB_PHYS" > osfmk/arm64/ph1_fb_override.h
