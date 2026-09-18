"""Build the static GitHub Pages site.

The page runs the real synfinder package in the browser through Pyodide, so
the hosted version and the CLI share one ranking implementation. Nothing is
reimplemented in JavaScript.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs_site"


def main() -> int:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()

    # 1. a wheel of the package, installed in the browser by micropip
    subprocess.run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps",
                    "-w", str(DOCS)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    wheel = next(DOCS.glob("synfinder-*.whl")).name

    # 2. the catalog as one bundle, unpacked into Pyodide's filesystem
    catalog = {}
    for p in sorted((ROOT / "catalog").rglob("*.yaml")):
        catalog[p.relative_to(ROOT / "catalog").as_posix()] = p.read_text()
    (DOCS / "catalog.json").write_text(json.dumps(catalog))

    # 3. the frontend, with the static bootstrap swapped in
    html = (ROOT / "web" / "index.html").read_text()
    html = html.replace("/*__CSS__*/", (ROOT / "web" / "style.css").read_text())
    html = html.replace("/*__JS__*/", (ROOT / "web" / "app.js").read_text())
    html = html.replace("__BUILD__", "pages")
    html = html.replace("</head>",
        '<script src="https://cdn.jsdelivr.net/pyodide/v0.28.0/full/pyodide.js"></script>\n'
        f'<script>window.SYNFINDER_WHEEL="{wheel}";</script>\n'
        '<script src="boot.js"></script>\n</head>')
    (DOCS / "index.html").write_text(html)
    shutil.copy(ROOT / "web" / "boot.js", DOCS / "boot.js")
    (DOCS / ".nojekyll").touch()

    size = sum(p.stat().st_size for p in DOCS.rglob("*") if p.is_file())
    print(f"built {DOCS.relative_to(ROOT)}  ({size/1e6:.2f} MB, wheel {wheel})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
