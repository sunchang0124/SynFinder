"""Hard filters and weighted scoring."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .intake import Intake
from .schema import Method

OPEN_LICENSES = {
    "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0",
    "GPL-3.0", "GPL-2.0", "LGPL-3.0", "MPL-2.0", "CC-BY-4.0", "CC0-1.0",
}


@dataclass
class Exclusion:
    method_id: str
    method_name: str
    reason: str


def _exclusion_reason(method: Method, intake: Intake) -> str | None:
    """The first reason this method cannot serve this intake, or None."""
    if method.is_framework:
        return "is a framework or toolkit, not a generation method in itself"

    if intake.domain not in method.domains and "general" not in method.domains:
        return f"is not established for the {intake.domain} domain"

    if intake.data_type not in method.data_types:
        return f"cannot handle {intake.data_type} data"

    if intake.privacy == "formal_dp_required" and not method.formal_dp:
        return "provides no formal differential privacy guarantee"

    if intake.compute == "cpu_fine" and method.compute == "gpu_required":
        return "requires a GPU, which you said is not available"

    missing = set(intake.variable_types) - set(method.variable_types)
    if "free_text" in missing:
        return "cannot generate free text fields"
    if missing:
        return f"cannot generate {', '.join(sorted(missing))} variables"

    if intake.require_open_license and method.license not in OPEN_LICENSES:
        return f"license {method.license} is not an open licence"

    return None


def hard_filter(
    methods: list[Method], intake: Intake
) -> tuple[list[Method], list[Exclusion]]:
    kept: list[Method] = []
    dropped: list[Exclusion] = []
    for method in methods:
        reason = _exclusion_reason(method, intake)
        if reason is None:
            kept.append(method)
        else:
            dropped.append(Exclusion(method.id, method.name, reason))
    return kept, dropped
