"""Shared test factory so every ranking test builds methods the same way."""
from synfinder.schema import Method, Scale, Maturity, Governance, Links


def make_method(**over) -> Method:
    base = dict(
        id="m", name="M", family="gan",
        domains=["general"], data_types=["tabular_cross_sectional"],
        variable_types=["continuous", "categorical"],
        formal_dp=False, dp_mechanism=None,
        compute="cpu_fine", license="MIT",
        purposes=["ml_augmentation"], preserves=["marginals"],
        scale=Scale(min_rows=None, max_rows=None, max_cols=None),
        expertise="medium",
        maturity=Maturity(maintained=True, last_release="2025-01",
                          implementation_quality="production_ready"),
        governance=Governance(),
        caveats=["A caveat."], evaluation=[], links=Links(),
        related_datasets=[], is_framework=False,
    )
    base.update(over)
    return Method(**base)
