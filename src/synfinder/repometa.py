"""Compare catalog entries with what their repositories say.

Pure logic only; the network lives in tools/sync_repos.py, which writes
catalog/repo_metadata.json. Tests read that committed file, so CI never
depends on GitHub being reachable.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_GITHUB = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)")

LICENSE_ALIASES = {
    "GPL-3.0-only": "GPL-3.0", "GPL-3.0-or-later": "GPL-3.0",
    "GPL-2.0-only": "GPL-2.0", "GPL-2.0-or-later": "GPL-2.0",
    "LGPL-3.0-only": "LGPL-3.0", "LGPL-3.0-or-later": "LGPL-3.0",
    "LGPL-2.1-only": "LGPL-2.1", "LGPL-2.1-or-later": "LGPL-2.1",
    "BSD-3-Clause-Clear": "BSD-3-Clause",
}
_UNKNOWN_LICENSE = {None, "", "NOASSERTION", "other"}

LANGUAGE_MAP = {
    "python": "python", "jupyter notebook": "python", "r": "r",
    "julia": "julia", "c++": "cpp", "c": "cpp", "java": "java",
    "javascript": "javascript", "typescript": "javascript",
}

MAINTAINED_WINDOW_DAYS = 730  # 24 months


def github_slug(url: str | None) -> str | None:
    if not url:
        return None
    m = _GITHUB.match(url.strip())
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}"


def normalise_license(spdx: str | None) -> str | None:
    if spdx in _UNKNOWN_LICENSE:
        return None
    return LICENSE_ALIASES.get(spdx, spdx)


def map_language(name: str | None) -> str | None:
    if not name:
        return None
    return LANGUAGE_MAP.get(name.lower())


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def is_maintained(pushed_at: str, archived: bool, fetched_at: str) -> bool:
    if archived:
        return False
    return (_parse(fetched_at) - _parse(pushed_at)).days <= MAINTAINED_WINDOW_DAYS


def drift(entry, meta: dict, fetched_at: str) -> list[str]:
    """Human-readable disagreements between a catalog entry and its repo."""
    out: list[str] = []
    repo_license = normalise_license(meta.get("license_spdx"))
    if repo_license and normalise_license(entry.license) != repo_license:
        out.append(f"{entry.id}: license is {entry.license!r} but the "
                   f"repository says {repo_license!r}")
    repo_lang = map_language(meta.get("language"))
    lang = getattr(entry, "language", None)
    if repo_lang and lang and lang != "multiple" and lang != repo_lang:
        out.append(f"{entry.id}: language is {lang!r} but the repository "
                   f"says {repo_lang!r}")
    pushed = meta.get("pushed_at")
    year = getattr(entry, "last_updated", None)
    if pushed and year is not None and year != _parse(pushed).year:
        out.append(f"{entry.id}: last_updated is {year} but the repository "
                   f"was last pushed in {_parse(pushed).year}")
    maturity = getattr(entry, "maturity", None)
    if pushed and maturity is not None:
        expected = is_maintained(pushed, bool(meta.get("archived")), fetched_at)
        if maturity.maintained != expected:
            why = "archived" if meta.get("archived") else (
                f"last pushed {pushed[:10]}")
            out.append(f"{entry.id}: maintained is {maturity.maintained} but "
                       f"the repository is {why}, so it should be {expected}")
    return out


def load_metadata(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def rewrite_fields(text: str, updates: dict[str, str]) -> str:
    """Replace scalar lines in a YAML file without reserialising it.

    Keys are top-level (`license`) or one level under `maturity`
    (`maturity.maintained`). A missing top-level key is inserted after the
    `license:` line. Comments, order and quoting elsewhere are untouched.
    """
    lines = text.split("\n")
    for key, value in updates.items():
        if "." in key:
            parent, child = key.split(".", 1)
            inside = False
            for i, line in enumerate(lines):
                if line.startswith(f"{parent}:"):
                    inside = True
                    continue
                if inside and line and not line.startswith(" "):
                    inside = False
                if inside and line.lstrip().startswith(f"{child}:"):
                    indent = line[:len(line) - len(line.lstrip())]
                    lines[i] = f"{indent}{child}: {value}"
                    break
            continue
        for i, line in enumerate(lines):
            if line.startswith(f"{key}:"):
                lines[i] = f"{key}: {value}"
                break
        else:
            for i, line in enumerate(lines):
                if line.startswith("license:"):
                    lines.insert(i + 1, f"{key}: {value}")
                    break
    return "\n".join(lines)
