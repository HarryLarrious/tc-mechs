"""Serves the animation editor (tools/animator) and saves its drafts.

    python3 tools/animator/serve.py [port]      (default $PORT, else 8767)

Then open http://127.0.0.1:8767/tools/animator/. It serves the repository
read-only (the editor loads tools/viewer/mech_data.js for the mech and
mech/animations/*.json for the game's animations), on 127.0.0.1 only, and
takes two writes:

  GET  /drafts            the drafts' names (JSON list)
  GET  /animations        the game's animations' names (JSON list)
  POST /drafts/<name>     saves the request body (an animation, JSON) as
                          tools/animator/drafts/<name>.json

Drafts are where the editor's rough animations go for polishing; the game
bakes only mech/animations/*.json (pack/src/mech_pilot.py).
"""

from __future__ import annotations

import json
import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRAFTS = Path(__file__).resolve().parent / "drafts"
NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_BYTES = 2_000_000


def format_anim(doc: dict) -> str:
    """An animation as JSON with one key per line (readable diffs)."""
    head = {k: v for k, v in doc.items() if k != "keys"}
    lines = ["{"] + [f" {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    lines.append(' "keys": [')
    lines.append(",\n".join("  " + json.dumps(k) for k in doc.get("keys", [])))
    lines += [" ]", "}"]
    return "\n".join(lines) + "\n"


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") == "/drafts":
            names = sorted(p.stem for p in DRAFTS.glob("*.json"))
            return self.reply(200, json.dumps(names))
        if self.path.rstrip("/") == "/animations":
            names = sorted(p.stem for p in (ROOT / "mech/animations").glob("*.json"))
            return self.reply(200, json.dumps(names))
        return super().do_GET()

    def do_POST(self):
        m = re.match(r"^/drafts/([^/?]+)$", self.path)
        if not m or not NAME.match(m.group(1)):
            return self.reply(400, json.dumps({"error": "bad draft name (letters, digits, - and _)"}))
        size = int(self.headers.get("Content-Length", 0))
        if size <= 0 or size > MAX_BYTES:
            return self.reply(413, json.dumps({"error": "empty or too big"}))
        try:
            doc = json.loads(self.rfile.read(size))
            if not isinstance(doc, dict) or not isinstance(doc.get("keys"), list):
                raise ValueError("no keys")
        except ValueError as e:
            return self.reply(400, json.dumps({"error": f"not an animation: {e}"}))
        DRAFTS.mkdir(exist_ok=True)
        path = DRAFTS / f"{m.group(1)}.json"
        path.write_text(format_anim(doc))
        return self.reply(200, json.dumps({"saved": str(path.relative_to(ROOT))}))

    def reply(self, code: int, body: str):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        # always fresh: the mech data and animations change with each build
        if not self.path.startswith(("/drafts", "/animations")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8767))
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(ROOT)))
    print(f"animator: http://127.0.0.1:{port}/tools/animator/  (drafts in {DRAFTS.relative_to(ROOT)})")
    server.serve_forever()


if __name__ == "__main__":
    main()
