#!/usr/bin/env bash
# Quick disk status report for macOS APFS system.
# Shows: free space, local TM snapshots, and key cache sizes.

set -euo pipefail

echo "=== Disk Status $(date '+%Y-%m-%d %H:%M') ==="
echo ""

echo "--- Free space ---"
df -h /System/Volumes/Data | tail -1
diskutil info /System/Volumes/Data | grep "Container Free Space"
echo ""

echo "--- Local Time Machine snapshots (non-os) ---"
tmutil listlocalsnapshots / 2>/dev/null | grep -v "os.update" | grep -i timemachine || echo "  none"
echo ""

echo "--- Key cache sizes ---"
du -sh \
  "${HOME}/.cache/uv" \
  "${HOME}/.cache/huggingface" \
  "${HOME}/.claude/projects" \
  "${HOME}/Library/Developer/CoreSimulator" \
  "${HOME}/Library/Developer/Xcode/DerivedData" \
  "${HOME}/Library/Application Support/Google/DriveFS" \
  "${HOME}/Documents/GitHub" \
  2>/dev/null | sort -rh
