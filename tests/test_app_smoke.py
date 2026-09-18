import importlib.util
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def load_app():
    spec = importlib.util.spec_from_file_location("streamlit_app", APP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_intake_maps_answers_to_the_model():
    app = load_app()
    intake = app.build_intake({
        "domain": "biomedical",
        "data_type": "tabular_cross_sectional",
        "purpose": "open_release",
        "privacy": "required",
        "expertise": None,
        "preserves": [],
    })
    assert intake.privacy == "required"
    assert intake.expertise is None
    assert intake.answered("expertise") is False


def test_dataset_rows_flattens_for_the_browse_table():
    from synfinder.schema import Dataset
    app = load_app()
    d = Dataset(id="d1", name="Ready Set", domains=["biomedical"],
                data_types=["tabular_cross_sectional"], purposes=["education"],
                n_records="1,000 patients", access_conditions="Free download",
                license="CC0-1.0", realism_caveats=["Not a real population."])
    rows = app.dataset_rows([d])
    assert rows[0]["Name"] == "Ready Set"
    assert rows[0]["Records"] == "1,000 patients"
    assert "biomedical" in rows[0]["Domains"]
