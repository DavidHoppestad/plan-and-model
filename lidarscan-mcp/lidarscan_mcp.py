#!/usr/bin/env python3
# AGENT NOTE: lidarscan-mcp, a read-only MCP server over stdio for Claude Desktop and Claude Code
# (issue M4-05, docs/design/04-export-interop.md §9, decision D46: Python 3.9 standard library
# only, so it runs on the system /usr/bin/python3 with nothing to install).
# Rules:
# - Read-only. Files are opened with "rb" only; nothing is created, renamed or deleted under the
#   root. Test: tests/test_server.py runs every tool against a read-only copy.
# - Every path is resolved (realpath) and must stay inside the root; anything else is rejected.
# - iCloud files on the Mac can be "dataless" (st_flags SF_DATALESS). They are downloaded with
#   `brctl download <file>` and polled until present (VERIFIED in M0-08: brctl on a file works,
#   on a directory it does not recurse).
# - Scan names may contain U+202F (narrow no-break space, builds <= 2); matching normalises it.
# - Protocol: JSON-RPC 2.0, one message per line; methods initialize, tools/list, tools/call,
#   ping; the server answers with the protocol version the client asked for.

import base64
import json
import os
import subprocess
import sys
import time

SERVER_NAME = "lidarscan-mcp"
SERVER_VERSION = "0.1.0"
DEFAULT_ROOT = os.path.expanduser("~/Library/Mobile Documents/iCloud~com~hoppestad~planandmodel/Documents")
SF_DATALESS = 0x40000000
DOWNLOAD_TIMEOUT_S = float(os.environ.get("LIDARSCAN_DOWNLOAD_TIMEOUT", "30"))


class ToolError(Exception):
    pass


def norm(s):
    return s.replace(" ", " ").replace(" ", " ").strip().lower()


class Library:
    def __init__(self, root, is_dataless=None, download=None, sleep=time.sleep):
        self.root = os.path.realpath(root)
        self.is_dataless = is_dataless or self._is_dataless
        self.download = download or self._download
        self.sleep = sleep

    # --- path safety -------------------------------------------------------------------------

    def safe(self, *parts):
        """Absolute path for parts under the root; raises ToolError when it escapes the root."""
        path = os.path.realpath(os.path.join(self.root, *parts))
        if path != self.root and not path.startswith(self.root + os.sep):
            raise ToolError("Path is outside the Plan & Model folder.")
        return path

    # --- iCloud dataless files ------------------------------------------------------------------

    @staticmethod
    def _is_dataless(path):
        try:
            return bool(os.stat(path).st_flags & SF_DATALESS)
        except (AttributeError, OSError):
            return False

    @staticmethod
    def _download(path):
        subprocess.run(["brctl", "download", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)

    def read(self, path):
        """Bytes of a file under the root, downloading it from iCloud first when needed."""
        path = self.safe(os.path.relpath(path, self.root)) if os.path.isabs(path) else self.safe(path)
        if not os.path.isfile(path):
            raise ToolError("File not found: " + os.path.relpath(path, self.root))
        if self.is_dataless(path):
            self.download(path)
            waited = 0.0
            while self.is_dataless(path):
                if waited >= DOWNLOAD_TIMEOUT_S:
                    raise ToolError("Still downloading from iCloud: " + os.path.relpath(path, self.root)
                                    + ". Open the Plan & Model folder in Finder or try again shortly.")
                self.sleep(0.5)
                waited += 0.5
        with open(path, "rb") as f:
            return f.read()

    # --- scans ----------------------------------------------------------------------------------

    def scans(self):
        scans_dir = self.safe("Scans")
        out = []
        if not os.path.isdir(scans_dir):
            return out
        for entry in sorted(os.listdir(scans_dir)):
            if not entry.endswith(".lidarscan"):
                continue
            folder = entry[: -len(".lidarscan")]
            info = {"name": folder, "folder": folder}
            try:
                manifest = json.loads(self.read(os.path.join("Scans", entry, "manifest.json")))
                info.update({k: manifest.get(k) for k in ("name", "createdAt", "areaM2", "roomCount", "state")})
            except (ToolError, ValueError):
                info["state"] = "manifest unavailable"
            info["exports"] = os.path.isdir(self.safe("Exports", folder))
            out.append(info)
        return out

    def resolve(self, name):
        """Scan folder name for a user-given name: exact, then case/space-insensitive, then prefix."""
        if not name or "/" in name or name.startswith("."):
            raise ToolError("Give a scan name from list_scans.")
        scans = self.scans()
        for key in (lambda s: s["folder"] == name, lambda s: norm(s["folder"]) == norm(name) or norm(s["name"] or "") == norm(name),
                    lambda s: norm(s["folder"]).startswith(norm(name)) or norm(s["name"] or "").startswith(norm(name))):
            hits = [s for s in scans if key(s)]
            if len(hits) == 1:
                return hits[0]["folder"]
            if len(hits) > 1:
                raise ToolError("Several scans match '%s': %s" % (name, ", ".join(s["folder"] for s in hits)))
        if len(scans) == 1 and norm(name) in ("", "latest", "my scan", "the scan"):
            return scans[0]["folder"]
        raise ToolError("No scan named '%s'. Available: %s" % (name, ", ".join(s["folder"] for s in scans) or "none"))

    def export_file(self, scan, relative):
        return self.read(os.path.join("Exports", self.resolve(scan), relative))


# --- tools ------------------------------------------------------------------------------------

def text(s):
    return {"content": [{"type": "text", "text": s}]}


def tool_list_scans(lib, args):
    scans = lib.scans()
    if not scans:
        return text("No scans found in " + lib.root)
    lines = []
    for s in scans:
        area = "%.1f m²" % s["areaM2"] if isinstance(s.get("areaM2"), (int, float)) else "area unknown"
        lines.append("- %s (%s, %s room(s), scanned %s)" % (s["folder"], area, s.get("roomCount") or "?", s.get("createdAt") or "?"))
    return text("Scans:\n" + "\n".join(lines) + "\n\nPass a scan name to the other tools.")


def tool_get_summary(lib, args):
    return text(lib.export_file(args.get("scan", ""), "claude/summary.md").decode("utf-8"))


def tool_get_room_json(lib, args):
    return text(lib.export_file(args.get("scan", ""), "claude/room.json").decode("utf-8"))


def image(data):
    return {"content": [{"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": "image/png"}]}


def tool_get_plan_image(lib, args):
    return image(lib.export_file(args.get("scan", ""), "claude/plan.png"))


RENDERS = {"plan": "claude/plan.png", "elevations": "claude/elevations.png", "furniture": "furniture.png"}


def tool_get_render(lib, args):
    view = (args.get("view") or "plan").lower()
    if view not in RENDERS:
        raise ToolError("Unknown view '%s'. Available: %s" % (view, ", ".join(sorted(RENDERS))))
    return image(lib.export_file(args.get("scan", ""), RENDERS[view]))


def tool_find(lib, args):
    query = norm(args.get("query", ""))
    if not query:
        raise ToolError("Give something to search for, e.g. 'sofa' or 'kitchen'.")
    hits = []
    for s in lib.scans():
        try:
            room = json.loads(lib.export_file(s["folder"], "claude/room.json"))
        except (ToolError, ValueError):
            continue
        for r in room.get("rooms", []):
            if query in norm(r.get("name", "")) or query in norm(r.get("label", "")):
                hits.append("%s: room '%s' (%s), %.2f m²" % (s["folder"], r.get("name"), r.get("label"), r.get("area_m2", 0)))
        for o in room.get("objects", []):
            if query in norm(o.get("category", "")):
                size = " × ".join("%.2f" % v for v in o.get("size_m", []))
                hits.append("%s: %s, %s m (w × d × h), at %s" % (s["folder"], o.get("category"), size, o.get("center")))
    return text("\n".join(hits) if hits else "Nothing matching '%s'." % args.get("query"))


def tool_export_paths(lib, args):
    folder = lib.safe("Exports", lib.resolve(args.get("scan", "")))
    lines = []
    for dirpath, _, files in os.walk(folder):
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            note = " (in iCloud, not downloaded)" if lib.is_dataless(p) else ""
            lines.append("%s  %d bytes%s" % (p, os.stat(p).st_size, note))
    return text("\n".join(sorted(lines)) or "No exported files.")


SCAN_ARG = {"scan": {"type": "string", "description": "Scan name from list_scans (case-insensitive; a unique prefix is enough)."}}
TOOLS = [
    ("list_scans", "List the room scans made with Plan & Model (name, floor area, rooms, date).", {}, [], tool_list_scans),
    ("get_summary", "Markdown summary of a scan: rooms and areas, wall lengths, doors, windows, objects, accuracy caveats.",
     SCAN_ARG, ["scan"], tool_get_summary),
    ("get_room_json", "The scan as structured data (room.json, schema lidarscan.claude/1, metres): rooms with polygons and areas, "
     "walls with start/end/length/height, openings, objects, adjacency.", SCAN_ARG, ["scan"], tool_get_room_json),
    ("get_plan_image", "The dimensioned floor plan as a PNG image.", SCAN_ARG, ["scan"], tool_get_plan_image),
    ("get_render", "A drawing of the scan as a PNG image: view 'plan', 'elevations' or 'furniture'.",
     dict(SCAN_ARG, view={"type": "string", "enum": sorted(RENDERS)}), ["scan"], tool_get_render),
    ("find", "Search all scans for rooms (by name or type) and objects (by category, e.g. sofa, bed, table).",
     {"query": {"type": "string"}}, ["query"], tool_find),
    ("export_paths", "Absolute paths of a scan's exported files (DXF, OBJ, STL, USDZ, GLB, PDF, ...) for Blender, FreeCAD or scripts.",
     SCAN_ARG, ["scan"], tool_export_paths),
]
HANDLERS = {t[0]: t[4] for t in TOOLS}


def tool_list():
    return [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p, "required": r},
             "annotations": {"readOnlyHint": True}} for n, d, p, r, _ in TOOLS]


def handle(lib, msg):
    """Response dict for one JSON-RPC message, or None for notifications."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                  "instructions": "Read-only access to Plan & Model room scans in iCloud Drive. Start with list_scans."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tool_list()}
    elif method == "tools/call":
        params = msg.get("params") or {}
        handler = HANDLERS.get(params.get("name"))
        if handler is None:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "Unknown tool: %s" % params.get("name")}}
        try:
            result = handler(lib, params.get("arguments") or {})
        except ToolError as e:
            result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        except Exception as e:  # report, never crash the server
            result = {"content": [{"type": "text", "text": "Internal error: %s" % e}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found: %s" % method}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    lib = Library(os.environ.get("LIDARSCAN_ROOT", DEFAULT_ROOT))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(lib, msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
