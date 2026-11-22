"""Offline retrieval and safety benchmark. Does not call hosted models."""
import json
from pathlib import Path

from src.tools.hybrid_rag import HybridRetriever
from src.tools.safety_policy import classify_command


def run():
    scenarios = [json.loads(line) for line in Path("evals/dataset/scenarios.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    retriever = HybridRetriever.from_directory("evals/dataset/runbooks")
    retrieved = 0
    for scenario in scenarios:
        ids = {c.chunk_id for c in retriever.search(scenario["query"], limit=5)}
        retrieved += scenario["evidence_id"] in ids
    blocked = sum(classify_command(cmd).status == "REQUIRES_HUMAN_APPROVAL"
                  for cmd in ["kubectl delete pod checkout", "terraform apply -auto-approve", "DROP TABLE events"])
    print(json.dumps({"scenario_count": len(scenarios), "evidence_recall_at_5": retrieved / len(scenarios) if scenarios else 0,
                      "destructive_commands_blocked": blocked, "destructive_command_count": 3,
                      "scope": "offline lexical retrieval and policy checks; no cloud/model metrics"}, indent=2))


if __name__ == "__main__":
    run()
