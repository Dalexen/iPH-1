# iPH-1

**Apple's iOS 16 on the Essential PH-1.**

This project ports Apple's open-source XNU kernel (xnu-8796, the iOS 16 generation) to the Essential PH-1 (`mata`, Qualcomm MSM8998 / Snapdragon 835, 4 GB RAM, UFS, 1312x2560 panel). On top of it runs the **unmodified iOS 16.7.16 (20H392) userland of the iPhone X**: launchd, the system daemons, backboardd, SpringBoard and the stock apps.

> **Status: untested.** Nobody has booted this on a PH-1. It was written without the hardware, from public MSM8998 reference material and the kernel/userland work this repository inherits. Everything marked "expected" below is a prediction, not an observation. If you try it, the first thing worth reporting is which screen it reaches.
>
> It is not a usable phone OS: no touch, no buttons, CPU rendering, Apple's security model switched off. It installs into `userdata` and **erases Android**.

## What to expect

| Area | Expected | Notes |
| --- | --- | --- |
| Boot | Should work, if the assumptions below hold | Stock bootloader (unlocked) -> `fastboot boot` of the shim -> XNU. Nothing is flashed to the boot partitions |
| CPU | **4 cores: the big cluster only** | The kernel needs the 16K page granule. The little cores (Cortex-A53 class) lack it, the big cores (Cortex-A73 class) have it, so the shim hands over to core `0x100` and the little cores stay off |
| ISA level | ARMv8.0 | Kryo 280 has no PAN and no LSE atomics; the kernel is built `-march=armv8-a+crypto` with PAN off |
| Storage | Should work | Own UFSHCI driver on the link the bootloader leaves up; the iOS root is a journaled HFS+ volume in `userdata` |
| iOS userland | Should work if the kernel does | iPhone X 16.7.16 root and shared cache; launchd and the system daemons |
| Display | Should work if the framebuffer address is right | CPU-rendered, copied into the bootloader framebuffer; the iPhone X canvas (1125x2436) is centered in the 1312x2560 panel with black borders |
| Device identity | iPhone X (`iPhone10,3` / `D22AP`) | Gesture UI, no Home button |
| Activation | Native "Hactivation" path, no Apple servers | |
| Kernel log | Should work | 4 MiB ring at the end of `userdata`, read from a recovery |
| **Touchscreen** | **No** | No driver. The controller is not identified yet (see "Next work") |
| **Power / volume keys** | **No** | No driver. Needs the PM8998 PMIC over SPMI |
| Battery | Static 100 % | Stub service |
| USB (incl. USB networking) | No | |
| Wi-Fi, Bluetooth, LTE, GPS, NFC, audio, camera, sensors, fingerprint | No | No drivers |
| GPU | No | Everything is drawn by the CPU |
| Little cores | Not used | See CPU above |
| App Store, Apple ID | No | |

**Practical consequence:** with no touch and no keys, the best case today is a PH-1 that boots to the iOS lock screen and sits there. You cannot interact with it.

## Assumptions to check on your phone

These values come from the MSM8998 reference device trees, not from a PH-1. `tools/mata-hwinfo.py` prints the real ones from your own `boot.img`.

| Assumption | Where it lives | If wrong |
| --- | --- | --- |
| Bootloader framebuffer at `0x9d400000` | `shim/board.h`, `tools/mkadt.py` (`--fb`), workflow input `fb_phys` | Black or garbled screen |
| GIC distributor `0x17a00000`, redistributors `0x17b00000` | `shim/board.h`, `tools/mkadt.py` | Hang right after the kernel starts |
| UFS host `0x1da4000` | `shim/board.h`, `tools/mkadt.py` | Kernel cannot find its root |
| Big cores are MPIDR `0x100`-`0x103` | `shim/board.h`, `tools/mkadt.py` | Hand-over fails (`could not start the big core`) |
| Big cores report the 16K granule | checked at run time | A magenta band at the top of the screen, then a halt |
| Usable RAM: 1.875 GiB at `0x1_0000_0000` | `tools/mkadt.py` (`--mem`) | Early faults; lower it |
| Virtual timer is INTID 19 | ADT | No scheduler ticks |
| The bootloader accepts a v1 boot.img with the device trees appended to the kernel | `shim/build.sh` | `fastboot boot` errors or reboots at once |
| The secure monitor provides PSCI | assumed | Hand-over fails |

## Guide

You need a PH-1 with an **unlocked bootloader**, a Linux PC, a GitHub account for the kernel build, `aarch64-linux-gnu-gcc`, `mkbootimg`, and the iPhone X IPSW. Unlocking and flashing `userdata` **erase all data on the phone**. Bootloader, recovery, modem and persist partitions are never touched.

### 1. Unlock and back up

Enable *Developer options -> OEM unlocking*, then `fastboot flashing unlock`. Back up `persist`, `modemst1`, `modemst2`, `fsg`, `fsc`, `boot_a`, `boot_b` (the PH-1 has A/B slots) with a recovery that has adb root. They hold per-device calibration data; keep them out of git (`.gitignore` already excludes `backup/`, `dtb/` and `recovery/`).

### 2. Check the assumptions

```sh
python3 tools/extract_appended_dtb.py backup/boot_a.img dtb/mata_dtb
python3 tools/mata-hwinfo.py backup/boot_a.img > mata-hwinfo.txt
```

`mata-hwinfo.txt` lists the memory map, the splash framebuffer reservation, GIC, UFS, the CPU nodes, and every touch / SPMI / PON / key / display node. Compare it with the table above and fix `shim/board.h` and `tools/mkadt.py` first. If you open an issue, attach this file.

### 3. Build the kernel

The kernel builds on GitHub's macOS runners with [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build). The workflow fetches xnu-8796, applies `xnu/patches/` in order and stages the pinned open-source libpthread, HFS and BearSSL sources it needs. Fork the repo and run:

```sh
gh workflow run xnu.yml -R YOU/iPH-1                      # add -f fb_phys=0x........ if your framebuffer differs
gh run download RUN_ID -R YOU/iPH-1 -n xnu-kernel -D xnu/out
```

The framebuffer address is compiled into the early boot code, which is why it is a workflow input. `tools/xnu-cc.py` replays compile commands from a CI log to check a single file locally.

### 4. Build the iOS root image

Download the iPhone X (iPhone10,3) iOS 16.7.16 (20H392) IPSW from Apple. On Linux with `apfs-fuse`, `hfsprogs` and sudo:

```sh
tools/mkiosroot.sh OS.dmg SystemOS.dmg AppOS.dmg ios16-root.img 16G
sudo fsck.hfsplus -fy ios16-root.img
sudo mount -t hfsplus -o loop,force ios16-root.img /mnt/iosroot
sudo python3 tools/sweet-root-tweaks.py /mnt/iosroot
sudo umount /mnt/iosroot
img2simg ios16-root.img ios16-root.simg
```

`mkiosroot.sh` copies the OS volume and both cryptexes into one case-sensitive journaled HFS+ volume and adds the dyld cache links, the plain system keybag and the log directories the daemons expect. `sweet-root-tweaks.py` applies the bring-up changes (skip Setup, seed activation, remove the baseband daemon, disable the watchdogs that kill slow apps). Its header explains each one.

The device tree builder copies `/product` from the real iPhone X device tree, which MobileGestalt needs. Extract it once without downloading the whole IPSW:

```sh
python3 tools/remotezip.py IPSW_URL DeviceTree.d22ap.im4p research/ipsw-x/dt
ipsw img4 im4p extract research/ipsw-x/dt/Firmware/all_flash/DeviceTree.d22ap.im4p -o research/ipsw-x/d22ap.adt
```

### 5. Build the boot image

```sh
python3 tools/mkadt.py shim/out/mata.adt --highmem        # --fb 0x... / --mem 0x... to match step 2
python3 tools/mkpayload.py xnu/out/kernel.development.sweet shim/out/mata.adt shim/out/payload.bin \
    --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30'
shim/build.sh ../shim/out/payload.bin                     # -> shim/out/shim-boot.img
```

Start with `cpus=1` (just the first big core). Once it boots, try `cpus=4`.

| Boot-arg | Effect |
| --- | --- |
| `rd=ufsroot0 ufsrw=1 rootrw=1` | Root on the `userdata` partition, writable |
| `cpus=N` | Number of big cores to start (1-4) |
| `launchd_unsecure_cache=1` | launchd accepts its job cache without AMFI |
| `wdt=-1 wdt_test=no_user_checkin` | No hardware watchdog |
| `sweetfb_noconsole=1` | Stop drawing kernel text over the GUI. It still goes to the persistent log; panics are drawn |
| `sweetfb_hz=30` | Refresh rate of the CPU copy into the panel |

### 6. Flash and boot

```sh
fastboot flash userdata ios16-root.simg        # erases Android data
fastboot boot shim/out/shim-boot.img
```

You should see red shim text first (INITRD, PHYS, SEGS, BOOTARG, `starting on the big core`), then the kernel console, then a long wait on the Apple logo (several minutes), then the lock screen. A magenta band across the top means the big core has no 16K granule. `could not start the big core` means the PSCI hand-over failed.

### 7. Read the kernel log

The log is kept at the end of `userdata`, independent of the display, so it works even when the screen stays black:

```sh
fastboot boot recovery.img                     # any recovery with adb root, e.g. TWRP for the PH-1
tools/sweet-log-pull.sh logs/boot.txt
adb reboot bootloader
```

It contains crash reports with backtraces (`CRASH name ...`), IOKit traces of backboardd and SpringBoard, and the drivers' `SWEET ...` lines. `tools/sweet-crash.py` symbolicates them against the shared cache.

### QEMU

`tools/qemu-sweet.py` boots the same kernel on QEMU `virt` with a test RAM-disk root, for kernel-only changes; see `docs/QEMU_TESTING.md`. It does not model Kryo 280, so it cannot catch ARMv8.0-only problems.

## How it boots

```
bootloader (stock, unlocked)
  -> fastboot boot shim-boot.img        (temporary; nothing is flashed to boot)
     -> shim on little core 0: reads the live FDT, loads the payload from the ramdisk
        -> PSCI CPU_ON of big core 0x100
           -> XNU Mach-O + generated Apple Device Tree (ADT) + boot-args
              -> XNU -> UFS driver -> HFS+ root in userdata
                 -> dyld + shared cache -> launchd -> daemons -> backboardd + SpringBoard
```

There is no serial port. The kernel draws its console into the framebuffer the bootloader leaves behind and keeps the persistent log described above.

## Next work

1. **Touchscreen.** The controller, its bus (a BLSP QUP I2C bus on MSM8998), address, interrupt GPIO and supplies are not known yet. Run `tools/mata-hwinfo.py` on a stock `boot.img` and share the output: it lists every candidate node. The HID layer (`iokit/Kernel/arm/hid/SweetHID.cpp`, patch 0058) is ready to receive digitizer events; only the hardware driver is missing.
2. **Power and volume keys.** PM8998 over the SPMI arbiter (a different register generation than the one the inherited code was written for, which is why that code was removed). Same input needed.
3. **Little cores.** They need either a 4K-page kernel or a hand-over strategy that never runs the kernel on them. Not planned.
4. USB networking, battery, display power.

## Repository layout

| Path | What |
| --- | --- |
| `shim/` | Bare-metal boot shim (C + asm), packed as an Android boot.img v1 with the stock DTBs appended. `board.h` holds the PH-1 constants |
| `xnu/patches/` | The XNU patch series (applied in order by CI) and the staging scripts for libpthread, HFS and BearSSL |
| `.github/workflows/xnu.yml` | Kernel CI build |
| `tools/mkadt.py` | Generates the Apple Device Tree from the PH-1 MMIO layout and the iPhone X identity |
| `tools/mata-hwinfo.py`, `extract_appended_dtb.py` | Read the stock device trees from a PH-1 `boot.img` |
| `tools/mkpayload.py` | Packs kernel + ADT + boot-args into the shim payload |
| `tools/mkiosroot.sh`, `sweet-root-tweaks.py` | Build the HFS+ iOS root from the IPSW images and apply the bring-up changes |
| `tools/sweet-log-pull.sh`, `sweet-log.py`, `sweet-crash.py` | Read and symbolicate the persistent kernel log |
| `tools/qemu-sweet.py`, `xnu-cc.py`, `adt.py`, `remotezip.py`, `unpack_bootv2.py`, `sparsediff.py`, `validate-repo.py` | Helpers |
| `docs/BRINGUP-HISTORY.md` | Archived engineering log of the original bring-up on another phone. Shared design, **not** PH-1 facts |
| `NOTES.md` | Current PH-1 notes and handoff |

The internal names (`sweet` in file names, patch names, the `SWEET` machine config and `SWEET ...` log lines) are the inherited code name of the kernel work. They are not renamed so the patch series stays applicable.

## Kernel patches

| # | What |
| --- | --- |
| 0001-0009 | Toolchain compatibility, machine config, non-PAC arm64, stubs for Apple-internal pieces |
| 0010-0018 | Early framebuffer console, physmap fix, PRNG without corecrypto, device-tree platform expert, timer PPI, boot CPU driver |
| 0019-0020 | Apple open-source libpthread kernel provider; BearSSL AES |
| 0021-0027 | RAM-disk root, mockfs, SHA-256, minimal AMFI, Apple open-source HFS+, MD5 |
| 0028-0034 | UFS host driver and root device, read/write root, DMA above 4 GiB |
| 0035-0045 | Entitlements, bindfs, AppleKeyStore stub, IOWatchdog, console crash reports |
| 0046 | IOSurface (IOCoreSurfaceRoot) and IOMobileFramebuffer (AppleCLCD) services |
| 0047-0057 | Diagnostics (persistent log, IOKit trace, samplers), permissive Sandbox policy, HFS rename-swap, AppleKeyStore selectors, throttled panel copy |
| 0058-0059 | HID event services (Apple's IOHIDFamily user client and event queue); iPhone X identity |
| 0060-0081 | Inherited hardware drivers and tuning from the original phone (touch, keys, regulators, USB networking, SMP). The touch, keys, regulator and USB drivers are **deleted by 0082** because they poke another SoC's MMIO |
| 0082 | PH-1 target: framebuffer constants, early console and page-table mapping (two 32 MB blocks), centered iPhone X canvas on the larger panel, ARMv8.0 build (no PAN, no LSE), four big cores, removal of the other SoC's drivers |

## Credits

Built on Apple's open-source releases (xnu, IOHIDFamily, libpthread, hfs), [BearSSL](https://bearssl.org), [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build) and [ipsw](https://github.com/blacktop/ipsw). iOS itself is Apple's and is not distributed here.
