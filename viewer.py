#!/usr/bin/env python3
"""Springfield Viewer — serves viewer.html with a local API for browsing Claude JSONL logs.

Usage:
    python3 viewer.py [--port PORT] [--springfield-dir DIR]

Defaults:
    --port 7890
    --springfield-dir ~/.springfield
"""

import argparse
import json
import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def find_viewer_html():
    """Find viewer.html next to this script."""
    return Path(__file__).parent / "viewer.html"


class ViewerHandler(SimpleHTTPRequestHandler):
    springfield_dir = None

    def log_message(self, format, *args):
        # Quieter logging — only errors
        if args and isinstance(args[0], str) and args[0].startswith("GET /api/"):
            return
        super().log_message(format, *args)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/viewer.html":
            self._serve_html()
        elif parsed.path == "/api/index":
            self._serve_index()
        elif parsed.path == "/api/session":
            params = parse_qs(parsed.query)
            project = params.get("project", [None])[0]
            session_file = params.get("file", [None])[0]
            if project and session_file:
                self._serve_session(project, session_file)
            else:
                self._json_response(400, {"error": "missing project or file param"})
        else:
            self._json_response(404, {"error": "not found"})

    def _serve_html(self):
        html_path = find_viewer_html()
        if not html_path.exists():
            self._json_response(500, {"error": "viewer.html not found"})
            return
        content = html_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _find_ralphhomes(base):
        """Recursively find all ralphhome/.claude directories under base."""
        results = []
        try:
            for entry in sorted(base.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name == "ralphhome":
                    claude_dir = entry / ".claude"
                    if claude_dir.is_dir():
                        results.append((entry.parent, claude_dir))
                else:
                    results.extend(ViewerHandler._find_ralphhomes(entry))
        except PermissionError:
            pass
        return results

    def _serve_index(self):
        """Return project list with session metadata (filenames + mtimes)."""
        base = Path(self.springfield_dir)
        if not base.is_dir():
            self._json_response(200, {"projects": {}})
            return

        projects = {}

        for project_dir, claude_dir in self._find_ralphhomes(base):
            project_name = str(project_dir.relative_to(base))

            # Read history.jsonl
            history = []
            history_file = claude_dir / "history.jsonl"
            if history_file.is_file():
                history = self._read_jsonl(history_file)

            # Find session files
            sessions = {}
            projects_dir = claude_dir / "projects"
            if projects_dir.is_dir():
                for encoding_dir in projects_dir.iterdir():
                    if not encoding_dir.is_dir():
                        continue
                    for jsonl_file in encoding_dir.glob("*.jsonl"):
                        rel = jsonl_file.name
                        stat = jsonl_file.stat()
                        mtime_iso = self._ns_to_iso(stat.st_mtime_ns)
                        preview = self._session_preview(jsonl_file)
                        sessions[rel] = {
                            "mtime": mtime_iso,
                            "preview": preview,
                        }

            projects[project_name] = {
                "history": history,
                "sessions": sessions,
            }

        self._json_response(200, {"projects": projects})

    def _serve_session(self, project, session_file):
        """Return parsed JSONL lines for a specific session."""
        base = Path(self.springfield_dir)
        project_path = base / project
        rh_claude = project_path / "ralphhome" / ".claude" / "projects"

        if not rh_claude.is_dir():
            self._json_response(404, {"error": "project not found"})
            return

        project_dir = rh_claude

        # Session file could be in any encoding subdirectory
        # Sanitize to prevent path traversal
        safe_file = Path(session_file).name
        if safe_file != session_file or ".." in session_file:
            self._json_response(400, {"error": "invalid filename"})
            return

        for encoding_dir in project_dir.iterdir():
            if not encoding_dir.is_dir():
                continue
            candidate = encoding_dir / safe_file
            if candidate.is_file():
                lines = self._read_jsonl(candidate)
                self._json_response(200, lines)
                return

        self._json_response(404, {"error": "session not found"})

    @staticmethod
    def _ns_to_iso(mtime_ns):
        """Convert nanosecond mtime to ISO 8601 string."""
        from datetime import datetime, timezone
        return datetime.fromtimestamp(mtime_ns / 1e9, tz=timezone.utc).isoformat()

    @staticmethod
    def _session_preview(path):
        """Read the first user message from a session file for sidebar preview."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        line = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if line.get("type") != "user":
                        continue
                    msg = line.get("message", {})
                    content = msg.get("content")
                    if isinstance(content, str):
                        import re
                        text = re.sub(r"<[^>]+>", "", content).strip()
                        if text:
                            return text[:100]
                    elif isinstance(content, list):
                        for block in content:
                            if block.get("type") == "text" and block.get("text"):
                                import re
                                text = re.sub(r"<[^>]+>", "", block["text"]).strip()
                                if text:
                                    return text[:100]
        except OSError:
            pass
        return ""

    def _read_jsonl(self, path):
        lines = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass
        return lines

    def _json_response(self, status, data):
        body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Springfield Claude Chat Viewer")
    parser.add_argument(
        "--port", type=int, default=7890, help="Port to serve on (default: 7890)"
    )
    parser.add_argument(
        "--springfield-dir",
        default=os.path.expanduser("~/.springfield"),
        help="Path to .springfield directory (default: ~/.springfield)",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Don't auto-open browser"
    )
    args = parser.parse_args()

    ViewerHandler.springfield_dir = args.springfield_dir

    if not Path(args.springfield_dir).is_dir():
        print(f"Warning: {args.springfield_dir} does not exist yet", file=sys.stderr)

    if not find_viewer_html().exists():
        print(f"Error: viewer.html not found at {find_viewer_html()}", file=sys.stderr)
        sys.exit(1)

    # Show discovered projects at startup
    base = Path(args.springfield_dir)
    if base.is_dir():
        found = ViewerHandler._find_ralphhomes(base)
        if found:
            print(f"Found {len(found)} project(s):")
            for proj_dir, _ in found:
                print(f"  {proj_dir.relative_to(base)}")
        else:
            print(f"No projects found in {args.springfield_dir}")
            print("  Expected: <dir>/ralphhome/.claude/projects/*.jsonl")

    server = HTTPServer(("127.0.0.1", args.port), ViewerHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Springfield Viewer running at {url}")
    print(f"Watching: {args.springfield_dir}")
    print("Press Ctrl+C to stop")

    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
