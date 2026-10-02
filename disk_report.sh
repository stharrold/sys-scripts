#!/usr/bin/env bash
# Quick disk status report for macOS APFS system.
# Shows: free space, local TM snapshots, key cache sizes, simulator runtime images.

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

# du exits nonzero for missing paths; `|| true` keeps set -e/pipefail from ending the report early.
# Podman's VM disk is a sparse file: du reports allocated bytes (fstrim inside the VM shrinks it).
echo "--- Key cache sizes ---"
du -sh \
  "${HOME}/.cache/uv" \
  "${HOME}/.cache/huggingface" \
  "${HOME}/.cache/pre-commit" \
  "${HOME}/.cache/chrome-devtools-mcp" \
  "${HOME}/.npm" \
  "${HOME}/.claude/projects" \
  "${HOME}/.local/share/containers/podman/machine/"*/*.raw \
  "${HOME}/Library/Developer/CoreSimulator" \
  "${HOME}/Library/Developer/Xcode/DerivedData" \
  "${HOME}/Library/Developer/Xcode/iOS DeviceSupport" \
  "${HOME}/Library/Developer/Xcode/watchOS DeviceSupport" \
  "${HOME}/Library/Application Support/Google/Chrome" \
  "${HOME}/Library/Application Support/Google/DriveFS" \
  "${HOME}/Documents/GitHub" \
  2>/dev/null | sort -rh || true
echo ""

# Runtime images live under /Library, outside ~/Library/Developer/CoreSimulator above.
echo "--- Simulator runtime images ---"
xcrun simctl runtime list 2>/dev/null | grep "Total Disk Images" || echo "  none (or Xcode not installed)"
