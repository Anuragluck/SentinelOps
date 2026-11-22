"""Deterministic command gate. LLM output never authorizes execution."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Decision:
    status: str
    reasons: tuple[str, ...]


# Conservative rules: anything not explicitly recognized as read-only needs a human.
_DESTRUCTIVE = re.compile(
    r"\b(drop|delete|truncate|destroy|purge|terminate|remove|scale\s+down|"
    r"restart|reboot|kill|rollback|apply|taint|replace)\b|--force|\brm\s+-rf\b",
    re.IGNORECASE,
)
_READ_ONLY_PREFIXES = (
    "kubectl get", "kubectl describe", "kubectl logs", "kubectl top",
    "gcloud logging read", "gcloud monitoring", "gcloud run services describe",
    "terraform plan", "SELECT ", "bq query --use_legacy_sql=false",
    "curl -i", "curl -s", "journalctl", "grep ", "cat ", "tail ",
)


def classify_command(command: str) -> Decision:
    normalized = command.strip()
    if not normalized:
        return Decision("REQUIRES_HUMAN_APPROVAL", ("Empty command is not allowed",))
    if any(token in normalized for token in (";", "&&", "||", "|", "`", "$(", "\n")):
        return Decision("REQUIRES_HUMAN_APPROVAL", ("Shell chaining or substitution requires review",))
    if _DESTRUCTIVE.search(normalized):
        return Decision("REQUIRES_HUMAN_APPROVAL", ("Potentially destructive operation",))
    if normalized.lower().startswith(tuple(p.lower() for p in _READ_ONLY_PREFIXES)):
        return Decision("ALLOW_READ_ONLY", ())
    return Decision("REQUIRES_HUMAN_APPROVAL", ("Command is not on the read-only allowlist",))


def apply_safety_policy(commands: list[dict]) -> list[dict]:
    results = []
    for item in commands:
        decision = classify_command(str(item.get("command", "")))
        results.append({**item, "decision": decision.status, "reasons": list(decision.reasons)})
    return results
