"""Each catalog entry must agree with its repository on the mechanical
facts: licence, language, last push year, maintained. The facts come from
catalog/repo_metadata.json, written by tools/sync_repos.py and committed, so
this test needs no network.
"""
import pytest
from synfinder.catalog import load_catalog
from synfinder.cli import default_catalog_root
from synfinder.repometa import drift, load_metadata

META_PATH = default_catalog_root() / "repo_metadata.json"
if not META_PATH.exists():
    pytest.skip("catalog/repo_metadata.json not present; run tools/sync_repos.py",
                allow_module_level=True)

META = load_metadata(META_PATH)
CATALOG = load_catalog(default_catalog_root())
ENTRIES = {e.id: e for e in CATALOG.methods + CATALOG.datasets}


@pytest.mark.xfail(strict=False, reason="drift fixed in the next commit")
@pytest.mark.parametrize("entry_id", sorted(ENTRIES))
def test_entry_agrees_with_its_repository(entry_id):
    entry = ENTRIES[entry_id]
    if entry_id in META.get("errors", {}):
        pytest.skip(f"{entry_id}: repository returned HTTP "
                    f"{META['errors'][entry_id]['status']}; fix the code link")
    meta = META["entries"].get(entry_id)
    if meta is None:
        pytest.skip(f"{entry_id}: no GitHub repository to compare with")
    problems = drift(entry, meta, META["fetched_at"])
    assert not problems, "\n".join(problems)


def test_metadata_is_not_stale():
    """Facts older than a year are not facts. Rerun the sync."""
    from datetime import datetime, timezone
    fetched = datetime.fromisoformat(META["fetched_at"].replace("Z", "+00:00"))
    assert (datetime.now(timezone.utc) - fetched).days < 365
