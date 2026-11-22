"""Citation verifier. Citations must resolve to evidence IDs supplied to the critic."""


def verify(citations: list[dict], evidence_ids: set[str]) -> tuple[bool, list[str]]:
    missing = [c.get("evidence_id", "") for c in citations if c.get("evidence_id") not in evidence_ids]
    return not missing, missing
