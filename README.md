# ios-sweet

**Apple's iOS 16 running on a Redmi Note 10 Pro.**

This project ports Apple's open-source XNU kernel (xnu-8796, the iOS 16 generation) to the Xiaomi Redmi Note 10 Pro (`sweet`, Qualcomm SM7150 / Snapdragon 732G). On top of it runs the **unmodified iOS 16.7.16 (20H392) userland of the iPhone X**: launchd, the system daemons, backboardd, SpringBoard and the stock apps.

As of **2026-10-18** the phone boots to the **iOS home screen**. You can unlock it, open Settings, pull down Control Center and the notification center, and use the touchscreen and the hardware buttons. Rendering runs entirely on the CPU; there is no GPU driver.

> Experimental bring-up, not a usable phone OS. Many things are missing or stubbed (see below), and Apple's security model is mostly switched off. It installs into the `userdata` partition and so **erases Android's user data**.

## Essential PH-1 (`mata`) port: experimental, untested

This fork adds a second target, the **Essential PH-1** (`mata`, Qualcomm MSM8998 / Snapdragon 835, 4 GB RAM, UFS 2.1, 1312x2560 panel), selected with `BOARD=mata` / `SWEET_BOARD=mata` / `--board mata`. The default is still `sweet`, and the sweet build output is byte-identical to before (checked for the ADT).

> **Nobody has booted this on a PH-1 yet.** The code was written without the hardware, from the msm8998 reference device trees and the sweet port. Everything below is what the code *should* do. Treat every "works" as "expected to work, unverified". If you try it, please report the first screen it reaches.

### What should work, and what does not

| Area | Expected on PH-1 | Why |
| --- | --- | --- |
| Shim boot, XNU entry, ADT | Should work | Same shim and kernel; the board constants (GIC, UFS, framebuffer, CPU) are switched to MSM8998 |
| UFS root (`userdata`) | Should work | The driver is plain UFSHCI and relies on the link ABL left up. Only the base address changes (`0x1da4000`) |
| iOS userland, SpringBoard, rendering | Should work if the above does | Software rendering to the ABL framebuffer, same as sweet |
| Display | Should work, if the framebuffer address is right | iPhone X canvas (1125x2436) centered in the 1312x2560 panel with black borders |
| CPU | **1 core only** (little cluster, `cpus=1`) | The SMP code assumes sweet's MPIDR layout (Aff1 = core); MSM8998 uses Aff1 = cluster, Aff0 = core |
| Touchscreen | **No** | Needs a new driver. The Goodix/GENI driver is for sweet; PH-1 touch is a different controller on a BLSP QUP I²C bus. Drivers are off by default on mata |
| Power / volume buttons | **No** | The PMIC (PM8998) uses a different SPMI arbiter generation than the sweet driver |
| Battery | Static 100 % | Same stub as sweet |
| USB (incl. USB networking) | **No** | The sweet USB code pokes SM7150 addresses; it is off on mata |
| Wi-Fi, Bluetooth, LTE, GPS, NFC, audio, camera, sensors, fingerprint | **No** | No drivers, as on sweet |
| GPU | **No** | CPU rendering only, as on sweet |
| Persistent kernel log | Should work | Same UFS path; read it from a recovery |

**Practical consequence:** with no touch and no buttons, the best case today is a PH-1 that boots to the iOS lock screen and sits there. You cannot interact with it. Input drivers are the next piece of work.

### Assumptions that may be wrong (check against your own phone)

These come from the msm8998 reference trees, not from a PH-1. Each is a one-line change:

| Assumption | Where | How to check |
| --- | --- | --- |
| Bootloader framebuffer at `0x9d400000` | `shim/board.h`, `xnu/patches/0082-stage-board.sh` (`SWEET_FB_PHYS`), `tools/mkadt.py --fb` | `cont_splash_mem` / `splash` node in your decompiled live FDT. Screen stays black or garbled if wrong |
| GIC redistributors at `0x17b00000` | `shim/board.h`, `tools/mkadt.py` | `interrupt-controller@17a00000` `reg` |
| UFS host at `0x1da4000` | same | `ufshc@1da4000` in the FDT |
| Virtual timer is INTID 19 (PPI 3) | already used on sweet | `timer` node `interrupts` |
| Usable RAM: 1.875 GiB at `0x1_0000_0000` | `tools/mkadt.py` (`--mem`) | `memory` node and `reserved-memory` regions. Lower it if the kernel faults early |
| ABL accepts a v1 boot.img with the DTB appended to the kernel | `shim/build.sh` | `fastboot boot` reports an error or reboots at once |
| Secure monitor offers PSCI | assumed | Shim prints `PSCI ver=` |

The shim reads the live FDT for the ramdisk, so it adapts to the memory layout of the payload but not to the constants above.

### Guide

Requirements are the same as for sweet (Linux PC, GitHub account for the kernel build, `aarch64-linux-gnu-gcc`, `mkbootimg`), plus a PH-1 with an **unlocked bootloader**. Unlocking and flashing `userdata` **erase all data on the phone**.

1. **Unlock and back up.** Enable *Developer options -> OEM unlocking*, then `fastboot flashing unlock`. Back up `persist`, `modemst1`, `modemst2`, `fsg`, `fsc`, `boot_a`, `boot_b` before touching anything (TWRP or another recovery with adb root; PH-1 has A/B slots). Do not commit the backups.
2. **Extract the stock device trees.** The PH-1 `boot.img` carries them appended to the kernel:
   ```sh
   python3 tools/extract_appended_dtb.py backup/boot_a.img dtb/mata_dtb
   ```
   Decompile one with `dtc -I dtb -O dts` and check the assumptions table above. Fix them first if they differ.
3. **Build the kernel for mata.** Run the workflow with the board input:
   ```sh
   gh workflow run xnu.yml -R YOU/iPH-1 -f board=mata
   gh run download RUN_ID -R YOU/iPH-1 -n xnu-kernel -D xnu/out
   ```
   If your framebuffer address differs, set `SWEET_FB_PHYS` in the workflow `env` (it is compiled into the early boot code).
4. **Build the iOS root.** Identical to sweet (section 2 of the guide below): `mkiosroot.sh`, `sweet-root-tweaks.py`, `img2simg`.
5. **Build the boot image.**
   ```sh
   python3 tools/mkadt.py shim/out/mata.adt --highmem --board mata   # add --fb 0x... / --mem 0x... if needed
   python3 tools/mkpayload.py xnu/out/kernel.development.sweet shim/out/mata.adt shim/out/payload.bin \
       --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30 sweetkeys=0 sweettouch=0 sweetusb=0'
   BOARD=mata shim/build.sh ../shim/out/payload.bin      # -> shim/out/shim-boot.img
   ```
6. **Flash and boot.**
   ```sh
   fastboot flash userdata ios16-root.simg      # erases Android data
   fastboot boot shim/out/shim-boot.img
   ```
   Expect red/white shim text first, then the kernel console, then a long wait (several minutes, one core) on the Apple logo.
7. **Debug.** If the screen stays black, the framebuffer address is the first suspect. Boot a recovery and run `tools/sweet-log-pull.sh logs/boot.txt`: the kernel log is kept at the end of `userdata`, which is independent of the display.

### What changed for mata

| File | Change |
| --- | --- |
| `shim/board.h`, `shim/build.sh` | Board constants (framebuffer, GIC, UFS, MPIDR); `BOARD=mata` builds a v1 boot.img with the DTB appended to the kernel; the reset path uses PSCI only |
| `tools/mkadt.py` | `--board`, `--fb`, `--mem`; one MSM8998 CPU node, 1312x2560 framebuffer node, mata identity |
| `tools/extract_appended_dtb.py` | New: pulls the appended DTBs out of a stock boot.img |
| `xnu/patches/0082-*` | Framebuffer address and size, early console and page-table mapping (two 32 MB blocks, since 13.4 MB at `0x9d400000` crosses a block boundary), centered iPhone X canvas on a larger panel, and the sm7150 MMIO drivers (keys, touch, USB) default to off |
| `.github/workflows/xnu.yml` | `board` input |

## What works (Redmi Note 10 Pro / sweet)

| Area | State |
| --- | --- |
| Boot | Stock Xiaomi bootloader → `fastboot boot` of our shim → XNU. Nothing is flashed to the boot partitions |
| CPU | 6 of the 8 cores (the six Cortex-A55s) via PSCI, 16K pages, GICv3 interrupts, timers |
| Memory | About 3.95 GiB of the upper DDR bank |
| Storage | Own UFS host driver; the iOS root is a journaled HFS+ volume in `userdata`, read/write |
| iOS userland | Real iPhone X 16.7.16 root filesystem and shared cache; launchd and the system daemons run |
| Display | Kernel IOSurface + IOMobileFramebuffer (`AppleCLCD`) services; CoreAnimation renders in software; frames are copied into the bootloader's framebuffer. Presented to iOS as an iPhone X panel (1125×2436) |
| GUI | backboardd, SpringBoard, lock screen, home screen, Control Center, notification center, Settings |
| Touch | Goodix GT9896 over I²C (GENI), rail enabled through RPMh, delivered as HID digitizer events |
| Buttons | Power, volume up/down (PMIC through SPMI) as HID consumer keys; lock/wake works |
| Battery | IOPMPowerSource service (static 100 %, charging icon; real fuel-gauge readout prepared) |
| Device identity | iPhone X (`iPhone10,3` / `D22AP`): no Home button, gesture UI |
| Activation | Native "Hactivation" path of mobileactivationd, chosen through device-tree security status. No Apple servers involved |

## What does not work (yet, sweet)

- **Navigation:** you cannot leave an app (the home gesture and AssistiveTouch Home do nothing yet).
- **No Wi-Fi, Bluetooth, cellular, audio, camera, sensors, GPS or SEP / Face ID.** Daemons for them start and fail or keep relaunching.
- **No GPU.** Everything is drawn by the CPU at roughly 20–30 fps. The two Cortex-A76 cores are not used yet.
- **Few apps.** The image has only what is on the system volume. There is no App Store, no Apple ID, and some Settings pages are empty.
- **Slow boot:** about 4 minutes on the Apple logo.
- **Security is off:** permissive code signing (AMFI) and sandbox policies, a stub AppleKeyStore, no data protection. Do not put anything personal on it.

## How it boots

```
ABL (stock Xiaomi bootloader, unlocked)
  -> fastboot boot shim-boot.img              (temporary; nothing is flashed to boot)
     -> shim: own MMU setup, reads the live FDT, loads the payload from the ramdisk
        -> XNU Mach-O + generated Apple Device Tree (ADT) + boot-args
           -> XNU -> UFS driver -> HFS+ root in the userdata partition
              -> dyld + shared cache -> launchd -> daemons -> backboardd + SpringBoard
```

There is no serial port (the debug UART is wired as SPI on this board). The kernel draws its console into the framebuffer that ABL leaves at `0x9c000000`, and keeps a persistent 4 MiB log ring at the end of `userdata`. You read that log from OrangeFox recovery with `tools/sweet-log-pull.sh`, so you don't have to film the screen.

## How to do it yourself

You need a Redmi Note 10 Pro (`sweet`, global or Indian variant, SM7150) with an **unlocked bootloader**, a Linux PC, and a GitHub account for the kernel build. This is the exact path used for the screenshots above; other variants or firmware may need changes. **Everything on `userdata` is lost.** Bootloaders, recovery, modem and persist partitions are never touched.

### 0. Back up the phone

Boot OrangeFox (or any recovery with adb root) temporarily and pull at least `persist`, `modemst1`, `modemst2`, `fsg`, `fsc` and `boot`, `dtbo`, `vbmeta`. They contain per-device calibration data. Keep them off git; `.gitignore` already excludes `backup/`, `dtb/` and `recovery/`.

The shim needs the stock DTB. Unpack your phone's stock `boot.img`:

```sh
python3 tools/unpack_bootv2.py backup/boot.img dtb/boot_unpacked   # -> dtb/boot_unpacked/dtb
```

### 1. Build the kernel

The kernel builds on GitHub's macOS runners with [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build). The workflow fetches xnu-8796, applies `xnu/patches/` in order, and also stages the pinned open-source libpthread, HFS and BearSSL sources it needs. Fork the repo (public repos get free macOS minutes) and run:

```sh
gh workflow run xnu.yml -R YOU/ios-sweet
gh run download RUN_ID -R YOU/ios-sweet -n xnu-kernel -D xnu/out
```

To check a patch locally before spending a CI run, `tools/xnu-cc.py` replays the compile commands of a previous CI log for single files.

### 2. Build the iOS root image

Download the iPhone X (iPhone10,3) iOS 16.7.16 (20H392) IPSW from Apple. Then, on Linux, with `apfs-fuse`, `hfsprogs` and sudo:

```sh
# OS, SystemOS and AppOS disk images from the IPSW (see BuildManifest.plist for their names)
tools/mkiosroot.sh OS.dmg SystemOS.dmg AppOS.dmg ios16-root.img 16G
sudo fsck.hfsplus -fy ios16-root.img
sudo mount -t hfsplus -o loop,force ios16-root.img /mnt/iosroot
sudo python3 tools/sweet-root-tweaks.py /mnt/iosroot
sudo umount /mnt/iosroot
img2simg ios16-root.img ios16-root.simg
```

`mkiosroot.sh` copies the OS volume and both cryptexes into one case-sensitive journaled HFS+ volume. It adds the dyld cache links, the plain system keybag and the log directories the daemons expect. `sweet-root-tweaks.py` applies the bring-up changes: it skips Setup, seeds the activation state, removes the baseband daemon, disables the watchdogs that kill slow apps and the crash-looping media paths, and so on. The script's header explains each change.

The device tree builder copies `/product` from the real iPhone X device tree, which MobileGestalt needs. Extract it once, without downloading the whole IPSW:

```sh
python3 tools/remotezip.py IPSW_URL DeviceTree.d22ap.im4p research/ipsw-x/dt
ipsw img4 im4p extract research/ipsw-x/dt/Firmware/all_flash/DeviceTree.d22ap.im4p -o research/ipsw-x/d22ap.adt
```

### 3. Build the boot image

Needs `aarch64-linux-gnu-gcc` and `mkbootimg`.

```sh
python3 tools/mkadt.py shim/out/sweet.adt --highmem
python3 tools/mkpayload.py xnu/out/kernel.development.sweet shim/out/sweet.adt shim/out/payload.bin \
    --cmdline 'debug=0xc serial=3 cpus=6 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30'
shim/build.sh ../shim/out/payload.bin      # -> shim/out/shim-boot.img
```

What the less obvious boot-args do:

| Boot-arg | Effect |
| --- | --- |
| `rd=ufsroot0 ufsrw=1 rootrw=1` | Root on the `userdata` partition, writable |
| `cpus=6` | Start the six A55 cores; `cpus=1` is the safe fallback |
| `launchd_unsecure_cache=1` | launchd accepts its job cache without AMFI |
| `wdt=-1 wdt_test=no_user_checkin` | No hardware watchdog |
| `sweetfb_noconsole=1` | Stop drawing kernel text over the GUI. It still goes to the persistent log; panics are drawn |
| `sweetfb_hz=30` | Panel refresh rate of the CPU copy |
| `sweettouch=0`, `sweetkeys=0` | Disable the touch or button driver |

### 4. Flash the root and boot

```sh
fastboot -S 512M flash userdata ios16-root.simg   # ~7 minutes; do not unplug
# Xiaomi's fastboot often hangs after a large flash: re-enter fastboot with Power + Volume down
fastboot boot shim/out/shim-boot.img
```

The first boot takes about 4–5 minutes on the Apple logo, then the lock screen appears. Swipe up to unlock. To get back to fastboot, hold Power + Volume down.

### 5. Read the kernel log

```sh
fastboot boot recovery/recovery.img        # OrangeFox, temporary
tools/sweet-log-pull.sh logs/boot.txt      # 4 MiB console ring from the end of userdata
adb reboot bootloader
```

The log contains crash reports with backtraces (`CRASH name ...`), IOKit traces of backboardd and SpringBoard, and the drivers' `SWEET ...` lines. `tools/sweet-crash.py` symbolicates them against the shared cache.

### QEMU

`tools/qemu-sweet.py` boots the same kernel on QEMU `virt` with a test RAM-disk root. It is useful for kernel-only changes; see `NOTES.md`.

## Repository layout

| Path | What |
| --- | --- |
| `shim/` | Bare-metal boot shim (C + asm) packed as an Android boot.img v2 |
| `xnu/patches/` | The XNU patch series (applied in order by CI), plus staging scripts for libpthread, HFS and BearSSL |
| `.github/workflows/xnu.yml` | Kernel CI build |
| `tools/mkadt.py` | (`--board mata` for the PH-1) Generates the Apple Device Tree from sweet's MMIO layout and the iPhone X identity |
| `tools/mkpayload.py` | Packs kernel + ADT + boot-args into the shim payload |
| `tools/mkiosroot.sh` | Builds the HFS+ iOS root from the IPSW images |
| `tools/sweet-root-tweaks.py` | Bring-up changes to the root (Setup skip, activation, daemons) |
| `tools/sweet-log-pull.sh`, `sweet-log.py` | Read the persistent kernel log from recovery |
| `tools/sweet-crash.py` | Symbolicate console crash reports |
| `tools/xnu-cc.py` | Local single-file compile check from a CI log |
| `tools/qemu-sweet.py` | QEMU test boots with framebuffer text decoding |
| `tools/adt.py`, `remotezip.py`, `unpack_bootv2.py`, `sparsediff.py` | Helpers |
| `NOTES.md` | Detailed engineering log: every boot, crash and decision, plus hardware facts |

Not in git: partition backups, live device trees, recovery images, Apple firmware and root images, and downloaded or generated build trees. They contain device serials and calibration data, or Apple's copyrighted files.

## Kernel patches

| # | What |
| --- | --- |
| 0001–0009 | Toolchain compatibility, SWEET machine config, non-PAC arm64, stubs for Apple-internal pieces |
| 0010–0018 | Early framebuffer console, physmap fix, PRNG without corecrypto, device-tree platform expert, timer PPI, boot CPU driver |
| 0019–0020 | Apple open-source libpthread kernel provider; BearSSL AES |
| 0021–0027 | RAM-disk root, mockfs, SHA-256, minimal AMFI, Apple open-source HFS+, MD5 |
| 0028–0034 | UFS host driver and root device, read/write root, DMA above 4 GiB |
| 0035–0045 | Entitlements, bindfs, AppleKeyStore stub, IOWatchdog, console crash reports |
| 0046 | IOSurface (IOCoreSurfaceRoot) and IOMobileFramebuffer (AppleCLCD) services |
| 0047–0055 | Diagnostics: persistent log, /dev/null tee, IOKit trace, heap strings and user stack sampler on crash; permissive Sandbox policy; HFS rename-swap; AppleKeyStore selectors |
| 0056–0057 | Throttled panel copy; no external identity resolver |
| 0058 | HID event services. Apple's IOHIDFamily-1915.140.3 user client and event queue, matching the iOS 16.7 userland |
| 0059 | iPhone X identity (`hw.product` / `hw.target` from the device tree) |
| 0060 | Power and volume keys over SPMI; touch over GENI I²C |
| 0061 | Present the display as 1125×2436 |
| 0062 | RPMh regulator vote for the touch rail; battery power source |
| 0063 | GENI FIFO packing fix and the Goodix GT9896 protocol |
| 0064 | Grant PRIV_WORK_INTERVAL (UIKit's CoreAnimation work interval) |
| 0065 | SMP: secondary A55 cores via PSCI CPU_ON |
| 0066–0067 | Fault-region crash info; console mute |
| 0068 | IOSurface lookup semantics for already-mapped surfaces |
| 0069 | Batched persistent-log flushes |
| 0082 | Selectable board (sweet / mata): framebuffer constants, centered canvas, SoC drivers off by default on mata |

## Key hardware facts

- RAM: payloads use the upper bank, `0x100000000` + `0xfcc00000` (about 3.95 GiB), above Qualcomm's protected carve-outs.
- GICv3 with security extensions: the timer goes through Group 1 IRQ (virtual timer INTID 19), not FIQ as on Apple silicon.
- PSCI through `smc`, 19.2 MHz timer, ARMv8.2 without pointer authentication. MPIDR uses Aff1 for the core number.
- Panel: 1080×2400 DSC video mode, continuous splash from ABL, no refresh kick needed.
- Touch: Goodix GT9896 at I²C `0x5d` on QUP SE7 (`0xa84000`), powered by PM6150L LDO11 through RPMh.
- Buttons: power and volume down on the PM6150 PON block, volume up on PM6150L GPIO2 (SPMI SID 4).

More in [`NOTES.md`](NOTES.md).

## Credits

Built on Apple's open-source releases (xnu, IOHIDFamily, libpthread, hfs), [BearSSL](https://bearssl.org), [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build), [ipsw](https://github.com/blacktop/ipsw), Qualcomm/Xiaomi's published Linux kernel sources for the hardware details, and [OrangeFox Recovery](https://orangefox.download). iOS itself is Apple's and is not distributed here.
