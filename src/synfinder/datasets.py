"""Match ready-made synthetic datasets to an intake.

Runs before ranking: if a dataset already exists that fits, training a model
is wasted work.
"""
from __future__ import annotations

from .intake import Intake
from .schema import Dataset


def match_datasets(datasets: list[Dataset], intake: Intake) -> list[Dataset]:
    out: list[Dataset] = []
    for d in datasets:
        if intake.domain not in d.domains and "general" not in d.domains:
            continue
        if intake.data_type not in d.data_types:
            continue
        # An empty purpose list is silence, not a claim of unsuitability.
        if d.purposes and intake.purpose not in d.purposes:
            continue
        out.append(d)
    return out
