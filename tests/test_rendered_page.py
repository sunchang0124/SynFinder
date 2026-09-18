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
def results_page(server):
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:
            pytest.skip(f"no browser available: {exc}")
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
        browser.close()


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
