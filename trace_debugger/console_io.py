"""跨平台控制台输出：重定向到管道/文件时固定 UTF-8，避免旧代码页崩溃。

Windows 上 Python 只有在 stdout 是真正的控制台时才用 UTF-8；一旦被重定向
（CI 日志、`subprocess.run(capture_output=True)`、`> out.txt`），编码回落到
ANSI 代码页（英文版 Windows 是 cp1252）。此时 CLI 里的中文/emoji 会直接抛
``UnicodeEncodeError`` 并让整个命令以 traceback 结束——输出中文的 CLI 不该
因为终端代码页而死。

本模块在 CLI 入口做一次尽力而为的 ``reconfigure``：编码固定 UTF-8（与
``tests/test_fail_on_cli.py`` 用 UTF-8 解码子进程输出一致），错误策略 replace
（即使上游显式指定了编码，也只是降级字符而不是崩溃）。
"""
from __future__ import annotations

import sys
from typing import Optional, TextIO

DEFAULT_ENCODING = "utf-8"
DEFAULT_ERRORS = "replace"


def configure_stdio(
    *,
    encoding: Optional[str] = DEFAULT_ENCODING,
    errors: str = DEFAULT_ERRORS,
) -> None:
    """把 stdout/stderr 切到 UTF-8 + errors=replace（尽力而为，不抛异常）。

    某些流（测试替身、已被关闭或只读包装）没有 ``reconfigure``，此时静默跳过：
    输出降级总好过整个命令失败。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding=encoding, errors=errors)
        except Exception:
            # OSError/ValueError/AttributeError: 流不支持或已关闭
            pass


def safe_print(text: str, *, file: Optional[TextIO] = None) -> None:
    """print 的降级包装：编码失败时按目标编码 replace，绝不抛 UnicodeEncodeError。"""
    stream = file or sys.stdout
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        enc = getattr(stream, "encoding", None) or DEFAULT_ENCODING
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"), file=stream)
