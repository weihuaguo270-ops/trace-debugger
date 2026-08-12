from pathlib import Path

from trace_debugger.record import resolve_record_path


def test_data_directory_override(tmp_path, monkeypatch):
    monkeypatch.delenv("TDEBUG_RECORD_PATH", raising=False)
    monkeypatch.setenv("TDEBUG_DATA_DIR", str(tmp_path))

    assert Path(resolve_record_path()) == tmp_path / "failures.jsonl"


def test_explicit_record_path_wins(tmp_path, monkeypatch):
    explicit = tmp_path / "explicit.jsonl"
    monkeypatch.setenv("TDEBUG_DATA_DIR", str(tmp_path / "default"))

    assert resolve_record_path(str(explicit)) == str(explicit)
