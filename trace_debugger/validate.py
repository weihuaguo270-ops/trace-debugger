"""validate — 轨迹 Format B 校验（轻量 + 可选 jsonschema）"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "agent_trajectory.schema.json"

_REQUIRED = ("session_id", "query", "steps", "final_answer")


def validate_trajectory_dict(
    data: dict,
    *,
    use_schema: bool = False,
    schema_path: Optional[Path] = None,
) -> list[str]:
    """校验轨迹 dict，返回错误列表（空 = 通过）。"""
    errors: list[str] = []
    for key in _REQUIRED:
        if key not in data:
            errors.append(f"missing required field: {key}")

    steps = data.get("steps")
    if steps is not None:
        if not isinstance(steps, list):
            errors.append("steps must be a list")
        else:
            for i, raw in enumerate(steps):
                if not isinstance(raw, dict):
                    errors.append(f"steps[{i}] must be an object")
                    continue
                step_num = raw.get("step")
                if step_num is None:
                    errors.append(f"steps[{i}] missing 1-based step number")
                elif not isinstance(step_num, int) or step_num < 1:
                    errors.append(f"steps[{i}].step must be integer >= 1")

    if use_schema and not errors:
        errors.extend(_jsonschema_validate(data, schema_path=schema_path))
    return errors


def validate_trajectory_file(
    path: str,
    *,
    use_schema: bool = False,
    schema_path: Optional[Path] = None,
) -> list[str]:
    """加载并校验一个轨迹文件，读取或格式错误均作为消息返回。"""
    p = Path(path)
    if not p.is_file():
        return [f"file not found: {path}"]
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]
    if not isinstance(data, dict):
        return ["trajectory root must be a JSON object"]
    return validate_trajectory_dict(data, use_schema=use_schema, schema_path=schema_path)


def format_validation_report(errors: list[str], *, path: str = "") -> str:
    """将校验错误格式化为稳定的终端报告。"""
    if not errors:
        prefix = f"{path}: " if path else ""
        return f"{prefix}OK — Format B validation passed"
    lines = [f"Validation failed ({len(errors)} error(s)):"]
    if path:
        lines.insert(0, f"File: {path}")
    lines.extend(f"  - {e}" for e in errors)
    return "\n".join(lines)


def _jsonschema_validate(data: dict, *, schema_path: Optional[Path] = None) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return [
            "jsonschema not installed; use: pip install 'trace-debugger[schema]'"
        ]

    sp = schema_path or SCHEMA_PATH
    if not sp.is_file():
        return [f"schema file not found: {sp}"]
    with open(sp, encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in sorted(validator.iter_errors(data), key=lambda x: x.path)]
