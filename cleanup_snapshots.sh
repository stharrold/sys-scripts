#!/usr/bin/env bash
# Delete all local Time Machine snapshots that are safe to remove.
# Skips com.apple.os.update-* snapshots (system-owned, required for SoftwareUpdate).
# After deletion, reports Container Free Space to show realized reclaim.

set -euo pipefail

echo "=== Local TM snapshots before ==="
tmutil listlocalsnapshots / 2>/dev/null | grep -v "os.update" || echo "  none"
echo ""

deleted=0
while IFS= read -r line; do
  # Extract date portion: com.apple.TimeMachine.YYYY-MM-DD-HHMMSS.local -> YYYY-MM-DD-HHMMSS
  snap=$(echo "$line" | sed 's/com\.apple\.TimeMachine\.\(.*\)\.local/\1/')
  if [[ -n "$snap" ]]; then
    echo "Deleting $snap ..."
    tmutil deletelocalsnapshots "$snap" 2>&1 || echo "  (warning: delete returned non-zero, may already be gone)"
    deleted=$((deleted + 1))
  fi
done < <(tmutil listlocalsnapshots / 2>/dev/null | grep "com.apple.TimeMachine")

echo ""
echo "Deleted $deleted snapshot(s)."
echo ""
echo "=== Container Free Space after ==="
diskutil info /System/Volumes/Data | grep "Container Free Space"
