"""Layout checks against a real browser.

These exist because a CSS class collision once crushed the "How to check it
worked" block to 15x15 pixels. The HTML was correct, the CSS was present, and
every text-level test passed - the fault was only visible as geometry.
"""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    proc = subprocess.Popen(
        ["uvicorn", "synfinder.web:app", "--port", str(port), "--app-dir",
         str(ROOT / "src")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.5)
    else:
        proc.terminate()
        pytest.skip("server did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def playwright():
    """One instance for the module. The sync API cannot be nested, so a second
    sync_playwright() inside a test raises while this fixture is held open."""
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="module")
def browser(playwright):
    try:
        b = playwright.chromium.launch()
    except Exception as exc:
        pytest.skip(f"no browser available: {exc}")
    yield b
    b.close()


@pytest.fixture(scope="module")
def results_page(server, browser):
    if True:
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server, wait_until="networkidle")
        page.select_option("#domain", "biomedical")
        page.select_option("#data_type", "tabular_cross_sectional")
        page.select_option("#purpose", "ml_augmentation")
        page.select_option("#privacy", "not_required")
        page.click("#submitBtn")
        page.wait_for_selector(".card", timeout=20000)
        page.wait_for_timeout(600)
        yield page, errors
        page.close()


def test_no_javascript_errors(results_page):
    _, errors = results_page
    assert errors == []


def test_every_callout_is_actually_visible(results_page):
    """The collision bug: a rule meant for the 15px tooltip button matched
    the callout and collapsed it. Text was present but the box was a dot."""
    page, _ = results_page
    boxes = page.evaluate("""() => [...document.querySelectorAll('.callout')]
      .map(el => { const r = el.getBoundingClientRect();
                   return {w: Math.round(r.width), h: Math.round(r.height),
                           cls: el.className,
                           clipped: el.scrollWidth > el.clientWidth + 1}; })""")
    assert boxes, "expected callouts on a result card"
    for b in boxes:
        assert b["w"] > 200, f"callout {b['cls']} is only {b['w']}px wide"
        assert b["h"] > 40, f"callout {b['cls']} is only {b['h']}px tall"
        assert not b["clipped"], f"callout {b['cls']} clips its own content"


def test_the_evaluation_block_renders_its_steps_as_list_items(results_page):
    page, _ = results_page
    info = page.evaluate("""() => {
      const el = document.querySelector('.callout.info');
      if (!el) return null;
      return {heading: el.querySelector('.k')?.innerText,
              items: el.querySelectorAll('li').length};
    }""")
    assert info, "no evaluation callout found"
    assert "HOW TO CHECK IT WORKED" in info["heading"].upper()
    assert info["items"] >= 1


def test_the_tooltip_button_stays_small_and_round(results_page):
    """The other half of the collision - the fix must not inflate the button."""
    page, _ = results_page
    tip = page.evaluate("""() => {
      const t = document.querySelector('.infotip');
      if (!t) return null;
      const r = t.getBoundingClientRect();
      return {w: Math.round(r.width), h: Math.round(r.height),
              radius: getComputedStyle(t).borderRadius};
    }""")
    assert tip, "no tooltip button found"
    assert tip["w"] <= 24 and tip["h"] <= 24
    assert "50%" in tip["radius"]


def test_nothing_overflows_the_viewport_horizontally(results_page):
    page, _ = results_page
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 1, f"page scrolls horizontally by {overflow}px"


@pytest.fixture(scope="module")
def static_site(tmp_path_factory):
    """Build the GitHub Pages bundle and serve it like GitHub would."""
    import http.server
    import shutil
    import threading

    if shutil.which("pip") is None:
        pytest.skip("pip needed to build the wheel")
    subprocess.run([__import__("sys").executable, "tools/build_pages.py"],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    directory = str(ROOT / "docs_site")
    port = _free_port()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)
        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}/"
    server.shutdown()


def test_static_build_agrees_with_the_python_engine(static_site, browser):
    """The hosted page runs the same package under Pyodide. If it ever
    disagrees with the engine, the whole no-second-implementation argument
    has failed."""
    from synfinder.catalog import load_catalog
    from synfinder.cli import default_catalog_root
    from synfinder.intake import Intake
    from synfinder.ranking import load_weights, rank

    root = default_catalog_root()
    catalog = load_catalog(root)
    intake = Intake(domain="biomedical", data_type="genomic",
                    purpose="open_release", privacy="required")
    expected = [c.method.name for c in rank(
        catalog.generation_methods(), intake,
        load_weights(root / "weights.yaml"), top_n=24).shortlist[:5]]

    page = browser.new_page()
    try:
        page.goto(static_site, wait_until="domcontentloaded")
        page.wait_for_function(
            "document.querySelectorAll('#domain option').length > 0",
            timeout=300000)
        page.select_option("#domain", "biomedical")
        page.select_option("#data_type", "genomic")
        page.select_option("#purpose", "open_release")
        page.select_option("#privacy", "required")
        page.click("#submitBtn")
        page.wait_for_selector(".card", timeout=180000)
        got = page.eval_on_selector_all(".card h3",
                                        "e => e.map(x => x.textContent)")
    finally:
        page.close()
    assert got == expected, f"browser said {got}, engine said {expected}"
