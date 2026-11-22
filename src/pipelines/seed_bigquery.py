"""Create reproducible synthetic BigQuery tables for demos. Requires configured GCP access."""
from __future__ import annotations

import argparse
import random
import re
from datetime import UTC, datetime, timedelta


def generate_rows(seed: int = 7, count: int = 500):
    rng = random.Random(seed)
    services = ["checkout-api", "payments-api", "catalog-api", "identity-api"]
    errors = []
    deployments = []
    metrics = []
    now = datetime.now(UTC)
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
    if not re.fullmatch(r"[A-Za-z0-9_]+", args.dataset):
        parser.error("--dataset must be a valid BigQuery dataset identifier")
    if not 1 <= args.count <= 50000:
        parser.error("--count must be from 1 to 50000")
    from google.cloud import bigquery
    client = bigquery.Client(project=args.project)
    schemas = {
        "error_logs": [
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("service", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("severity", "STRING"),
            bigquery.SchemaField("message", "STRING"),
            bigquery.SchemaField("error_code", "STRING"),
        ],
        "recent_deployments": [
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("service", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("version", "STRING"),
            bigquery.SchemaField("environment", "STRING"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("change_summary", "STRING"),
        ],
        "service_metrics": [
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("service", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("request_count", "INT64"),
            bigquery.SchemaField("error_rate", "FLOAT64"),
            bigquery.SchemaField("p95_latency_ms", "INT64"),
        ],
    }
    for name, rows in generate_rows(count=args.count).items():
        table_id = f"{args.project}.{args.dataset}.{name}"
        client.create_table(bigquery.Table(table_id, schema=schemas[name]), exists_ok=True)
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            raise RuntimeError(f"Insert failed for {table_id}: {errors[:3]}")
        print(f"Inserted {len(rows)} rows into {table_id}")


if __name__ == "__main__":
    main()
