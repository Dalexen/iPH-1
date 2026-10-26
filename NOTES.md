# iPH-1 notes (Essential PH-1 / mata, MSM8998)

Read `README.md` first. The old engineering log of the original bring-up is `docs/BRINGUP-HISTORY.md`
(a different phone: its addresses and results do not apply here).

## State (2026-10-26)

Nothing has been built in CI or booted on a PH-1. Everything is derived from MSM8998 reference material.

Done:
- Board constants for the PH-1 (`shim/board.h`, `tools/mkadt.py`, `xnu/patches/0082-ph1-board.patch`).
- Hand-over to big core `0x100` (shim `big_entry`, `loader.c`): the little cores (Cortex-A53 class) have no
  16K granule; Cortex-A73 class cores do. A magenta band is painted if the big core has none either.
- ARMv8.0 kernel build: `-march=armv8-a+crypto`, `__ARM_PAN_AVAILABLE__ 0`.
- Four big cores in the ADT; SweetCPU accepts MPIDR 0x100-0x103 (0x0-0x3 only for the QEMU tree).
- The other SoC's keys/touch/USB/regulator drivers deleted (0082); `sweet_spmi_init` returns -1.
- `tools/mata-hwinfo.py` to dump the facts a driver needs from a stock boot.img.

Verified locally: 0082 applies on 0001-0081 (xnu-8796.141.3); shim compiles (clang syntax check); header
arithmetic (two L2 blocks for the framebuffer) preprocesses correctly; hwinfo tool self-test passes.
Not verified: kernel compile (CI only), anything on hardware.

Unverified guesses (README table): framebuffer 0x9d400000, GICR 0x17b00000, UFS 0x1da4000, RAM size,
MPIDR layout, TGran16 on Kryo 280 big cores (Cortex-A73 supports it; Kryo is semi-custom), v1 boot.img + appended DTB.

## Next action

Get `mata-hwinfo.txt` from a real PH-1 boot.img, correct the constants, then write the touch driver
(controller/bus/GPIO/supplies unknown until then) and the PM8998 key reader.
