# Working on iPH-1 (iOS on the Essential PH-1)

- Read `NOTES.md` before starting; it has the current state, the unverified
  assumptions and the next concrete action. `docs/BRINGUP-HISTORY.md` is an
  archive from another phone: its addresses and results do not apply.
- Update the handoff in `NOTES.md` after each milestone and before stopping.
  Record commits, CI run IDs, exact build/boot results and unfinished work.
  Distinguish observations from guesses.
- Commit completed changes. Use `gh` for GitHub Actions kernel builds and logs.
  Local single-file cross-compiles are useful before spending a CI run.
- Bring-up uses temporary `fastboot boot` images. Flashing `userdata` erases
  Android; keep bootloaders, recovery, modem, persist and the backups intact,
  and confirm each destructive step with the user before running it.
- Keep device dumps, serial numbers and downloaded Apple artifacts out of git.
