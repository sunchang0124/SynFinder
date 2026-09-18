from synfinder import llm
from synfinder.explain import Explanation
from synfinder.intake import Intake
from tests.factories import make_method

EXPL = Explanation(headline="M — 90% fit", why_fits=["supports your purpose"],
                   weakness=None, caveats=["A caveat."], evaluation=[])
INTAKE = Intake(domain="biomedical", data_type="tabular_cross_sectional",
                purpose="ml_augmentation", privacy="none")


def no_credentials(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)


def test_unavailable_without_credentials(monkeypatch):
    no_credentials(monkeypatch)
    assert llm.available() is False


def test_narrate_returns_none_without_credentials(monkeypatch):
    no_credentials(monkeypatch)
    assert llm.narrate(EXPL, make_method(), INTAKE) is None


def test_narrate_returns_none_when_the_call_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(llm, "_call", boom)
    assert llm.narrate(EXPL, make_method(), INTAKE) is None


def test_prompt_carries_only_catalog_facts():
    prompt = llm.build_prompt(EXPL, make_method(), INTAKE)
    assert "A caveat." in prompt
    assert "do not introduce" in prompt.lower()
