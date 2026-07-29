"""validate 模块测试"""

import json
import tempfile

from trace_debugger.validate import (
    format_validation_report,
    validate_trajectory_dict,
    validate_trajectory_file,
)


def test_validate_ok_fixture():
    errors = validate_trajectory_file("fixtures/failure_golden/tool_error.json")
    assert errors == []


def test_validate_missing_fields():
    errors = validate_trajectory_dict({"session_id": "x"})
    assert any("missing" in e for e in errors)


def test_validate_file_not_found():
    assert validate_trajectory_file("no/such/file.json")[0].startswith("file not found")


def test_validate_report_ok():
    assert "OK" in format_validation_report([])


def test_validate_schema_optional_without_package():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(
            {
                "session_id": "s",
                "query": "q",
                "steps": [{"step": 1, "thought": "t", "observation": ""}],
                "final_answer": "a",
            },
            f,
        )
        path = f.name
    errors = validate_trajectory_file(path, use_schema=True)
    # 未安装 jsonschema 时应提示安装；已安装则应通过
    assert errors == [] or any("jsonschema" in e for e in errors)
