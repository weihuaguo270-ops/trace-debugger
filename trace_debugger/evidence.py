"""Evidence chain helpers — structured, deterministic failure signals."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class EvidenceItem:
    """One auditable signal backing a failure label."""

    rule_id: str
    signal: str
    excerpt: str = ""
    step_index: Optional[int] = None
    path_index: Optional[int] = None
    failure_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop nulls for compact JSON handoff
        return {k: v for k, v in d.items() if v is not None and v != ""}


def evidence(
    rule_id: str,
    signal: str,
    *,
    excerpt: str = "",
    step_index: Optional[int] = None,
    path_index: Optional[int] = None,
    failure_type: str = "",
) -> EvidenceItem:
    """Build a truncated evidence item for exports and findings."""
    return EvidenceItem(
        rule_id=rule_id,
        signal=signal,
        excerpt=(excerpt or "")[:240],
        step_index=step_index,
        path_index=path_index,
        failure_type=failure_type,
    )


def evidence_chain_from_analysis(analysis: Any) -> list[dict[str, Any]]:
    """Flatten path/step evidence for failure-gate export."""
    chain: list[dict[str, Any]] = []
    for pa in getattr(analysis, "paths", []) or []:
        for sa in pa.step_analyses:
            items = getattr(sa, "evidence", None) or []
            if items:
                for item in items:
                    d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    d.setdefault("path_index", pa.path_index)
                    d.setdefault("step_index", sa.step_index)
                    if sa.failure_type:
                        d.setdefault("failure_type", sa.failure_type)
                    chain.append(d)
            elif not sa.success and sa.failure_type:
                chain.append(
                    evidence(
                        f"heuristic.{sa.failure_type}",
                        sa.failure_detail or sa.failure_type,
                        excerpt=sa.failure_detail or "",
                        step_index=sa.step_index,
                        path_index=pa.path_index,
                        failure_type=sa.failure_type,
                    ).to_dict()
                )
    return chain
