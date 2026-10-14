"""Fetch repository facts for every catalog entry with a GitHub code link.

Writes catalog/repo_metadata.json. Run by a maintainer, not by CI:

    .venv/bin/python tools/sync_repos.py            # resume, skip fresh entries
    .venv/bin/python tools/sync_repos.py --force    # refetch everything

Uses GITHUB_TOKEN or `gh auth token` when available (5,000 requests/hour);
unauthenticated access allows 60, so a full run takes about three sessions.
On a rate limit the partial file is written and the script exits 3 with the
reset time; rerun after it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synfinder.catalog import load_catalog  # noqa: E402
from synfinder.repometa import github_slug  # noqa: E402

OUT = ROOT / "catalog" / "repo_metadata.json"
FRESH_DAYS = 7


def _token() -> str | None:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _get(url: str, token: str | None) -> tuple[int, dict | None, dict]:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "synfinder-sync",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, None, dict(e.headers)
    except (urllib.error.URLError, OSError, ValueError):
        return 0, None, {}


def fetch(slug: str, token: str | None) -> tuple[dict | None, int, dict]:
    status, repo, headers = _get(f"https://api.github.com/repos/{slug}", token)
    if status != 200 or repo is None:
        return None, status, headers
    meta = {
        "slug": repo.get("full_name", slug),
        "license_spdx": (repo.get("license") or {}).get("spdx_id"),
        "language": repo.get("language"),
        "pushed_at": repo.get("pushed_at"),
        "archived": bool(repo.get("archived")),
        "stars": repo.get("stargazers_count"),
        "latest_release": None,
    }
    rstatus, rel, headers = _get(
        f"https://api.github.com/repos/{slug}/releases/latest", token)
    if _rate_limited(rstatus, headers):
        return None, rstatus, headers
    if rstatus == 200 and rel:
        meta["latest_release"] = {"tag": rel.get("tag_name"),
                                  "published_at": rel.get("published_at")}
    return meta, 200, headers


def _rate_limited(status: int, headers: dict) -> bool:
    return status in (403, 429) and headers.get("X-RateLimit-Remaining") == "0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="refetch fresh entries too")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    existing = json.loads(OUT.read_text()) if OUT.exists() else {}
    data = {"fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "entries": dict(existing.get("entries", {})),
            "errors": {}, "unverifiable": {}}
    stamps = existing.get("stamps", {})
    data["stamps"] = dict(stamps)
    token = _token()

    catalog = load_catalog(ROOT / "catalog")
    for entry in catalog.methods + catalog.datasets:
        slug = github_slug(entry.links.code)
        if slug is None:
            if entry.links.code:
                data["unverifiable"][entry.id] = entry.links.code
            continue
        stamp = stamps.get(entry.id)
        if (not args.force and stamp and entry.id in data["entries"]
                and now - datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                < timedelta(days=FRESH_DAYS)):
            continue
        meta, status, headers = fetch(slug, token)
        if _rate_limited(status, headers):
            OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
            reset = headers.get("X-RateLimit-Reset")
            when = (datetime.fromtimestamp(int(reset), timezone.utc).isoformat()
                    if reset else "unknown")
            print(f"rate limited; partial results written; resets at {when}",
                  file=sys.stderr)
            return 3
        if meta is None:
            data["errors"][entry.id] = {"slug": slug, "status": status}
            data["entries"].pop(entry.id, None)
            print(f"  {entry.id}: HTTP {status} for {slug}")
            continue
        data["entries"][entry.id] = meta
        data["stamps"][entry.id] = data["fetched_at"]
        print(f"  {entry.id}: {slug} ok")

    OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['entries'])} entries, "
          f"{len(data['errors'])} errors, {len(data['unverifiable'])} unverifiable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
