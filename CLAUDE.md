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
- After `uv cache prune`, run `cleanup_snapshots.sh` twice: once to clear prior snapshots, then once more to clear the snapshot that captured the prune itself
- `eject_disk_images.sh` skips system cryptexes by image-path (`MetalToolchain`, `/System/Cryptexes`,
  `com.apple.security.cryptexd`) because `hdiutil info` stops reporting their mount point once `cryptexd`
  unmounts the fs while the image stays attached — a mount-point-only check misses them. CoreSimulator's
  own `Cryptex/Images/bundle/` images are NOT skipped (user-detachable). Truly-busy images still fail the
  `hdiutil detach -force` gracefully and are reported, not fatal.
- CoreSimulator cleanup: `xcrun simctl runtime list` to see installed runtimes (can be 8 GB each);
  `xcrun simctl runtime delete <UUID>` to remove the runtime, then `xcrun simctl delete unavailable`
  to also free device data (~7 GB). Running `xcrun simctl delete unavailable` alone (without deleting
  the runtime first) only removes device instances, NOT runtime disk images — silently succeeds without freeing space.
  Sometimes the first `delete unavailable` pass doesn't clear all now-orphaned devices immediately after a runtime
  delete (`CoreSimulator/Devices/` stays large even though `simctl list devices` shows them "unavailable") —
  run `delete unavailable` a second time and verify with `du -sh ~/Library/Developer/CoreSimulator/*/`.
  `delete unavailable` is a no-op if every device shows "Shutdown" rather than "unavailable" in `simctl list devices` —
  that's live device data, not orphaned. Reclaiming an old runtime's space (~7-20 GB) requires `simctl runtime delete <UUID>`
  first, which destroys any device data tied to that runtime — confirm the runtime is actually unused (check target OS in
  project build configs) before running it, since it's more destructive than the routine cleanup pass.
- `~/Documents/GitHub/` investigation: `du -sh ~/Documents/GitHub/*/` when total is large; `portfolio/data/snapshots/` accumulates ~960 MB weekly snapshots and is safe to prune. For any repo that's disproportionately large, check `du -sh <repo>/.git` to separate history bloat from working-tree data, and `git worktree list` for stale worktrees on suspiciously-named sibling dirs (e.g. `*_feature_TIMESTAMP_*`) — a worktree's own `.git` is a tiny ~4KB pointer file, so its real size lives outside `.git` and won't show up in a `.git`-size check.
- Git-LFS repos can have `.git` dominated by `lfs/objects/` (old blob versions retained locally). `git lfs prune --dry-run` reports reclaimable size safely — it only removes objects that are re-fetchable from `origin` and never touches unpushed/uncommitted objects. `git lfs prune` to actually reclaim.
- Transcript compaction has diminishing returns after the first run (~628 MB vs ~9 GB); skip if run recently
- `compact_transcripts.py --execute` moves compacted files to `~/Library/CloudStorage/GoogleDrive-.../My Drive/My_Drive/Data/Claude`; Drive must be mounted or use `--no-archive`
- uv cache can grow 50+ GB in days of heavy dev work; prune weekly with `uv cache prune`
- `~/Downloads/<month>/.tmp.driveupload/` holds Google Drive upload temp files locked by the Drive process; quit Drive from the menu bar before deleting, or delete from Finder after quitting. Drive refuses a scripted `osascript -e 'quit app "Google Drive"'` (error -128) — ask the user to quit it from the menu bar; never force-kill it.
- Xcode auto-downloads simulator runtimes silently; disable with `defaults write com.apple.dt.Xcode DVTDownloadableAutomaticUpdate -bool NO` (Xcode 26 has no UI toggle — Components → Platform Support shows runtimes but no auto-download option). This only blocks background/idle auto-downloads — it does NOT stop `xcodebuild -destination 'platform=iOS Simulator,...'` from installing a runtime on demand when the targeted simulator isn't present. Runtimes will keep reappearing with any simulator-targeted build regardless of this setting; the CoreSimulator cleanup above is the durable fix, not prevention.
- Deleting `/Applications` items requires sudo; use Finder (right-click → Move to Trash) or run `! sudo rm -rf /Applications/<App>` in an interactive terminal — `rm -rf` without sudo returns Permission denied
- Chrome cache investigation: `du -sh ~/Library/Application\ Support/Google/Chrome/*/`, then per-origin `Default/Service Worker/CacheStorage/<hash>/` (`strings <hash>/index.txt | grep -Eo 'https?://[a-zA-Z0-9._-]+'` names the origin). To see *what* is cached, run in that origin's page: `caches.keys()` → per-cache `(await caches.open(k)).keys()` URLs. Without a browser, count cached synavistra bundle versions by reading only entry headers: `head -c 2048` each `*_0` file in the origin dir `| grep -aoE 'bundles/v[0-9.]+-[0-9TZ]+' | sort | uniq -c` (full-file `strings` on multi-GB entries is too slow). `transformers-cache` = transformers.js model weights keyed by URL; synavistra's stale-bundle pile-up was fixed by synavistra PR #1620 (2026-09-26) — the real profile now holds one current bundle (~7.4G per origin, prod and staging each). Leave that alone: clearing it only forces a 7.4G re-download on the next visit.
- `chrome-devtools` MCP tools (`mcp__chrome-devtools__*`) launch an isolated Chrome profile at `~/.cache/chrome-devtools-mcp/chrome-profile`, NOT the user's real browser — verify with `pgrep -fl user-data-dir` (it can't open `chrome://` URLs) before relying on it to inspect or modify real browser state. That profile accumulates its own site caches (16G of stale synavistra bundles found 2026-10-02) and isn't covered by fixes that only run when the real user visits. Use `claude-in-chrome` (extension installed + user logged into claude.ai in their real browser) to act on the real profile.
- Clear one origin's cache safely via `claude-in-chrome`: navigate to the origin, then `javascript_tool` → `for (const k of await caches.keys()) await caches.delete(k)` (Chrome frees the disk within ~1 min; never `rm` the CacheStorage dirs while Chrome runs — its index goes inconsistent). If `tabs_context_mcp` reports "Browser extension is not connected" after one retry, stop — it's an extension setup issue (install/enable/login/restart Chrome) outside Claude Code's control. Fall back to manual: DevTools (Cmd+Option+I) → Application → Storage → "Clear site data" (wipes cookies too), or right-click entries under Cache storage to clear just the cache without logging the user out. Origins behind Cloudflare Access (e.g. `staging.synavistra.ai`) redirect to a login page on another origin, so in-page `caches.delete()` can't reach them; if that browser is not running (`pgrep -f <user-data-dir>` empty — stop the DevTools MCP browser with `pkill -f <user-data-dir>`), `rm -rf` the origin's CacheStorage dir instead (verified safe: the profile restarts with an empty, working Cache API).
- Simulator "Shutdown" devices can still hold junk: `du -sh <device>/data/Library/Caches/*/` — `com.apple.nsurlsessiond/Downloads/` accumulates retried MobileAsset downloads (14G of duplicate Siri ASR `.dmg`s seen in the Watch sim); safe to `rm -rf` its contents while the device is Shutdown. `xcrun simctl erase <UDID>` is the full reset.
- Runtime disk images live under `/Library/Developer/CoreSimulator/`, NOT `~/Library/Developer/CoreSimulator` (so `disk_report.sh` doesn't count them), and a deleted runtime can reappear — check `xcrun simctl runtime list` every run. `xcrun simctl list devices -j` maps each device to its runtime, proving a runtime has zero devices before `runtime delete`.
- APFS frees space asynchronously after big deletes and `simctl runtime delete` — the reading right after `cleanup_snapshots.sh` can undercount by ~20 GB; re-run `disk_report.sh` a minute or two later before reporting. A `(dataless)` TM snapshot survives `cleanup_snapshots.sh` and pins nothing.
- Before pruning: a stale worktree is zero-risk to `git worktree remove` if `git -C <main-repo> branch -a --contains <worktree HEAD>` lists a branch and `git -C <worktree> status --short` is empty. Portfolio snapshot hashes can be referenced in `portfolio/CLAUDE.md`/docs — `grep -r <hash>` and keep referenced ones.
- `disk_report.sh` now also reports podman VM `.raw` (allocated size), `~/.npm`, `~/.cache/chrome-devtools-mcp`, `~/.cache/pre-commit`, Xcode iOS/watchOS DeviceSupport, Chrome, and simulator runtime images under `/Library` — these held ~60G unnoticed before 2026-10-02. Still not covered: `~/Library/Caches/*`, `~/Downloads`; `du -sh` them when the total doesn't add up.
- Podman VM disk (`~/.local/share/containers/podman/machine/applehv/*.raw`) is sparse: deletes inside the VM don't return to macOS until `podman machine ssh -- sudo fstrim -av` (freed 25G alone). Prune with `podman image prune -a -f --filter until=720h` (keeps recent images; list `localhost/` project images for the user first), then fstrim again. Never `rm` the `.raw`.
- npm: `npm cache clean --force` empties `~/.npm/_cacache`. In `~/.npm/_npx`, delete only hash dirs no running process uses (`ps -axo command` / `lsof +D` for `/.npm/_npx/<hash>`) — live MCP servers (chrome-devtools-mcp, etc.) execute from there.
- Xcode `iOS DeviceSupport/<model> <os>`: delete folders for OS versions the connected device no longer runs (5.5G each); Xcode re-copies on connect. `pre-commit gc` frees little (0.3G of 4.6G); `pre-commit clean` wipes all. `uv cache clean` frees less than it reports (18.5GiB removed → ~8G real) because of hardlinks into venvs.
- portfolio `data/tmp/ingest_*_<run_id>.jsonl` crash-recovery buffers can outlive a finished run (3.5G seen). Safe to delete if a read-only DuckDB query shows rows for that `run_id` (e.g. `decision_log`) and no pipeline process has the file open.
