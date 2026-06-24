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
- After `uv cache prune`, run `cleanup_snapshots.sh` to see reclaim reflected in `df`
- `eject_disk_images.sh` skips system cryptexes by image-path (`MetalToolchain`, `/System/Cryptexes`,
  `com.apple.security.cryptexd`) because `hdiutil info` stops reporting their mount point once `cryptexd`
  unmounts the fs while the image stays attached — a mount-point-only check misses them. CoreSimulator's
  own `Cryptex/Images/bundle/` images are NOT skipped (user-detachable). Truly-busy images still fail the
  `hdiutil detach -force` gracefully and are reported, not fatal.
- CoreSimulator cleanup: `xcrun simctl runtime list` to see installed runtimes (can be 8 GB each);
  `xcrun simctl runtime delete <UUID>` to remove one. `xcrun simctl delete unavailable` only removes
  device instances, NOT runtimes — it will silently succeed without freeing space.
- `~/Documents/GitHub/` investigation: `du -sh ~/Documents/GitHub/*/` when total is large; `portfolio/data/snapshots/` accumulates ~960 MB weekly snapshots and is safe to prune
- Transcript compaction has diminishing returns after the first run (~628 MB vs ~9 GB); skip if run recently
- `compact_transcripts.py --execute` moves compacted files to `~/Library/CloudStorage/GoogleDrive-.../My Drive/My_Drive/Data/Claude`; Drive must be mounted or use `--no-archive`
- uv cache can grow 50+ GB in days of heavy dev work; prune weekly with `uv cache prune`
