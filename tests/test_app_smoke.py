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
        "privacy": "formal_dp_required",
        "expertise": None,
        "preserves": [],
    })
    assert intake.privacy == "formal_dp_required"
    assert intake.expertise is None
    assert intake.answered("expertise") is False
