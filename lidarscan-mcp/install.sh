#!/bin/bash
# AGENT NOTE: One-command installer for lidarscan-mcp (issue M8-10, 10-app-store.md §8).
# Installs into ~/Library/Application Support/lidarscan-mcp/<version>/ (a "current" symlink points
# at the active version) and registers the server with Claude Desktop (config JSON, backed up
# first, other servers kept) and with Claude Code when the `claude` CLI is on PATH.
# It never touches the iCloud container: the server itself is read-only (README.md).
# Usage:
#   ./install.sh                  install from this folder (an unpacked release zip or the repo)
#   ./install.sh --no-register    copy files only; print the config snippets
#   LIDARSCAN_MCP_URL=<zip url> ./install.sh   download a release zip first (SHA256 checked when
#                                 LIDARSCAN_MCP_SHA256 is set)
# Requires /usr/bin/python3 (3.9+). On a Mac without the Command Line Tools, macOS offers to
# install them the first time python3 runs; the installer stops and says so.
set -euo pipefail

REGISTER=1
for a in "$@"; do
  case "$a" in
    --no-register) REGISTER=0 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done

PY=/usr/bin/python3
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  echo "lidarscan-mcp needs Python 3.9 or later at /usr/bin/python3." >&2
  echo "If macOS offered to install the Command Line Tools, finish that and run this again." >&2
  exit 1
fi

SRC="$(cd "$(dirname "$0")" && pwd)"
TMP=""
# Must return 0: under set -e a false test here becomes the script's exit status.
cleanup() { if [ -n "$TMP" ]; then rm -rf "$TMP"; fi; }
trap cleanup EXIT
if [ -n "${LIDARSCAN_MCP_URL:-}" ]; then
  TMP="$(mktemp -d)"
  curl -fsSL "$LIDARSCAN_MCP_URL" -o "$TMP/release.zip"
  if [ -n "${LIDARSCAN_MCP_SHA256:-}" ]; then
    echo "${LIDARSCAN_MCP_SHA256}  $TMP/release.zip" | shasum -a 256 -c - >/dev/null 2>&1 || { echo "Checksum mismatch; not installing." >&2; exit 1; }
  fi
  /usr/bin/ditto -x -k "$TMP/release.zip" "$TMP/x"
  SRC="$(dirname "$(find "$TMP/x" -name lidarscan_mcp.py | head -1)")"
fi
[ -f "$SRC/lidarscan_mcp.py" ] || { echo "lidarscan_mcp.py not found next to install.sh" >&2; exit 1; }

VERSION="$("$PY" -c 'import re,sys; print(re.search(r"SERVER_VERSION = \"([^\"]+)\"", open(sys.argv[1]).read()).group(1))' "$SRC/lidarscan_mcp.py")"
BASE="$HOME/Library/Application Support/lidarscan-mcp"
DEST="$BASE/$VERSION"
mkdir -p "$DEST"
cp "$SRC/lidarscan_mcp.py" "$DEST/"
[ -f "$SRC/README.md" ] && cp "$SRC/README.md" "$DEST/"
cp "$SRC/uninstall.sh" "$BASE/uninstall.sh" 2>/dev/null || true
ln -sfn "$DEST" "$BASE/current"
SERVER="$BASE/current/lidarscan_mcp.py"

# Self-check: the server answers initialize and lists its tools.
CHECK="$(printf '%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"install","version":"1"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | "$PY" "$SERVER" 2>/dev/null || true)"
echo "$CHECK" | grep -q '"list_scans"' || { echo "Installed server did not answer tools/list; see $DEST" >&2; exit 1; }
echo "Installed lidarscan-mcp $VERSION to $DEST"

if [ "$REGISTER" = 1 ]; then
  CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
  if [ -d "$(dirname "$CFG")" ]; then
    [ -f "$CFG" ] && cp "$CFG" "$CFG.lidarscan-backup"
    "$PY" - "$CFG" "$PY" "$SERVER" <<'PYEOF'
import json, os, sys
cfg, py, server = sys.argv[1:4]
data = {}
if os.path.exists(cfg):
    with open(cfg) as f:
        text = f.read().strip()
        data = json.loads(text) if text else {}
data.setdefault("mcpServers", {})["lidarscan"] = {"command": py, "args": [server]}
tmp = cfg + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
os.replace(tmp, cfg)
PYEOF
    echo "Registered with Claude Desktop (restart Claude Desktop to load it)."
  else
    echo "Claude Desktop not found; skipped its config."
  fi
  if command -v claude >/dev/null 2>&1; then
    claude mcp remove lidarscan >/dev/null 2>&1 || true
    claude mcp add --scope user lidarscan -- "$PY" "$SERVER" >/dev/null && echo "Registered with Claude Code (user scope)."
  fi
else
  echo "Claude Desktop config entry:"
  echo "  \"lidarscan\": {\"command\": \"$PY\", \"args\": [\"$SERVER\"]}"
  echo "Claude Code: claude mcp add --scope user lidarscan -- $PY \"$SERVER\""
fi
echo 'Try in Claude: "list my scans".'
