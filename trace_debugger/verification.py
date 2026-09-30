"""verification — machine-checkable binding between a finding and its regression lock.

A finding claims "failure type X regressed". That claim is only actionable if a
fixture or test can *refute* the fix. This module derives that binding from the
fixture manifests (never from hardcoded case ids) and validates it, so a ``hold``
finding that nothing can verify fails the build instead of passing as prose.

Coverage semantics per failure type:
  - ``must_detect``     — golden/held-out cases that must still fire this type
  - ``must_stay_clean`` — true-positive cases that must NOT fire this type

A type with an empty ``must_detect`` has **no regression lock**: nothing proves
the detector still works, so its ref is marked ``verified=False``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

# Test entry points that lock the taxonomy; a ref is only resolvable if they exist.
LOCK_TESTS: tuple[str, ...] = (
    "tests/test_failure_golden.py",
    "tests/test_failure_fp_and_gate.py",
)
LOCK_COMMAND = "pytest tests/test_failure_golden.py tests/test_failure_fp_and_gate.py -q"


def _all_cases() -> list[Any]:
    """Every case from the repo's golden + false-positive manifests.

    Unreadable manifests degrade to an empty list so validation reports the
    problem instead of raising.
    """
    from .golden import DEFAULT_FP_DIR, load_manifest

    cases: list[Any] = []
    for path in (None, str(DEFAULT_FP_DIR / "manifest.json")):
        try:
            manifest = load_manifest() if path is None else load_manifest(path)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        cases.extend(manifest.cases)
    return cases


def known_case_ids() -> set[str]:
    """Ids available as regression locks."""
    return {case.id for case in _all_cases()}


def fixture_coverage(failure_type: str) -> dict[str, list[str]]:
    """Case ids that lock ``failure_type``, split by must-fire / must-not-fire."""
    must_detect: list[str] = []
    must_stay_clean: list[str] = []
    for case in _all_cases():
        if failure_type in list(getattr(case, "expected_failures", None) or []):
            must_detect.append(case.id)
        if failure_type in list(getattr(case, "must_not_detect", None) or []):
            must_stay_clean.append(case.id)
    return {"must_detect": sorted(must_detect), "must_stay_clean": sorted(must_stay_clean)}


def build_verification_ref(failure_type: Optional[str] = None) -> dict[str, Any]:
    """Build the ref that says how a finding's fix would be verified.

    ``failure_type=None`` builds a suite-scope ref (used by session-level
    findings such as rule B fail-rate, which are not type specific).
    """
    coverage = (
        fixture_coverage(failure_type)
        if failure_type
        else {"must_detect": [], "must_stay_clean": []}
    )
    ref: dict[str, Any] = {
        "scope": "failure_type" if failure_type else "suite",
        "fixtures": coverage,
        "tests": list(LOCK_TESTS),
        "command": LOCK_COMMAND,
        # A type-scoped ref is verified only when a case proves detection.
        "verified": bool(coverage["must_detect"]) if failure_type else True,
    }
    if failure_type:
        ref["failure_type"] = failure_type
    return ref


def validate_findings_report(
    report: dict[str, Any],
    *,
    project_root: Optional[str] = None,
) -> list[str]:
    """Return human-readable problems; empty list means every finding is verifiable.

    Checks, per finding:
      - ``verification_ref`` present
      - every referenced fixture id exists in the manifests
      - a type-scoped ref has at least one must-fire case (else: no regression lock)
      - ``verified`` is true
      - referenced test files exist under ``project_root`` (when given)
    """
    cases = _all_cases()
    if not cases:
        return ["fixture manifests unreadable — cannot verify any finding"]

    known = {case.id for case in cases}
    problems: list[str] = []

    for finding in report.get("findings") or []:
        fid = finding.get("id") or "<finding without id>"
        ref = finding.get("verification_ref")
        if not ref:
            problems.append(f"{fid}: missing verification_ref — no regression lock")
            continue

        local: list[str] = []
        fixtures = ref.get("fixtures") or {}
        referenced = list(fixtures.get("must_detect") or []) + list(
            fixtures.get("must_stay_clean") or []
        )
        for case_id in referenced:
            if case_id not in known:
                local.append(f"unknown fixture id {case_id!r}")

        if ref.get("scope") == "failure_type":
            ftype = ref.get("failure_type") or finding.get("failure_type") or "?"
            if not fixtures.get("must_detect"):
                local.append(
                    f"no fixture proves failure type {ftype!r} is detected "
                    "— add a golden case before calling this verified"
                )

        # Only fall back to the generic reason when nothing specific fired.
        if not ref.get("verified") and not local:
            local.append("verification_ref marked unverified")

        if project_root:
            for rel in ref.get("tests") or []:
                if not (Path(project_root) / rel).exists():
                    local.append(f"missing test file {rel}")

        problems.extend(f"{fid}: {item}" for item in local)

    return problems
