from src.tools.bigquery_tools import recent_deployments, recent_errors, recent_metrics


def investigate(service: str) -> dict:
    return {"errors": recent_errors(service), "deployments": recent_deployments(service),
            "metrics": recent_metrics(service)}
