---
name: disk-cleanup
description: macOS disk space reclamation workflow for this machine. Use this skill whenever the user mentions running low on disk space, wants to free up space, asks about disk cleanup, or wants to know what's eating their disk. Also trigger when the user runs disk_report.sh and asks what to do next, after uv cache prune, or when free space looks low. This skill knows the exact tools, scripts, and APFS quirks specific to this repo.
---

# Disk Cleanup Workflow

This repo (`sys-scripts`) has three maintenance scripts. Always start by assessing current state, then recommend targets in priority order, get approval, execute, and report results.

## Step 1: Assess

```bash
bash disk_report.sh
```

Note from the output:
- **Container Free Space** — the authoritative number (not the `df` row)
- TM snapshot count
- Sizes of key dirs: CoreSimulator, uv cache, `.claude/projects`, Xcode/DerivedData, Documents/GitHub

## Step 2: Recommend targets (in priority order)

Present a table of targets with actual sizes from the report. Only include targets with meaningful savings (>200 MB). This is the standard priority order — skip any that are already small:

| Priority | Target | Command | Notes |
|----------|--------|---------|-------|
| 1 | CoreSimulator | `xcrun simctl delete unavailable` | Unused iOS simulator runtimes; can be 10–20 GB; safe |
| 2 | TM snapshots | `bash cleanup_snapshots.sh` | Required after bulk deletions to realize APFS reclaim |
| 3 | uv cache | `uv cache prune` | Safe; wheels still hardlinked in active venvs |
| 4 | Stale `.venv` dirs | `rm -rf <path>` | Confirm project is inactive before deleting |
| 5 | Xcode DerivedData | `rm -rf ~/Library/Developer/Xcode/DerivedData` | Xcode rebuilds on demand |
| 6 | Claude transcripts | `uv run python compact_transcripts.py --execute` | Run from sys-scripts dir; ~50% reduction typical |
| 7 | Google Chrome (if large) | Chrome → Settings → Privacy → Clear Browsing Data | Check size: `du -sh ~/Library/Application\ Support/Google/Chrome`; File System API storage (per-site) is the non-obvious large entry — use Chrome UI or investigate with user approval |

Ask which targets to proceed with before executing anything destructive.

## Step 3: Execute approved steps

Run each command and report output. After any bulk file deletion, always run `cleanup_snapshots.sh` to realize the reclaim in `df`.

### APFS gotcha
Deletions on macOS don't appear in `df` until local TM snapshots are cleared. APFS copy-on-write pins the deleted blocks in snapshot history. `cleanup_snapshots.sh` removes all safe local snapshots (skips `com.apple.os.update-*`). Always run it after bulk deletes.

### uv cache note
`du` double-counts bytes that are hardlinked into active `.venv` dirs. The actual free-space gain from `uv cache prune` only shows after running `cleanup_snapshots.sh`.

### compact_transcripts.py details
- Covers ALL Claude Code sessions: scans `~/.claude/projects/` which includes `-private-tmp/` subdirs (Claude stores `/private/tmp` sessions there)
- Keeps 2 newest transcripts per project intact; skips files <100 KB or modified within the last hour
- Level A (≥11 assistant turns): keeps human turns + first/last 5 assistant turns; drops tool results
- Level B: keeps all human+assistant, drops only progress/tool_result lines
- Always `--dry-run` first to preview, then `--execute`

## Step 4: Final report

```bash
bash disk_report.sh
```

Report:
- Free space before → after
- Total reclaimed (GB)
- Remaining targets for the next session (if any)

Update `.remember/remember.md` with the session state so the next session can pick up where this one left off.
