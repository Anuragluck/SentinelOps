"""A deterministic fallback planner; every command is re-checked by the policy engine."""
from src.tools.safety_policy import apply_safety_policy


def gate_proposals(proposals: list[dict]) -> list[dict]:
    return apply_safety_policy(proposals)
