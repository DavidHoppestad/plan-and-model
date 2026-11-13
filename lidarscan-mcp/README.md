<!-- AGENT NOTE: lidarscan-mcp setup and behaviour (issue M4-05). Keep the tool list in sync with
TOOLS in lidarscan_mcp.py. Packaging for App Store users is M8-10 (install.sh, uninstall.sh, release.sh, RELEASING.md). -->

# lidarscan-mcp

A read-only MCP server that lets Claude Desktop and Claude Code read your Plan & Model scans from
iCloud Drive on your Mac. It uses only the Python that ships with macOS (`/usr/bin/python3`, 3.9+);
there is nothing to install.

## Tools

| Tool | What Claude gets |
|---|---|
| `list_scans` | Every scan: name, floor area, room count, date |
| `get_summary(scan)` | `claude/summary.md`: rooms and areas, walls, doors, windows, objects, caveats |
| `get_room_json(scan)` | `claude/room.json`  |
| `get_plan_image(scan)` | The dimensioned floor plan as an image |
| `get_render(scan, view)` | `plan`, `elevations` or `furniture` drawing as an image |
| `find(query)` | Rooms (by name or type) and objects (by category) across all scans |
| `export_paths(scan)` | Absolute paths of the exported files (DXF, OBJ, STL, USDZ, GLB, PDF, ...) |

`scan` is a name from `list_scans`; matching ignores case and accepts a unique prefix.

## Install (one command)

From an unpacked release (or this folder):

```bash
./install.sh
```

It copies the server to `~/Library/Application Support/lidarscan-mcp/<version>/`, checks that it
answers, and registers it with Claude Desktop (your config is backed up and other servers are
kept) and with Claude Code if the `claude` command is installed. `--no-register` copies only and
prints the config lines. `~/Library/Application Support/lidarscan-mcp/uninstall.sh` removes it.
Releases: see `RELEASING.md`.

## Set up by hand

Replace `<repo>` with the path of this repository (or copy `lidarscan_mcp.py` anywhere).

Claude Code:

```bash
claude mcp add lidarscan -- /usr/bin/python3 "<repo>/lidarscan-mcp/lidarscan_mcp.py"
```

Claude Desktop: Settings › Developer › Edit Config, then add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lidarscan": {
      "command": "/usr/bin/python3",
      "args": ["<repo>/lidarscan-mcp/lidarscan_mcp.py"]
    }
  }
}
```

Restart Claude Desktop, then ask: "list my scans", "what is the area of the kitchen?",
"show me the plan of the kitchen scan".

Environment variables: `LIDARSCAN_ROOT` (default
`~/Library/Mobile Documents/iCloud~com~hoppestad~planandmodel/Documents`),
`LIDARSCAN_DOWNLOAD_TIMEOUT` (seconds to wait for an iCloud download, default 30).

## Behaviour

- Read-only: it never writes, renames or deletes anything in the folder. Paths that resolve outside
  the folder (including through symlinks) are refused.
- Files that iCloud has not downloaded to this Mac yet are fetched with `brctl download` and read
  when they arrive; after the timeout the tool says the file is still downloading.

## Zero-code alternative

The reference filesystem MCP server, pointed at the same folder, also works; Claude then reads
`Exports/<scan>/claude/summary.md`, `room.json` and `plan.png` itself:

```bash
claude mcp add files -- npx -y @modelcontextprotocol/server-filesystem "$HOME/Library/Mobile Documents/iCloud~com~hoppestad~planandmodel/Documents"
```

That server can also write files; lidarscan-mcp cannot.

## Tests

```bash
/usr/bin/python3 -m unittest discover -s Tools/lidarscan-mcp/tests
```
