"""Message-list adapters (OpenAI / Anthropic style) → Format B.

Plain dict APIs only — no openai / anthropic SDK dependency.
"""
from __future__ import annotations

from .openai_messages import (
    openai_messages_to_step_events,
    openai_messages_to_trajectory,
)
from .openai_responses import (
    openai_responses_items_to_step_events,
    openai_responses_to_trajectory,
)
from .openai_stream import (
    IncompleteStreamError,
    apply_incomplete_meta,
    chat_stream_to_trajectory,
    coalesce_chat_completion_chunks,
    messages_from_chat_stream,
    normalize_on_incomplete,
)
from .anthropic_messages import (
    anthropic_messages_to_step_events,
    anthropic_messages_to_trajectory,
)

__all__ = [
    "IncompleteStreamError",
    "apply_incomplete_meta",
    "chat_stream_to_trajectory",
    "normalize_on_incomplete",
    "openai_messages_to_step_events",
    "openai_messages_to_trajectory",
    "openai_responses_items_to_step_events",
    "openai_responses_to_trajectory",
    "coalesce_chat_completion_chunks",
    "messages_from_chat_stream",
    "anthropic_messages_to_step_events",
    "anthropic_messages_to_trajectory",
]
