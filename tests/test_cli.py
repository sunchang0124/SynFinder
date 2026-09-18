from synfinder.cli import main

FIND = ["find", "--domain", "biomedical",
        "--data-type", "tabular_cross_sectional",
        "--purpose", "ml_augmentation", "--privacy", "none"]


def test_find_prints_a_shortlist(capsys):
    assert main(FIND) == 0
    assert "Recommended methods" in capsys.readouterr().out


def test_find_writes_a_report_file(tmp_path):
    target = tmp_path / "report.md"
    assert main(FIND + ["--out", str(target)]) == 0
    assert "Recommended methods" in target.read_text()


def test_find_rejects_a_data_type_outside_the_taxonomy(capsys):
    argv = ["find", "--domain", "biomedical", "--data-type", "holograms",
            "--purpose", "ml_augmentation", "--privacy", "none"]
    assert main(argv) == 2
    assert "holograms" in capsys.readouterr().err


def test_datasets_lists_the_registry(capsys):
    assert main(["datasets"]) == 0
    assert "SyntheticMass" in capsys.readouterr().out


def test_datasets_filters_by_data_type(capsys):
    assert main(["datasets", "--data-type", "images"]) == 0
    out = capsys.readouterr().out
    assert "SyntheticMass" not in out
    assert "No dataset" in out


def test_no_subcommand_prints_help(capsys):
    assert main([]) == 2
