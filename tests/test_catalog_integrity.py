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


def test_scale_bounds_always_cite_their_source():
    """An invented size envelope is worse than none - it silently scores."""
    for m in load_catalog(default_catalog_root()).methods:
        if any(v is not None for v in (m.scale.min_rows, m.scale.max_rows,
                                       m.scale.max_cols)):
            assert m.scale.evidence, f"{m.id} states a scale with no evidence"


def test_every_catalog_file_parses_as_yaml():
    """An unquoted colon inside a caveat silently breaks the whole catalog."""
    import yaml
    root = default_catalog_root()
    for path in sorted(root.rglob("*.yaml")):
        try:
            yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise AssertionError(f"{path.name} is not valid YAML: {exc}") from exc


def test_data_types_are_all_in_the_taxonomy():
    catalog = load_catalog(default_catalog_root())
    allowed = set(catalog.taxonomy["data_types"])
    for m in catalog.methods:
        assert set(m.data_types) <= allowed, f"{m.id} uses an unknown data type"


def test_every_rankable_method_has_an_output_preview():
    for m in load_catalog(default_catalog_root()).generation_methods():
        assert m.output_preview, f"{m.id} has no output_preview"


def test_image_previews_contain_a_specification_not_image_data():
    """A fabricated medical image presented as output would be a lie told by
    a tool whose whole subject is synthetic data honesty."""
    for m in load_catalog(default_catalog_root()).methods:
        p = m.output_preview
        if p and p.format == "image_spec":
            body = p.preview.lower()
            assert "data:image" not in body
            assert "base64" not in body
            assert any(ch.isdigit() for ch in body), (
                f"{m.id} image_spec should state concrete dimensions")


def test_preview_format_suits_the_data_type():
    """A CSV snippet for a graph method tells the user nothing."""
    expected = {"images": "image_spec", "graph": "graph_edgelist",
                "genomic": "genomic_matrix"}
    for m in load_catalog(default_catalog_root()).generation_methods():
        for dt, fmt in expected.items():
            if m.data_types == [dt] and m.output_preview:
                assert m.output_preview.format == fmt, (
                    f"{m.id} handles only {dt} but previews as "
                    f"{m.output_preview.format}")
