---
title: Use your scans in Claude on your Mac
nav: 4
---

# Use your scans in Claude on your Mac

lidarscan-mcp is a small, free helper for your Mac. It lets Claude Desktop and Claude Code list
your scans, read their room data and show their plans, straight from iCloud Drive. It only reads;
it never changes your files.

## Install

You need a Mac signed in to the same iCloud account as your iPhone or iPad, with iCloud Drive on.

1. Download [lidarscan-mcp 0.1.0](https://github.com/DavidHoppestad/plan-and-model/releases/download/mcp-v0.1.0/lidarscan-mcp-0.1.0.zip).
   SHA-256: `658c2a1bc00229cb28b0cc710d9b45d0f1a3a157d2bc39aab62e3205e34acfdd`
2. Open Terminal in the download folder and run:

   ```bash
   ditto -x -k lidarscan-mcp-0.1.0.zip . && ./lidarscan-mcp-0.1.0/install.sh
   ```

3. Restart Claude Desktop, then ask: "list my scans".

If macOS offers to install the Command Line Tools, accept and run the command again; the helper
uses the Python that comes with them.

## Remove

```bash
"$HOME/Library/Application Support/lidarscan-mcp/uninstall.sh"
```

## What Claude can ask for

Your scan list, a scan's summary (rooms, areas, walls, doors, windows, furniture), its room data
as JSON, the floor plan and drawings as images, a search for rooms or furniture across scans, and
the paths of exported files.
