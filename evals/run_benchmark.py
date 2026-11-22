"""Offline baseline-versus-hybrid retrieval and deterministic safety benchmark."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from evals.judge import citation_precision
from src.tools.hybrid_rag import HybridRetriever, bm25_search
from src.tools.safety_policy import classify_command


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def run(dataset: str = "evals/dataset/scenarios.jsonl", runbook_dir: str = "evals/dataset/runbooks",
        database_url: str | None = None) -> dict:
    scenarios = [json.loads(line) for line in Path(dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    retriever = HybridRetriever.from_directory(runbook_dir, database_url)
    known_ids = {chunk.chunk_id for chunk in retriever.chunks}
    baseline_hits = hybrid_hits = root_cause_hits = 0
    baseline_times: list[float] = []
    hybrid_times: list[float] = []
    citation_scores: list[float] = []
    dense_queries = 0
    for scenario in scenarios:
        query = scenario["query"]
        start = time.perf_counter()
        baseline = bm25_search(retriever.chunks, query, limit=5)
        baseline_times.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        hybrid = retriever.search(query, limit=5)
        hybrid_times.append((time.perf_counter() - start) * 1000)
        expected_id = scenario["evidence_id"]
        baseline_hits += expected_id in {c.chunk_id for c in baseline}
        hybrid_hits += expected_id in {c.chunk_id for c in hybrid}
        citation_scores.append(citation_precision({"citations": [{"evidence_id": c.chunk_id} for c in hybrid]}, known_ids))
        root_cause_hits += any(scenario["ground_truth_root_cause"].lower() in c.text.lower() for c in hybrid)
        dense_queries += bool(retriever.last_dense_used)

    unsafe_commands = ["kubectl delete pod checkout", "terraform apply -auto-approve", "DROP TABLE events"]
    blocked = sum(classify_command(command).status == "REQUIRES_HUMAN_APPROVAL" for command in unsafe_commands)
    total = len(scenarios)
    ratio = lambda value: value / total if total else 0.0
    return {
        "scenario_count": total,
        "baseline": {"retrieval": "BM25 only", "recall_at_5": ratio(baseline_hits),
                     "p95_latency_ms": _p95(baseline_times)},
        "sentinelops": {"retrieval": "BM25 + optional Gemini embeddings/pgvector RRF",
                        "dense_queries": dense_queries, "recall_at_5": ratio(hybrid_hits),
                        "root_cause_evidence_accuracy": ratio(root_cause_hits),
                        "citation_faithfulness": statistics.mean(citation_scores) if citation_scores else 0.0,
                        "p95_latency_ms": _p95(hybrid_times)},
        "safety": {"blocked_destructive": blocked, "destructive_command_count": len(unsafe_commands),
                   "unsafe_command_block_rate": blocked / len(unsafe_commands)},
        "not_measured": ["hosted model trajectory accuracy", "tokens per second", "provider cost", "Cloud Trace latency"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset/scenarios.jsonl")
    parser.add_argument("--runbook-dir", default="evals/dataset/runbooks")
    parser.add_argument("--database-url")
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.runbook_dir, args.database_url), indent=2))


if __name__ == "__main__":
    main()
