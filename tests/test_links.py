"""Check that every link in the catalog still resolves.

Opt-in, because it hits the network: run with SYNFINDER_CHECK_LINKS=1.
It exists because four method repositories and one whole dataset host were
found dead only when a user complained - a class of rot no offline test sees.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest

from synfinder.catalog import load_catalog
from synfinder.cli import default_catalog_root

pytestmark = pytest.mark.skipif(
    os.environ.get("SYNFINDER_CHECK_LINKS") != "1",
    reason="set SYNFINDER_CHECK_LINKS=1 to check links over the network",
)

# Hosts that reject automated HEAD requests but are fine in a browser.
TOLERATE = {202, 403, 405, 429}  # IEEE answers bots with 202


def _links():
    catalog = load_catalog(default_catalog_root())
    for m in catalog.methods:
        for kind, url in (("paper", m.links.paper), ("code", m.links.code),
                          ("docs", m.links.docs)):
            if url and url.startswith("http"):
                yield f"method {m.id} {kind}", url
    for d in catalog.datasets:
        for kind, url in (("paper", d.links.paper), ("code", d.links.code),
                          ("docs", d.links.docs)):
            if url and url.startswith("http"):
                yield f"dataset {d.id} {kind}", url


def _status(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={
        "User-Agent": "Mozilla/5.0 (compatible; synfinder-linkcheck)"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status
    except urllib.error.HTTPError as e:
        if e.code in (405, 501):  # HEAD unsupported - retry as GET
            try:
                get = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; synfinder-linkcheck)"})
                with urllib.request.urlopen(get, timeout=25) as r:
                    return r.status
            except urllib.error.HTTPError as e2:
                return e2.code
            except Exception:
                return 0
        return e.code
    except Exception:
        return 0


@pytest.mark.parametrize("label,url", list(_links()), ids=lambda v: v)
def test_link_resolves(label, url):
    code = _status(url)
    assert code == 200 or code in TOLERATE, f"{label}: HTTP {code} for {url}"
