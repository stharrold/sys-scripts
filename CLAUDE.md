# sys-scripts

macOS system maintenance scripts. No pyproject.toml, no tests — run scripts directly.

## Scripts

```bash
bash disk_report.sh                                    # assess free space + cache sizes
bash cleanup_snapshots.sh                              # realize APFS reclaim after deletions
bash eject_disk_images.sh                              # preview detachable disk images (dry-run)
bash eject_disk_images.sh --execute                    # force-detach stale images, skip cryptexes
uv run python compact_transcripts.py --dry-run         # preview transcript compaction
uv run python compact_transcripts.py --execute         # compact + archive to Google Drive (local copy removed); --no-archive to skip move
```

## Notes

- `compact_transcripts.py` scans `~/.claude/projects/` which includes `-private-tmp/` subdirs
  (Claude Code stores `/private/tmp` sessions there), so it covers all sessions automatically.
- Disk cleanup sequence: `disk_report` → prune caches → `cleanup_snapshots` → `compact_transcripts`
- After `uv cache prune`, run `cleanup_snapshots.sh` twice: once to clear prior snapshots, then once more to clear the snapshot that captured the prune itself
- `eject_disk_images.sh` skips system cryptexes by image-path (`MetalToolchain`, `/System/Cryptexes`,
  `com.apple.security.cryptexd`) because `hdiutil info` stops reporting their mount point once `cryptexd`
  unmounts the fs while the image stays attached — a mount-point-only check misses them. CoreSimulator's
  own `Cryptex/Images/bundle/` images are NOT skipped (user-detachable). Truly-busy images still fail the
  `hdiutil detach -force` gracefully and are reported, not fatal.
- CoreSimulator cleanup: `xcrun simctl runtime list` to see installed runtimes (can be 8 GB each);
  `xcrun simctl runtime delete <UUID>` to remove the runtime, then `xcrun simctl delete unavailable`
  to also free device data (~7 GB). Running `xcrun simctl delete unavailable` alone (without deleting
  the runtime first) only removes device instances, NOT runtime disk images — silently succeeds without freeing space.
  Sometimes the first `delete unavailable` pass doesn't clear all now-orphaned devices immediately after a runtime
  delete (`CoreSimulator/Devices/` stays large even though `simctl list devices` shows them "unavailable") —
  run `delete unavailable` a second time and verify with `du -sh ~/Library/Developer/CoreSimulator/*/`.
  `delete unavailable` is a no-op if every device shows "Shutdown" rather than "unavailable" in `simctl list devices` —
  that's live device data, not orphaned. Reclaiming an old runtime's space (~7-20 GB) requires `simctl runtime delete <UUID>`
  first, which destroys any device data tied to that runtime — confirm the runtime is actually unused (check target OS in
  project build configs) before running it, since it's more destructive than the routine cleanup pass.
- `~/Documents/GitHub/` investigation: `du -sh ~/Documents/GitHub/*/` when total is large; `portfolio/data/snapshots/` accumulates ~960 MB weekly snapshots and is safe to prune. For any repo that's disproportionately large, check `du -sh <repo>/.git` to separate history bloat from working-tree data, and `git worktree list` for stale worktrees on suspiciously-named sibling dirs (e.g. `*_feature_TIMESTAMP_*`) — a worktree's own `.git` is a tiny ~4KB pointer file, so its real size lives outside `.git` and won't show up in a `.git`-size check.
- Git-LFS repos can have `.git` dominated by `lfs/objects/` (old blob versions retained locally). `git lfs prune --dry-run` reports reclaimable size safely — it only removes objects that are re-fetchable from `origin` and never touches unpushed/uncommitted objects. `git lfs prune` to actually reclaim.
- Transcript compaction has diminishing returns after the first run (~628 MB vs ~9 GB); skip if run recently
- `compact_transcripts.py --execute` moves compacted files to `~/Library/CloudStorage/GoogleDrive-.../My Drive/My_Drive/Data/Claude`; Drive must be mounted or use `--no-archive`
- uv cache can grow 50+ GB in days of heavy dev work; prune weekly with `uv cache prune`
- `~/Downloads/<month>/.tmp.driveupload/` holds Google Drive upload temp files locked by the Drive process; quit Drive from the menu bar before deleting, or delete from Finder after quitting
- Xcode auto-downloads simulator runtimes silently; disable with `defaults write com.apple.dt.Xcode DVTDownloadableAutomaticUpdate -bool NO` (Xcode 26 has no UI toggle — Components → Platform Support shows runtimes but no auto-download option). This only blocks background/idle auto-downloads — it does NOT stop `xcodebuild -destination 'platform=iOS Simulator,...'` from installing a runtime on demand when the targeted simulator isn't present. Runtimes will keep reappearing with any simulator-targeted build regardless of this setting; the CoreSimulator cleanup above is the durable fix, not prevention.
- Deleting `/Applications` items requires sudo; use Finder (right-click → Move to Trash) or run `! sudo rm -rf /Applications/<App>` in an interactive terminal — `rm -rf` without sudo returns Permission denied
