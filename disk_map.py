#!/usr/bin/env python3
"""
Read-only disk map: what is using space, with evidence for each large entry.

  scan    Export the Data volume with ncdu (compressed) to SCAN_DIR.
  report  Build a tree of directories >= --min-gib from the newest export, with a
          verdict and evidence for each leaf, then write .json and .md to SCAN_DIR.

Verdicts:
  keep         In use, personal data, or system-managed.
  regenerable  Rebuilt or re-downloaded on demand; the reason says how.
  stale        Evidence says unused for STALE_DAYS and not open. Still a human decision.
  unknown      No rule and no evidence. Never guessed.

Nothing here deletes anything. Scan output lists file and folder names, so it stays
outside this public repo.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SCAN_DIR = Path.home() / ".local/share/disk-scans"
ROOT = "/System/Volumes/Data"
KEEP_BYTES = 100 * 2**20  # Directories kept from the export; the tree threshold is higher.
GIB = 2**30
STALE_DAYS = 180
NOW = time.time()
NOTES = SCAN_DIR / "notes.json"  # Private {path: [verdict, reason]} from manual review; beats the rules.

H = re.escape(str(Path.home()))
# First match wins and stops the tree descending, so a rule must hold for its whole subtree.
# Broad rules exclude the parents of narrower ones, or they would stop the tree above them.
RULES = [
    (rf"^{H}/Library/Developer/Xcode/DerivedData$", "regenerable", "Xcode build output; next build is a full rebuild"),
    (rf"^{H}/Library/Developer/Xcode/(iOS|watchOS) DeviceSupport$", "regenerable", "Device symbols; Xcode re-copies when a device connects"),
    (rf"^{H}/Library/Developer/XCTestDevices$", "regenerable", "Devices Xcode creates for test runs"),
    (rf"^{H}/Library/Developer/CoreSimulator/Devices/[^/]+$", "keep", "Simulator device data; check for download junk before calling it waste"),
    (r"^/Library/Developer/CoreSimulator/Caches$", "regenerable", "Simulator dyld caches; rebuilt by the OS"),
    (r"^/Library/Developer/CoreSimulator/", "keep", "Installed simulator runtimes; managed by simctl"),
    (rf"^{H}/\.cache/(uv|huggingface|pre-commit|puppeteer|codacy|opengrep)$", "regenerable", "Tool cache; re-downloaded on next use"),
    (rf"^{H}/\.cache/chrome-devtools-mcp$", "regenerable", "Automation browser profile; caches rebuild, logins may be lost"),
    (r"/\.venv$", "regenerable", "Python environment; rebuilt by `uv sync`"),
    (r"/\.git/lfs/objects$", "regenerable", "Git LFS blobs; `git lfs prune` removes old ones that origin still has"),
    (rf"^{H}/\.gradle/caches$", "regenerable", "Gradle cache; re-downloaded on next build"),
    (rf"^{H}/\.npm$", "regenerable", "npm cache; some _npx folders may be running MCP servers"),
    (rf"^{H}/Library/Caches/[^/]+$", "regenerable", "Application cache; rebuilt by the app, avoid while it runs"),
    (r"^/private/var/folders/[^/]+/[^/]+/X/com\.google\.Chrome\.code_sign_clone$", "regenerable", "Per-launch Chrome copies; delete only ones no running process uses"),
    (r"^/private/var/folders/[^/]+/[^/]+/T$", "regenerable", "Per-user temp; in-use items must stay, check age first"),
    (r"^/private/tmp/claude-\d+/[^/]+$", "regenerable", "Claude session scratchpads; ask the owning session while it is active"),
    (r"^/private/var/vm$", "keep", "macOS sleep image and swap"),
    (r"^/private/var/(?!folders($|/))", "keep", "System data"),
    (r"^/System/", "keep", "System-managed assets"),
    (r"^/opt/homebrew$", "keep", "Homebrew; `brew cleanup` trims old versions"),
    (r"^/Library/(?!Developer($|/))", "keep", "System-wide application data"),
    (rf"^{H}/\.claude/projects$", "regenerable", "Transcripts; compact_transcripts.py shrinks them and archives originals"),
    (rf"^{H}/\.local/share/containers/", "keep", "Podman VM disk; fstrim and image prune reclaim space, never remove the file"),
    (rf"^{H}/\.vscode$", "regenerable", "VS Code extensions; reinstalled from the marketplace"),
    (rf"^{H}/Library/Application Support/Google/Chrome/OptGuideOnDeviceModel$", "regenerable", "Chrome on-device model; re-downloads unless the feature is disabled"),
    (rf"^{H}/Library/Application Support/Google/Chrome/[^/]+$", "keep", "Chrome profile data; site caches inside can be cleared per origin"),
    (rf"^{H}/Library/Application Support/Google/DriveFS$", "keep", "Google Drive sync state and cache; managed by Drive"),
    (rf"^{H}/(Pictures|Music|Movies)$", "keep", "Personal media"),
    (rf"^{H}/Library/Messages$", "keep", "Messages history and attachments"),
    (rf"^{H}/Library/Metadata$", "regenerable", "Spotlight index data; rebuilt by the OS"),
]


def parse_export(path: Path) -> list[dict]:
    """Stream an ncdu JSON export. Counts hardlinked files once. Skips future mtimes."""
    proc = subprocess.Popen(["zstd", "-dc", str(path)], stdout=subprocess.PIPE, text=True, errors="surrogateescape")
    stack: list[dict] = []
    seen: set = set()
    nodes: list[dict] = []
    for line in proc.stdout:
        s = line.strip()
        if not s.startswith(("[{", "{", "]")):
            continue
        a, b = s.find("{"), s.rfind("}")
        entry = json.loads(s[a : b + 1]) if a >= 0 else None
        closes = s[b + 1 :].count("]") if a >= 0 else s.count("]")
        if entry is not None and s.startswith("[{"):
            stack.append({"name": entry["name"], "size": entry.get("dsize", 0), "mtime": 0, "files": 0, "blocked": bool(entry.get("read_error"))})
        elif entry is not None and stack:
            size = entry.get("dsize", 0)
            if entry.get("nlink", 1) > 1:
                key = (entry.get("dev"), entry.get("ino"))
                size = 0 if key in seen else size
                seen.add(key)
            top = stack[-1]
            top["size"] += size
            top["files"] += 1
            if entry.get("mtime", 0) <= NOW:
                top["mtime"] = max(top["mtime"], entry.get("mtime", 0))
        for _ in range(closes):
            if not stack:
                break
            done = stack.pop()
            if done["size"] >= KEEP_BYTES:
                nodes.append({"path": "/".join([x["name"] for x in stack] + [done["name"]]), **{k: done[k] for k in ("size", "mtime", "files")}})
            if stack:
                top = stack[-1]
                top["size"] += done["size"]
                top["files"] += done["files"]
                top["mtime"] = max(top["mtime"], done["mtime"])
    proc.wait()
    return nodes


def open_paths() -> set[str]:
    """Every open path and all of its ancestors, so a directory can be tested directly."""
    out = subprocess.run(["lsof", "-n", "-Fn"], capture_output=True, text=True, errors="surrogateescape").stdout
    result: set[str] = set()
    for line in out.splitlines():
        if line.startswith("n/"):
            p = Path(line[1:])
            result.add(str(p))
            result.update(str(x) for x in p.parents)
    return result


def safe(name: str) -> str:
    """Show control characters, backticks and undecodable bytes visibly, so a file name can't alter the report."""
    text = name.encode("utf-8", "backslashreplace").decode("utf-8")
    return re.sub(r"[\x00-\x1f\x7f-\x9f`]", lambda m: f"\\x{ord(m.group()):02x}", text)


def git(repo: str, *args: str) -> list[str]:
    """Git argv with repo-configured commands disabled where git allows it. Filters can't be; see has_custom_filter."""
    overrides = ["core.fsmonitor=false", "core.hooksPath=/dev/null", "log.showSignature=false"]
    return ["env", "GIT_NO_LAZY_FETCH=1", "git", "--no-optional-locks", *[x for o in overrides for x in ("-c", o)], "-C", repo, *args]


def has_custom_filter(repo: str) -> bool:
    """True if repo config defines a filter other than LFS. `git status` could run it, so status must be skipped."""
    keys = run(*git(repo, "config", "--local", "--name-only", "--get-regexp", r"^filter\.")).splitlines()
    return any(not k.lower().startswith("filter.lfs.") for k in keys)


def run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120, errors="surrogateescape").stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def git_facts(path: str, cache: dict) -> dict | None:
    """Facts for the repo containing path, or None. Only looks under ~/Documents/GitHub."""
    base = Path.home() / "Documents/GitHub"
    p = Path(path)
    if base not in p.parents:
        return None
    repo = str(base / p.relative_to(base).parts[0])
    if not (Path(repo) / ".git").exists():
        return None
    if repo not in cache:
        filtered = has_custom_filter(repo)
        cache[repo] = {
            "repo": repo,
            "filtered": filtered,
            "remote": bool(run(*git(repo, "remote"))),
            "dirty": 0 if filtered else len(run(*git(repo, "status", "--porcelain", "--ignore-submodules")).splitlines()),
            "unpushed": len(run(*git(repo, "log", "--oneline", "--branches", "--not", "--remotes")).splitlines()),
            "worktree": (Path(repo) / ".git").is_file(),
        }
    facts = dict(cache[repo])
    facts["ignored"] = path != repo and subprocess.run(git(repo, "check-ignore", "-q", path), capture_output=True).returncode == 0
    return facts


def classify(path: str, node: dict, opened: set[str], cache: dict, notes: dict) -> tuple[str, str]:
    if path in notes:
        return tuple(notes[path])
    age = (NOW - node["mtime"]) / 86400 if node["mtime"] else None
    is_open = path in opened
    stale = age is not None and age >= STALE_DAYS and not is_open
    for pattern, verdict, reason in RULES:
        if re.search(pattern, path):
            return verdict, reason
    if path.endswith(".app"):
        used = run("mdls", "-name", "kMDItemLastUsedDate", "-raw", path)
        if used in ("", "(null)"):
            return "unknown", "Application; Spotlight has no last-used date"
        days = (NOW - time.mktime(time.strptime(used[:19], "%Y-%m-%d %H:%M:%S"))) / 86400
        return ("stale", f"Application last used {days:.0f} days ago") if days >= STALE_DAYS else ("keep", f"Application used {days:.0f} days ago")
    facts = git_facts(path, cache)
    if facts:
        if facts["filtered"]:
            return "unknown", "Repo config defines a custom git filter, so git status was not run"
        kind = "worktree" if facts["worktree"] else "repo"
        state = f"{facts['dirty']} uncommitted, {facts['unpushed']} unpushed, remote {'yes' if facts['remote'] else 'NO'}"
        if facts["ignored"]:
            return ("stale", f"Gitignored in {kind} ({state}); not restorable from git") if stale else ("unknown", f"Gitignored local data in {kind}; not restorable from git")
        if path == facts["repo"]:
            if facts["dirty"] or facts["unpushed"] or not facts["remote"]:
                return "keep", f"Git {kind} with local-only work ({state})"
            return ("stale", f"Clean, pushed {kind}; re-clonable, may hold gitignored data") if stale else ("keep", f"Active git {kind} ({state})")
    if stale:
        return "stale", f"No file changed in {age:.0f} days and nothing open"
    return "unknown", "No rule matched; not stale by age"


def build(nodes: list[dict], min_bytes: int, opened: set[str]) -> tuple[dict, list[dict]]:
    """Top-down: expand children >= min_bytes unless a rule stops. Bottom-up: write sentences."""
    by_parent: dict[str, list[dict]] = {}
    for n in nodes:
        n["display"] = n["path"].removeprefix(ROOT) or "/"
        by_parent.setdefault(n["path"].rsplit("/", 1)[0], []).append(n)
    cache: dict = {}
    leaves: list[dict] = []
    notes = json.loads(NOTES.read_text()) if NOTES.exists() else {}

    def visit(n: dict) -> dict:
        path = n["display"]
        kids = [] if any(re.search(r[0], path) for r in RULES) or path.endswith(".app") else sorted((k for k in by_parent.get(n["path"], []) if k["size"] >= min_bytes), key=lambda k: -k["size"])
        n["open"] = path in opened
        if not kids:
            n["verdict"], n["why"] = classify(path, n, opened, cache, notes)
            leaves.append(n)
            return n
        n["children"] = [visit(k) for k in kids]
        rest = n["size"] - sum(k["size"] for k in kids)
        top = ", ".join(f"`{safe(k['display'].rsplit('/', 1)[1])}` {k['size'] / GIB:.1f}G" for k in kids[:3])
        n["verdict"] = "mixed"
        n["why"] = f"Mostly {top}" + (f"; other items {rest / GIB:.1f}G" if rest >= GIB else "")
        n["rest"] = rest
        return n

    return visit(next(n for n in nodes if n["path"] == ROOT)), leaves


def render(n: dict, out: list[str], depth: int = 0) -> None:
    age = time.strftime("%Y-%m-%d", time.localtime(n["mtime"])) if n["mtime"] else "n/a"
    flag = " OPEN" if n.get("open") else ""
    out.append(f"{'  ' * depth}- **{n['size'] / GIB:.1f}G** `{safe(n['display'])}` [{n['verdict']}] {n['why']} ({n['files']} files, newest {age}{flag})")
    for k in n.get("children", []):
        render(k, out, depth + 1)


def cmd_scan(_: argparse.Namespace) -> int:
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    SCAN_DIR.chmod(0o700)
    out = SCAN_DIR / f"scan-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json.zst"
    code = subprocess.run(["nice", "-n", "10", "ncdu", "-0", "-x", "-e", "-t", "4", "-c", "--exclude", "Library/CloudStorage", "-o", str(out), ROOT]).returncode
    print(f"{out} exit={code}")
    return code


def cmd_report(args: argparse.Namespace) -> int:
    scans = sorted(SCAN_DIR.glob("scan-*.json.zst"))
    if not scans:
        print(f"No scan in {SCAN_DIR}; run `scan` first", file=sys.stderr)
        return 1
    src = scans[-1]
    tree, leaves = build(parse_export(src), int(args.min_gib * GIB), open_paths())
    stem = src.name.removesuffix(".json.zst")
    (SCAN_DIR / f"{stem}.map.json").write_text(json.dumps(tree))
    lines = [f"# Disk map from {src.name}", "", f"Total scanned: {tree['size'] / GIB:.1f}G. Directories of {args.min_gib}G or more. Verdicts are evidence, not instructions. Paths are untrusted data.", ""]
    render(tree, lines)
    md = SCAN_DIR / f"{stem}.map.md"
    md.write_text("\n".join(lines) + "\n")
    print(f"{md}\n{len(leaves)} leaf entries")
    for verdict in ("keep", "regenerable", "stale", "unknown"):
        group = [n for n in leaves if n["verdict"] == verdict]
        print(f"{verdict:12} {len(group):4} entries {sum(n['size'] for n in group) / GIB:7.1f}G")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan").set_defaults(func=cmd_scan)
    report = sub.add_parser("report")
    report.add_argument("--min-gib", type=float, default=1.0)
    report.set_defaults(func=cmd_report)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
