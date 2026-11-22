"""Read-only telemetry queries; all user values are passed as BigQuery parameters."""
import os
import re
from datetime import UTC, datetime, timedelta


def _client():
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise RuntimeError("Install sentinelops[cloud] to query BigQuery") from exc
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured")
    return bigquery, bigquery.Client(project=project)


def recent_errors(service: str, since_minutes: int = 60, limit: int = 100) -> list[dict]:
    if not 1 <= since_minutes <= 10080 or not 1 <= limit <= 500:
        raise ValueError("since_minutes or limit outside allowed range")
    bq, client = _client()
    dataset = os.getenv("BIGQUERY_DATASET", "sentinelops")
    if not re.fullmatch(r"[A-Za-z0-9_]+", dataset):
        raise ValueError("BIGQUERY_DATASET must be a valid BigQuery dataset identifier")
    sql = f"""SELECT timestamp, service, severity, message, error_code
FROM `{client.project}.{dataset}.error_logs`
WHERE service = @service AND timestamp >= @cutoff
ORDER BY timestamp DESC LIMIT @limit"""
    config = bq.QueryJobConfig(query_parameters=[
        bq.ScalarQueryParameter("service", "STRING", service),
        bq.ScalarQueryParameter("cutoff", "TIMESTAMP", datetime.now(UTC) - timedelta(minutes=since_minutes)),
        bq.ScalarQueryParameter("limit", "INT64", limit),
    ])
    return [dict(row) for row in client.query(sql, job_config=config).result()]


def recent_deployments(service: str, limit: int = 20) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("limit outside allowed range")
    bq, client = _client()
    dataset = os.getenv("BIGQUERY_DATASET", "sentinelops")
    if not re.fullmatch(r"[A-Za-z0-9_]+", dataset):
        raise ValueError("BIGQUERY_DATASET must be a valid BigQuery dataset identifier")
    sql = f"""SELECT timestamp, service, version, environment, status, change_summary
FROM `{client.project}.{dataset}.recent_deployments`
WHERE service = @service ORDER BY timestamp DESC LIMIT @limit"""
    config = bq.QueryJobConfig(query_parameters=[
        bq.ScalarQueryParameter("service", "STRING", service),
        bq.ScalarQueryParameter("limit", "INT64", limit),
    ])
    return [dict(row) for row in client.query(sql, job_config=config).result()]


def recent_metrics(service: str, limit: int = 60) -> list[dict]:
    if not 1 <= limit <= 500:
        raise ValueError("limit outside allowed range")
    bq, client = _client()
    dataset = os.getenv("BIGQUERY_DATASET", "sentinelops")
    if not re.fullmatch(r"[A-Za-z0-9_]+", dataset):
        raise ValueError("BIGQUERY_DATASET must be a valid BigQuery dataset identifier")
    sql = f"""SELECT timestamp, service, request_count, error_rate, p95_latency_ms
FROM `{client.project}.{dataset}.service_metrics`
WHERE service = @service ORDER BY timestamp DESC LIMIT @limit"""
    config = bq.QueryJobConfig(query_parameters=[
        bq.ScalarQueryParameter("service", "STRING", service),
        bq.ScalarQueryParameter("limit", "INT64", limit),
    ])
    return [dict(row) for row in client.query(sql, job_config=config).result()]
