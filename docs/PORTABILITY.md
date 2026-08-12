# Portability

Mutable failure logs default to the platform user-data directory rather than the repository.
Set `TDEBUG_DATA_DIR` for containers or restricted runners, or `TDEBUG_RECORD_PATH` for one
explicit JSONL file. The explicit path has highest priority.

EvaluationEpisode imports operate on JSON and do not require the SDK that produced the trace.
