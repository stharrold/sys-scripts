# sys-scripts

macOS system maintenance scripts.

## Scripts

### `compact_transcripts.py`
Lossy compaction of Claude Code JSONL transcript files to reclaim disk space.

**Policy:**
- Per project dir under `~/.claude/projects/`: keep the 2 most recently modified transcripts intact.
- Skip files < 100 KB or modified within the last hour (active sessions).
- **Level A** (≥ 11 assistant turns): keep human-user lines + first/last 5 assistant turns; drop everything else.
- **Level B** (< 11 assistant turns): keep all human-user + all assistant lines; drop only `progress` and `tool_result` lines.
- Atomic: renames original to `.bak` before writing, deletes `.bak` on success.

```bash
# Preview what would be compacted (no changes made)
uv run python compact_transcripts.py --dry-run

# Execute compaction
uv run python compact_transcripts.py --execute

# Target a different base directory
uv run python compact_transcripts.py --execute --base /path/to/projects
```

**Typical result:** ~50% reduction across all transcripts; individual large files can reach 98%+ reduction.

---

### `disk_report.sh`
Quick macOS disk status: free space, local TM snapshots, and key cache sizes.

```bash
bash disk_report.sh
```

---

### `cleanup_snapshots.sh`
Delete all safe local Time Machine snapshots (skips `com.apple.os.update-*`).
APFS copy-on-write pins deleted bytes in snapshots — deletions don't reflect in `df` until snapshots are removed.

```bash
bash cleanup_snapshots.sh
```

---

### `eject_disk_images.sh`
Force-detach attached disk images (stale `.dmg` mounts, leftover iOS Simulator
runtime/volume images) with `hdiutil detach -force`. SIP-protected system
cryptexes (Metal toolchain, `/System/Cryptexes`) are detected and skipped —
they're held by `cryptexd`, return "Resource busy", and reattach on demand.
Dry-run by default.

```bash
bash eject_disk_images.sh              # preview (dry-run)
bash eject_disk_images.sh --execute    # detach
```

## Background: APFS snapshot pinning

On macOS, `df` free space does not immediately reflect deletions because local Time Machine snapshots pin the blocks (APFS is copy-on-write). After bulk deletions, run `cleanup_snapshots.sh` to realize the reclaim. `com.apple.os.update-*` snapshots are system-owned and must not be deleted.

## Background: uv cache hardlinks

`~/.cache/uv` hardlinks wheel content into `.venv` directories. `du` double-counts the bytes. Running `uv cache prune` removes unused entries; bytes still hardlinked into active venvs only free when those venvs are removed.
