"""Local page for reviewing each method's purposes against the evidence.

    .venv/bin/python tools/review/app.py            # http://localhost:8600
    PORT=8700 .venv/bin/python tools/review/app.py

Reads review/sources/<id>.json and review/evidence/<id>.json, writes
review/decisions.json. Stdlib only; nothing leaves the machine.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from synfinder.catalog import load_catalog  # noqa: E402

HERE = Path(__file__).resolve().parent
SRC, EVD, DEC = ROOT / "review" / "sources", ROOT / "review" / "evidence", ROOT / "review" / "decisions.json"


def state() -> dict:
    cat = load_catalog(ROOT / "catalog")
    decisions = json.loads(DEC.read_text()) if DEC.exists() else {}
    methods = []
    for m in cat.methods:
        src = json.loads((SRC / f"{m.id}.json").read_text()) if (SRC / f"{m.id}.json").exists() else {}
        evd = json.loads((EVD / f"{m.id}.json").read_text()) if (EVD / f"{m.id}.json").exists() else {}
        links = {}
        for k in ("paper", "code", "docs"):
            r = src.get(k)
            if not r:
                continue
            links[k] = {"url": r.get("url"),
                        "status": r.get("api_status") or r.get("status") or r.get("http_status"),
                        "title": r.get("title") or r.get("description") or r.get("full_name"),
                        "year": r.get("year"), "renamed": r.get("full_name") if r.get("renamed") else None,
                        "archived": r.get("archived"), "fulltext": bool(r.get("fulltext") or r.get("readme"))}
        methods.append({"id": m.id, "name": m.name, "family": m.family,
                        "toolkit": bool(m.is_framework),
                        "current": list(m.purposes), "caveats": m.caveats,
                        "links": links, "evidence": evd.get("purposes", {}),
                        "link_notes": evd.get("link_notes"),
                        "decision": decisions.get(m.id)})
    return {"purposes": cat.taxonomy["purposes"], "methods": methods,
            "definitions": (HERE / "PURPOSES.md").read_text()}


class H(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._send(200, (HERE / "review.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._send(200, json.dumps(state()).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/decision":
            return self._send(404, b"not found", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        decisions = json.loads(DEC.read_text()) if DEC.exists() else {}
        if body.get("clear"):
            decisions.pop(body["id"], None)
        else:
            decisions[body["id"]] = {"purposes": body["purposes"], "notes": body.get("notes", ""),
                                     "links_ok": body.get("links_ok", True),
                                     "reviewer": body.get("reviewer") or "Chang Sun",
                                     "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        DEC.write_text(json.dumps(decisions, indent=1, ensure_ascii=False, sort_keys=True))
        self._send(200, json.dumps({"ok": True, "saved": len(decisions)}).encode(), "application/json")

    def log_message(self, *a) -> None:  # quiet
        pass


def main() -> int:
    port = int(os.environ.get("PORT", "8600"))
    print(f"purpose review on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
