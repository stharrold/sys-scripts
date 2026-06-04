#!/usr/bin/env python3
"""
Lossy compaction of Claude Code JSONL transcript files.

Policy (per project directory under ~/.claude/projects/):
  - Keep the 2 most recently modified transcripts intact.
  - Skip files modified within the last hour (active sessions).
  - Skip files smaller than 100 KB (no meaningful savings).
  - Level A (>= MIN_ASSISTANT_TO_COMPACT assistant turns):
      keep human_user lines + first KEEP_FIRST_ASSISTANT + last KEEP_LAST_ASSISTANT
      assistant turns; drop everything else.
  - Level B (< MIN_ASSISTANT_TO_COMPACT assistant turns):
      keep all human_user + all assistant lines; drop progress and tool_result lines.

Atomic safety: rename original to .bak BEFORE writing, delete .bak after success.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

TINY_THRESHOLD_BYTES = 100_000
RECENT_THRESHOLD_SECONDS = 3600
KEEP_NEWEST_PER_PROJECT = 2
KEEP_FIRST_ASSISTANT = 5
KEEP_LAST_ASSISTANT = 5
MIN_ASSISTANT_TO_COMPACT = 11


def classify_line(record: dict) -> str:
    t = record.get("type", "")
    if t == "assistant":
        return "assistant"
    if t == "progress":
        return "progress"
    if t == "user":
        content = record.get("message", {}).get("content", record.get("content", ""))
        if isinstance(content, list):
            return "tool_user"
        return "human_user"
    return "other"


def compact_lines(lines: list[str]) -> list[str] | None:
    records = []
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        try:
            records.append((line, json.loads(line)))
        except json.JSONDecodeError:
            records.append((line, None))

    assistant_indices = [i for i, (_, r) in enumerate(records) if r and classify_line(r) == "assistant"]

    if len(assistant_indices) >= MIN_ASSISTANT_TO_COMPACT:
        keep_assistant = set(assistant_indices[:KEEP_FIRST_ASSISTANT] + assistant_indices[-KEEP_LAST_ASSISTANT:])
        out = []
        for i, (raw, r) in enumerate(records):
            if r is None:
                continue
            cls = classify_line(r)
            if cls == "human_user":
                out.append(raw)
            elif cls == "assistant" and i in keep_assistant:
                out.append(raw)
        level = "A"
    else:
        out = []
        for raw, r in records:
            if r is None:
                continue
            cls = classify_line(r)
            if cls in ("human_user", "assistant"):
                out.append(raw)
        level = "B"

    marker = json.dumps({
        "type": "_compaction_marker",
        "level": level,
        "original_lines": len(records),
        "compacted_lines": len(out),
        "compacted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    out.append(marker)
    return out


def get_project_groups(base: Path) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for p in base.rglob("*.jsonl"):
        if p.suffix == ".bak":
            continue
        project = p.parent.name
        groups.setdefault(project, []).append(p)
    return groups


def should_skip(p: Path, now: float) -> str | None:
    try:
        st = p.stat()
    except OSError:
        return "stat error"
    if st.st_size < TINY_THRESHOLD_BYTES:
        return f"tiny ({st.st_size // 1024} KB)"
    if (now - st.st_mtime) < RECENT_THRESHOLD_SECONDS:
        return "recent (<1h)"
    if p.with_suffix(".jsonl.bak").exists():
        return "already has .bak"
    return None


def process_file(p: Path, dry_run: bool) -> tuple[int, int] | None:
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    compacted = compact_lines(lines)
    if compacted is None:
        return None
    before = p.stat().st_size
    if dry_run:
        after_est = sum(len(l) + 1 for l in compacted)
        return before, after_est
    bak = p.with_suffix(".jsonl.bak")
    p.rename(bak)
    try:
        p.write_text("\n".join(compacted) + "\n", encoding="utf-8")
        after = p.stat().st_size
        bak.unlink()
        return before, after
    except Exception:
        if bak.exists() and not p.exists():
            bak.rename(p)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact Claude JSONL transcripts")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    parser.add_argument("--base", default=str(Path.home() / ".claude" / "projects"),
                        help="Base directory to scan (default: ~/.claude/projects)")
    args = parser.parse_args()

    dry_run = args.dry_run
    base = Path(args.base).expanduser()
    now = time.time()

    groups = get_project_groups(base)
    total_before = total_after = files_processed = files_skipped = 0

    for project, files in sorted(groups.items()):
        files_sorted = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
        for i, p in enumerate(files_sorted):
            if i < KEEP_NEWEST_PER_PROJECT:
                files_skipped += 1
                continue
            reason = should_skip(p, now)
            if reason:
                files_skipped += 1
                continue
            try:
                result = process_file(p, dry_run)
            except Exception as e:
                print(f"  ERROR {p.name}: {e}", file=sys.stderr)
                continue
            if result:
                before, after = result
                saved = before - after
                total_before += before
                total_after += after
                files_processed += 1
                pct = 100 * saved / before if before else 0
                tag = "[dry-run] " if dry_run else ""
                print(f"  {tag}{p.parent.name}/{p.name}: {before//1024//1024}MB -> {after//1024//1024}MB ({pct:.0f}% reduction)")

    saved_total = total_before - total_after
    mode = "DRY RUN" if dry_run else "EXECUTED"
    print(f"\n[{mode}] {files_processed} files compacted, {files_skipped} skipped")
    print(f"  Before: {total_before/1024/1024:.1f} MB  After: {total_after/1024/1024:.1f} MB  Saved: {saved_total/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
