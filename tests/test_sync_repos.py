import importlib.util
import json
import urllib.error
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "sync_repos", Path(__file__).resolve().parents[1] / "tools" / "sync_repos.py")
sync_repos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_repos)

REPO = {"full_name": "x/y", "license": {"spdx_id": "MIT"}, "language": "Python",
        "pushed_at": "2026-09-30T00:00:00Z", "archived": False,
        "stargazers_count": 1}


def test_rate_limit_on_the_release_call_is_propagated(monkeypatch):
    limited = {"X-RateLimit-Remaining": "0"}

    def fake_get(url, token):
        if url.endswith("/releases/latest"):
            return 403, None, limited
        return 200, REPO, {}

    monkeypatch.setattr(sync_repos, "_get", fake_get)
    assert sync_repos.fetch("x/y", None) == (None, 403, limited)


def test_network_errors_become_status_zero(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(sync_repos.urllib.request, "urlopen", boom)
    assert sync_repos._get("https://api.github.com/x", None) == (0, None, {})


def test_bad_json_becomes_status_zero(monkeypatch):
    class R:
        status = 200
        headers = {}
        def read(self): return b"not json"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(sync_repos.urllib.request, "urlopen", lambda *a, **k: R())
    assert sync_repos._get("https://api.github.com/x", None)[:2] == (0, None)
