"""Example entrypoints for OpenAI / Anthropic message adapters.

Core logic lives in ``trace_debugger.adapters`` (no SDK dependency).
"""
from __future__ import annotations

from trace_debugger.adapters.openai_messages import (
    openai_messages_to_step_events,
    openai_messages_to_trajectory,
)

__all__ = [
    "openai_messages_to_step_events",
    "openai_messages_to_trajectory",
]
