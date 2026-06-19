#!/usr/bin/env bash
# Force-detach attached macOS disk images, skipping SIP-protected system cryptexes.
#
# Stale .dmg mounts (downloaded installers, leftover iOS Simulator runtime/volume
# images, etc.) accumulate and stay attached. This detaches them with `hdiutil
# detach -force`. Images mounted under the security cryptex tree (Metal toolchain,
# /System/Cryptexes) are held by cryptexd and will return "Resource busy" -- those
# are detected and skipped rather than fought.
#
# Dry-run by default; pass --execute to actually detach.

set -euo pipefail

EXECUTE=0
[[ "${1:-}" == "--execute" ]] && EXECUTE=1

echo "=== Attached disk images $(date '+%Y-%m-%d %H:%M') ==="
[[ $EXECUTE -eq 0 ]] && echo "(dry-run -- pass --execute to detach)"
echo ""

# Parse `hdiutil info` into one record per image:  whole-disk-dev <TAB> skip <TAB> image-path
# skip=yes when any of the image's partitions is mounted under a system cryptex tree.
records=$(hdiutil info | awk -F'\t' '
  function flush() {
    if (dev != "") printf "%s\t%s\t%s\n", dev, skip, img
    dev=""; img=""; skip="no"
  }
  BEGIN { skip="no" }
  /^====/ { flush(); next }
  /^image-path/ {
    line=$0; sub(/^image-path[ :]*/, "", line); img=line
    # Protected cryptexes: matched by asset path even when their fs is unmounted
    # but the image is still attached. NOTE: CoreSimulator/Cryptex/ bundle images
    # are user-detachable and deliberately NOT matched here.
    if (img ~ /MetalToolchain|com\.apple\.security\.cryptexd|\/System\/Cryptexes/) skip="yes"
    next
  }
  $1 ~ /^\/dev\/disk[0-9]+$/ && dev=="" { dev=$1 }
  # Also skip when a partition is actively mounted under a system cryptex tree.
  { if (NF>=3 && $3 ~ /com\.apple\.security\.cryptexd|^\/System\/Cryptexes/) skip="yes" }
  END { flush() }
')

if [[ -z "$records" ]]; then
  echo "No disk images attached."
  exit 0
fi

detached=0
skipped=0
while IFS=$'\t' read -r dev skip img; do
  [[ -z "$dev" ]] && continue
  name=$(basename "$img")
  if [[ "$skip" == "yes" ]]; then
    echo "SKIP  $dev  (system cryptex)  $name"
    skipped=$((skipped + 1))
    continue
  fi
  if [[ $EXECUTE -eq 0 ]]; then
    echo "WOULD detach  $dev  $name"
    continue
  fi
  echo "Detaching $dev  ($name) ..."
  if hdiutil detach -force "$dev" 2>&1; then
    detached=$((detached + 1))
  else
    echo "  (failed -- still busy; may be in active use)"
  fi
done <<< "$records"

echo ""
if [[ $EXECUTE -eq 0 ]]; then
  echo "Dry-run complete. $skipped system cryptex(es) would be skipped."
else
  echo "Detached $detached image(s); skipped $skipped system cryptex(es)."
fi
