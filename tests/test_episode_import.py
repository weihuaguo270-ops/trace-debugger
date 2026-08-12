import pytest

from trace_debugger.episode import import_evaluation_episode
from trace_debugger.reader import parse


def _episode():
    return {
        "schema_version": "evaluation-episode/v1",
        "episode_id": "expense-held-out-1",
        "task": "approve expense claim",
        "framework": "langgraph",
        "agent_version": "agent-v2",
        "split": "held_out",
        "acceptance_criteria": ["claim status is approved"],
        "expected_state": {"claim": {"status": "approved"}},
        "final_state": {"claim": {"status": "approved"}},
        "state_verification": {"passed": True},
        "trajectory": {
            "session_id": "s1",
            "query": "approve expense claim",
            "steps": [
                {
                    "step": 1,
                    "thought": "check claim",
                    "action": {
                        "name": "approve_claim",
                        "arguments": "{\"claim_id\": \"C-1\"}",
                    },
                    "observation": "approved",
                }
            ],
            "final_answer": "approved",
        },
    }


def test_import_episode_preserves_release_dimensions():
    imported = import_evaluation_episode(_episode())
    trajectory = parse(imported.trajectory)
    assert imported.split == "held_out"
    assert trajectory.metadata["framework"] == "langgraph"
    assert trajectory.metadata["agent_version"] == "agent-v2"
    assert trajectory.metadata["state_verification"]["passed"] is True
    assert trajectory.metadata["task_episode_id"] == "expense-held-out-1"


def test_import_episode_rejects_invalid_trajectory():
    payload = _episode()
    payload["trajectory"]["steps"][0].pop("step")
    with pytest.raises(ValueError, match="step"):
        import_evaluation_episode(payload)
