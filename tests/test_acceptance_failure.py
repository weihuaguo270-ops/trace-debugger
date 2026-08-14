from trace_debugger.analyzer import Analyzer, FailureType
from trace_debugger.reader import parse


def test_delivery_acceptance_failure_is_not_reported_as_pass():
    trajectory = parse({
        "session_id": "delivery-failed-1",
        "query": "change a policy and run tests",
        "model": "operator-plan-executor-v1",
        "steps": [
            {
                "step": 1,
                "thought": "Run the business acceptance suite.",
                "action": {
                    "name": "run_acceptance_tests",
                    "arguments": '{"command":["python","-m","pytest"]}',
                },
                "observation": "failed",
            }
        ],
        "final_answer": "delivery status: test_failed",
    })

    analysis = Analyzer().analyze(trajectory)

    assert analysis.needs_fix is True
    assert FailureType.ACCEPTANCE_FAILED in analysis.paths[0].failure_types
    assert analysis.paths[0].success is False
