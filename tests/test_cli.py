from synfinder.cli import main


def test_cli_prints_a_shortlist(capsys):
    code = main([
        "--domain", "biomedical",
        "--data-type", "tabular_cross_sectional",
        "--purpose", "ml_augmentation",
        "--privacy", "none",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "Recommended methods" in out


def test_cli_writes_a_report_file(tmp_path):
    target = tmp_path / "report.md"
    code = main([
        "--domain", "biomedical",
        "--data-type", "tabular_cross_sectional",
        "--purpose", "ml_augmentation",
        "--privacy", "none",
        "--out", str(target),
    ])
    assert code == 0
    assert "Recommended methods" in target.read_text()


def test_cli_rejects_a_data_type_outside_the_taxonomy(capsys):
    code = main([
        "--domain", "biomedical",
        "--data-type", "holograms",
        "--purpose", "ml_augmentation",
        "--privacy", "none",
    ])
    assert code == 2
    assert "holograms" in capsys.readouterr().err
