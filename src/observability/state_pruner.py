"""Bound tool output before it is copied into agent state."""
from collections.abc import Mapping
import json


def prune(value, max_chars: int = 6000):
    if max_chars < 128:
        raise ValueError("max_chars must be at least 128")
    serialized = json.dumps(value, default=str, ensure_ascii=False)
    if len(serialized) <= max_chars:
        return value
    return {"truncated": True, "original_chars": len(serialized),
            "preview": serialized[: max_chars - 64] + "…"}


def prune_state(state: Mapping, max_chars: int = 6000):
    return {key: prune(value, max_chars) for key, value in state.items()}
