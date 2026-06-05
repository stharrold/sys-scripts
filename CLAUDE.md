# sys-scripts

macOS system maintenance scripts. No pyproject.toml, no tests — run scripts directly.

## Scripts

```bash
bash disk_report.sh                                    # assess free space + cache sizes
bash cleanup_snapshots.sh                              # realize APFS reclaim after deletions
uv run python compact_transcripts.py --dry-run         # preview transcript compaction
uv run python compact_transcripts.py --execute         # compact (~50% reduction typical)
```

## Notes

- `compact_transcripts.py` scans `~/.claude/projects/` which includes `-private-tmp/` subdirs
  (Claude Code stores `/private/tmp` sessions there), so it covers all sessions automatically.
- Disk cleanup sequence: `disk_report` → prune caches → `cleanup_snapshots` → `compact_transcripts`
- After `uv cache prune`, run `cleanup_snapshots.sh` to see reclaim reflected in `df`
- CoreSimulator cleanup: `xcrun simctl runtime list` to see installed runtimes (can be 8 GB each);
  `xcrun simctl runtime delete <UUID>` to remove one. `xcrun simctl delete unavailable` only removes
  device instances, NOT runtimes — it will silently succeed without freeing space.
- `~/Documents/GitHub/` investigation: `du -sh ~/Documents/GitHub/*/` when total is large; `portfolio/data/snapshots/` accumulates ~960 MB weekly snapshots and is safe to prune
- Transcript compaction has diminishing returns after the first run (~628 MB vs ~9 GB); skip if run recently
