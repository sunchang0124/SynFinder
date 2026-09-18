from synfinder.catalog import load_catalog
from synfinder.cli import default_catalog_root


def test_the_real_catalog_loads():
    catalog = load_catalog(default_catalog_root())
    assert catalog.methods, "catalog is empty"


def test_every_method_has_caveats_and_links():
    for m in load_catalog(default_catalog_root()).methods:
        assert m.caveats, f"{m.id} has no caveats"
        assert m.links.code or m.links.paper, f"{m.id} has no paper or code link"


def test_related_dataset_ids_resolve():
    catalog = load_catalog(default_catalog_root())
    known = {d.id for d in catalog.datasets}
    for m in catalog.methods:
        for ref in m.related_datasets:
            assert ref in known, f"{m.id} references unknown dataset {ref}"
