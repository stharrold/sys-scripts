Run the macOS disk cleanup workflow for this machine.

## Step 1: Assess

```bash
bash disk_report.sh
```

Note from the output:
- **Container Free Space** — the authoritative number (not the `df` row)
- TM snapshot count
- Sizes of key dirs: CoreSimulator, uv cache, `.claude/projects`, Xcode/DerivedData, Documents/GitHub

## Step 2: Recommend targets (in priority order)

Present a table of targets with actual sizes from the report. Only include targets with meaningful savings (>200 MB). Standard priority order — skip any that are already small:

| Priority | Target | Command | Notes |
|----------|--------|---------|-------|
| 1 | CoreSimulator | `xcrun simctl delete unavailable` | Unused iOS simulator runtimes; can be 10–20 GB; safe |
| 2 | TM snapshots | `bash cleanup_snapshots.sh` | Required after bulk deletions to realize APFS reclaim |
| 3 | uv cache | `uv cache prune` | Safe; wheels still hardlinked in active venvs |
| 4 | Stale `.venv` dirs | `rm -rf <path>` | Confirm project is inactive before deleting |
| 5 | Xcode DerivedData | `rm -rf ~/Library/Developer/Xcode/DerivedData` | Xcode rebuilds on demand |
| 6 | Claude transcripts | `uv run python compact_transcripts.py --execute` | Run from sys-scripts dir; ~50% reduction typical |

Ask which targets to proceed with before executing anything destructive.

## Step 3: Execute approved steps

Run each command and report output. After any bulk file deletion, always run `cleanup_snapshots.sh` to realize the reclaim in `df`.

### APFS gotcha
Deletions on macOS don't appear in `df` until local TM snapshots are cleared. APFS copy-on-write pins the deleted blocks in snapshot history. `cleanup_snapshots.sh` removes all safe local snapshots (skips `com.apple.os.update-*`). Always run it after bulk deletes.

### uv cache note
`du` double-counts bytes hardlinked into active `.venv` dirs. The actual free-space gain from `uv cache prune` only shows after running `cleanup_snapshots.sh`.

### compact_transcripts.py details
- Covers ALL Claude Code sessions: scans `~/.claude/projects/` which includes `-private-tmp/` subdirs
- Keeps 2 newest transcripts per project intact; skips files <100 KB or modified within the last hour
- Level A (≥11 assistant turns): keeps human turns + first/last 5 assistant turns; drops tool results
- Level B: keeps all human+assistant, drops only progress/tool_result lines
- Always `--dry-run` first to preview, then `--execute`

## Step 4: Final report

```bash
bash disk_report.sh
```

Report free space before → after, total reclaimed, and any remaining targets. Update `.remember/remember.md` with session state.
