#!/bin/bash
# AGENT NOTE: Removes lidarscan-mcp (issue M8-10): the install folder, the Claude Desktop config
# entry (other servers kept, config backed up) and the Claude Code registration. Never touches
# scans or the iCloud container.
set -euo pipefail
BASE="$HOME/Library/Application Support/lidarscan-mcp"
CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ -f "$CFG" ]; then
  cp "$CFG" "$CFG.lidarscan-backup"
  /usr/bin/python3 - "$CFG" <<'PYEOF'
import json, os, sys
cfg = sys.argv[1]
with open(cfg) as f:
    data = json.load(f)
if data.get("mcpServers", {}).pop("lidarscan", None) is not None:
    with open(cfg + ".tmp", "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(cfg + ".tmp", cfg)
    print("Removed lidarscan from Claude Desktop.")
PYEOF
fi
command -v claude >/dev/null 2>&1 && claude mcp remove --scope user lidarscan >/dev/null 2>&1 && echo "Removed lidarscan from Claude Code." || true
rm -rf "$BASE"
echo "Removed $BASE"
