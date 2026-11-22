"""Create reproducible synthetic BigQuery tables for demos. Requires configured GCP access."""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone


def generate_rows(seed: int = 7, count: int = 500):
    rng = random.Random(seed)
    services = ["checkout-api", "payments-api", "catalog-api", "identity-api"]
    errors = []
    deployments = []
    metrics = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        service = rng.choice(services)
        stamp = now - timedelta(minutes=rng.randint(0, 10080))
        errors.append({"timestamp": stamp.isoformat(), "service": service,
                       "severity": rng.choice(["ERROR", "CRITICAL"]),
                       "message": rng.choice(["connection pool exhausted", "upstream timeout", "invalid token"]),
                       "error_code": rng.choice(["ERR_POOL_EXHAUSTED", "HTTP_504_GATEWAY", "AUTH_401"])})
        deployments.append({"timestamp": stamp.isoformat(), "service": service,
                            "version": f"v{1 + i // 100}.{i % 10}", "environment": "production",
                            "status": rng.choice(["SUCCEEDED", "SUCCEEDED", "FAILED"]),
                            "change_summary": "Synthetic seed deployment"})
        metrics.append({"timestamp": stamp.isoformat(), "service": service,
                        "request_count": rng.randint(100, 10000), "error_rate": round(rng.random() * .2, 4),
                        "p95_latency_ms": rng.randint(30, 3000)})
    return {"error_logs": errors, "recent_deployments": deployments, "service_metrics": metrics}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="sentinelops")
    parser.add_argument("--count", type=int, default=500)
    args = parser.parse_args()
    from google.cloud import bigquery
    client = bigquery.Client(project=args.project)
    for name, rows in generate_rows(count=args.count).items():
        table_id = f"{args.project}.{args.dataset}.{name}"
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            raise RuntimeError(f"Insert failed for {table_id}: {errors[:3]}")
        print(f"Inserted {len(rows)} rows into {table_id}")


if __name__ == "__main__":
    main()
