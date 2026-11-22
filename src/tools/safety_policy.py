"""Fail-closed deterministic command gate. LLM output never authorizes execution."""
import re
import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    status: str
    reasons: tuple[str, ...]


# Reject shell operators, substitutions, escaping, globbing, variable expansion, and line breaks.
_META = re.compile(r"[;|&<>`\\*?{}\[\]$^%!()\n\r]")
_DESTRUCTIVE = re.compile(
    r"\b(drop|delete|truncate|destroy|purge|terminate|remove|restart|reboot|"
    r"kill|rollback|apply|taint|replace|scale|drain|cordon|patch|edit|exec|run|"
    r"create|insert|update|merge|alter|call|export|load)\b|--force|\brm\s+-rf\b",
    re.IGNORECASE,
)
_SQL_MUTATION = re.compile(
    r"\b(create|insert|update|delete|merge|drop|alter|truncate|call|export|load)\b", re.IGNORECASE
)


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return []


def _is_read_only(tokens: list[str]) -> bool:
    if not tokens:
        return False
    executable = tokens[0].lower()
    args = [arg.lower() for arg in tokens[1:]]
    if executable == "kubectl":
        # Only explicit inspection verbs; do not allow plugins, exec, or arbitrary subcommands.
        if not args or args[0] not in {"get", "describe", "logs", "top"}:
            return False
        return not any(arg in {"--raw", "--as", "--as-group"} for arg in args)
    if executable == "gcloud":
        allowed = (("logging", "read"), ("monitoring",), ("run", "services", "describe"))
        return any(tuple(args[:len(prefix)]) == prefix for prefix in allowed)
    if executable == "bq":
        if not args or args[0] != "query" or "--use_legacy_sql=false" not in args:
            return False
        query = " ".join(arg for arg in args[1:] if not arg.startswith("--")).strip()
        return query.lower().startswith(("select ", "with ")) and not _SQL_MUTATION.search(query)
    if executable == "curl":
        # Diagnostics may use GET/HEAD only and cannot write response data to disk.
        denied = {"-x", "--request", "-d", "--data", "-f", "--form", "-t", "--upload-file",
                  "-o", "--output", "--remote-name"}
        if any(arg in denied for arg in args):
            return False
        return any(arg in {"-i", "-s", "-sS", "--head"} for arg in args)
    return executable in {"journalctl", "grep", "cat", "tail", "head"}


def classify_command(command: str) -> Decision:
    normalized = command.strip()
    if not normalized:
        return Decision("REQUIRES_HUMAN_APPROVAL", ("Empty command is not allowed",))
    if _META.search(normalized):
        return Decision("REQUIRES_HUMAN_APPROVAL", ("Shell operators, expansion, or globbing require review",))
    if _DESTRUCTIVE.search(normalized):
        return Decision("REQUIRES_HUMAN_APPROVAL", ("Potentially destructive operation",))
    if _is_read_only(_tokens(normalized)):
        return Decision("ALLOW_READ_ONLY", ())
    return Decision("REQUIRES_HUMAN_APPROVAL", ("Command is not on the read-only allowlist",))


def apply_safety_policy(commands: list[dict]) -> list[dict]:
    decisions = []
    for item in commands:
        decision = classify_command(str(item.get("command", "")))
        decisions.append({**item, "decision": decision.status, "reasons": list(decision.reasons)})
    return decisions
