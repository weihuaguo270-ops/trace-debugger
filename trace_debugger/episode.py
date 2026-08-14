"""Import EvaluationEpisode v1 envelopes without depending on an Agent SDK."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from .validate import validate_trajectory_dict


EPISODE_SCHEMA_VERSION = "evaluation-episode/v1"


@dataclass(frozen=True)
class ImportedEpisode:
    """从跨框架 EvaluationEpisode 提取的只读调试证据。"""

    episode_id: str
    framework: str
    agent_version: str
    split: str
    trajectory: dict[str, Any]
    expected_state: dict[str, Any]
    final_state: dict[str, Any]
    state_verification: dict[str, Any]


def import_evaluation_episode(payload: Mapping[str, Any]) -> ImportedEpisode:
    """Extract and validate Format B evidence from an EvaluationEpisode envelope."""
    if payload.get("schema_version") != EPISODE_SCHEMA_VERSION:
        raise ValueError(f"expected schema_version={EPISODE_SCHEMA_VERSION}")
    trajectory = copy.deepcopy(payload.get("trajectory"))
    if not isinstance(trajectory, dict):
        raise ValueError("episode.trajectory must be an object")
    errors = validate_trajectory_dict(trajectory)
    if errors:
        raise ValueError("; ".join(errors))

    episode_id = str(payload.get("episode_id") or "")
    if not episode_id:
        raise ValueError("episode_id is required")
    metadata = dict(trajectory.get("metadata") or {})
    metadata.update(
        {
            "episode_id": episode_id,
            "framework": str(payload.get("framework") or "format_b"),
            "agent_version": str(payload.get("agent_version") or ""),
            "split": str(payload.get("split") or "dev"),
            "state_verification": copy.deepcopy(payload.get("state_verification") or {}),
        }
    )
    trajectory["metadata"] = metadata
    trajectory.setdefault("task_episode_id", episode_id)
    trajectory.setdefault(
        "acceptance_criteria", list(payload.get("acceptance_criteria") or [])
    )
    return ImportedEpisode(
        episode_id=episode_id,
        framework=metadata["framework"],
        agent_version=metadata["agent_version"],
        split=metadata["split"],
        trajectory=trajectory,
        expected_state=dict(payload.get("expected_state") or {}),
        final_state=dict(payload.get("final_state") or {}),
        state_verification=dict(payload.get("state_verification") or {}),
    )
