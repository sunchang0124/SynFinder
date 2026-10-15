from synfinder.cli import main

FIND = ["find", "--domain", "biomedical",
        "--data-type", "tabular_cross_sectional",
        "--purpose", "ml_augmentation", "--privacy", "not_required"]


def test_find_prints_a_shortlist(capsys):
    assert main(FIND) == 0
    assert "Recommended methods" in capsys.readouterr().out


def test_find_writes_a_report_file(tmp_path):
    target = tmp_path / "report.md"
    assert main(FIND + ["--out", str(target)]) == 0
    assert "Recommended methods" in target.read_text()


def test_find_rejects_a_data_type_outside_the_taxonomy(capsys):
    argv = ["find", "--domain", "biomedical", "--data-type", "holograms",
            "--purpose", "ml_augmentation", "--privacy", "not_required"]
    assert main(argv) == 2
    assert "holograms" in capsys.readouterr().err


def test_datasets_lists_the_registry(capsys):
    assert main(["datasets"]) == 0
    assert "Simulacrum" in capsys.readouterr().out


def test_datasets_filters_by_data_type(capsys):
    assert main(["datasets", "--data-type", "images"]) == 0
    out = capsys.readouterr().out
    assert "Simulacrum" not in out
    assert "No dataset" in out


def test_search_finds_a_method_by_name(capsys):
    assert main(["search", "synthea"]) == 0
    out = capsys.readouterr().out
    assert "[synthea]" in out
    assert "verified" in out.lower()


def test_search_reports_no_match(capsys):
    assert main(["search", "zzzz"]) == 0
    assert "No catalog entry" in capsys.readouterr().out


def test_find_report_no_longer_leads_with_datasets(capsys):
    argv = ["find", "--domain", "biomedical", "--data-type", "coded_event_sequences",
            "--purpose", "open_release", "--privacy", "required"]
    assert main(argv) == 0
    assert "You may not need to generate anything" not in capsys.readouterr().out


def test_no_subcommand_prints_help(capsys):
    assert main([]) == 2
