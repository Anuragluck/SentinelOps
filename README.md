# SentinelOps

SentinelOps is an evidence-first cloud incident triage platform. It accepts an alert, searches runbooks with BM25 and optional Gemini embeddings/pgvector RRF, investigates BigQuery telemetry, creates a cited report with the optional Google ADK workflow, and places every proposed command behind a deterministic safety policy. Cloud integrations require credentials and configuration.

> **Deployment status:** this repository is a deployable project scaffold, not a claim that a live GCP service, benchmark, trace, or production rollout already exists. The out-of-box triage path is local and clearly reports when telemetry/model integrations are unavailable.

## Start locally

Requirements: Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
$env:API_KEY = "local-dev-key"
uvicorn src.api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Example request:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/triage `
  -Method Post -Headers @{"X-API-Key"="local-dev-key"} `
  -ContentType "application/json" `
  -Body '{"service":"checkout-api","summary":"503 spike and ERR_POOL_EXHAUSTED","severity":"SEV2"}'
```

Health endpoint: `GET /health`. Set `API_KEY` for API-key authentication; requests without the key are rejected when it is configured, and production mode refuses to run the triage endpoint without one. In a deployed environment, store a strong secret in Secret Manager and never commit it.

## Enable the Google ADK workflow

Install cloud dependencies and choose the ADK backend:

```powershell
python -m pip install -e ".[cloud,dev]"
$env:AGENT_BACKEND = "adk"
$env:GOOGLE_GENAI_USE_ENTERPRISE = "true"
$env:GOOGLE_CLOUD_PROJECT = "your-project-id"
$env:GOOGLE_CLOUD_LOCATION = "us-central1"
```

Authenticate locally with Application Default Credentials, or set `GEMINI_API_KEY` / `GOOGLE_API_KEY` for a supported Gemini API setup. The package maps `GEMINI_API_KEY` to the ADK's `GOOGLE_API_KEY` when needed. ADK runs a triage supervisor, parallel runbook and telemetry investigators, and a planner/critic loop capped at two iterations. The citation verifier and command firewall run in Python after model output. By default, ADK sessions are in memory; set `SESSION_SERVICE_URI` to an async SQLAlchemy PostgreSQL URI (for example `postgresql+asyncpg://...`) for durable sessions. Cloud Run uses ADK by default in the Terraform config and needs a populated runbook index and valid BigQuery tables.

## Architecture

```mermaid
flowchart TD
  A[Alert JSON] --> B[FastAPI + Pydantic validation]
  B --> C[Bounded triage workflow]
  C --> D[Runbook retrieval: lexical + optional pgvector RRF]
  C --> E[Parameterized read-only BigQuery tools]
  D --> F[Evidence citations]
  E --> F
  F --> G[Incident report]
  G --> H[Deterministic command safety gate]
  H --> I[JSON response + trace metadata]
```

## Safety and evidence

- The default local path does not invoke an LLM. When GCP project access and telemetry tables are configured, it can query BigQuery; otherwise it reports the missing evidence. Set `AGENT_BACKEND=adk` to use the multi-agent workflow.
- Proposed commands are suggestions only; SentinelOps never executes them. The Python allowlist admits a narrow set of diagnostics. Destructive, chained, and unknown commands require human approval.
- BigQuery service values use query parameters; only the project and dataset identifiers are interpolated from trusted deployment configuration. Use a read-only service account and dataset-level IAM.
- Citation IDs identify source file chunks. The critic helper can verify citations against retrieved evidence IDs before synthesis.
- Configure `OTEL_ENABLED=true` with GCP credentials to export spans. Token usage comes from ADK model callbacks. Cost is left unknown until you set input/output price values for the model pricing applicable to your account; the local deterministic path reports zero model cost.

## Optional integrations

Install `pip install -e ".[cloud]"` and configure `.env` (see `.env.example`). BigQuery reads expect `error_logs`, `recent_deployments`, and `service_metrics` tables in `BIGQUERY_DATASET`. `src/pipelines/seed_bigquery.py` creates these tables and inserts reproducible synthetic rows when run with appropriate permissions. `src/pipelines/ingest_runbooks.py` reads local Markdown and/or GCS Markdown objects, creates Gemini embeddings, and upserts chunks into PostgreSQL/pgvector when `DATABASE_URL` is configured.

To seed a non-production dataset, run `python -m src.pipelines.seed_bigquery --project YOUR_PROJECT --dataset sentinelops` after provisioning the dataset.

The Gemini model names in `.env.example` are examples only and must be checked against models enabled for your project/region. The current implementation deliberately keeps inference optional rather than presenting mocked LLM output as real synthesis.

## Run locally with Postgres

```powershell
docker compose up --build
```

The compose profile starts Postgres with pgvector enabled. Index the included fixtures from another terminal after the database is ready:

```powershell
python -m pip install -e ".[cloud]"
$env:DATABASE_URL = "postgresql://sentinel:sentinel@localhost:5432/sentinel"
python -m src.pipelines.ingest_runbooks
```

Embedding indexing requires Gemini or Vertex AI credentials. The API remains available without them and falls back to BM25 retrieval.

## Evaluation

`evals/dataset/scenarios.jsonl` contains 50 deterministic synthetic scenarios and `python -m evals.generate_fixtures` regenerates them plus 80 runbooks. `python -m evals.run_benchmark` compares BM25-only with BM25 plus pgvector RRF when a vector index is available, and measures evidence recall, citation faithfulness, and policy blocks. Without the index it reports the BM25 fallback. It does not claim hosted model trajectory, token throughput, or cost results. Metrics are valid only for the environment actually measured. See `evals/judge.py` for citation and safety checks.

## Deploy to Cloud Run

1. Create a GCP project, enable billing, and create a Secret Manager secret with a populated latest version for the API key. Terraform does not place secret values in state.
2. Set Terraform variables and review `infra/main.tf`; apply from `infra/`. It provisions the bucket, dataset, Artifact Registry repository, runtime service account, scoped read permissions, Cloud Trace access, and Cloud Run service.
3. Build and push the Docker image to the Artifact Registry repository output by Terraform, then set `container_image` and apply again. Cloud Run remains IAM-private by default; grant invoker access only to the callers you intend to authorize.
4. Configure the BigQuery dataset and tables, then seed synthetic data only in a non-production dataset.
5. Call `/health` and `/docs`, then submit a known alert and verify source IDs, trace export, auth, and safety decisions.

Terraform expects an existing PostgreSQL service for durable ADK sessions and pgvector; provide a secure async `session_service_uri` separately. Review IAM, networking, secret bindings, budgets, log retention, and organization policy before production use.

## Repository map

```text
src/api/             FastAPI endpoints and strict schemas
src/agents/          Bounded triage, retrieval, telemetry and citation helpers
src/tools/           Hybrid retrieval, read-only BigQuery, safety policy
src/pipelines/       Synthetic BigQuery seed and runbook loader
src/observability/   Trace setup, metrics and state pruning
evals/               Synthetic scenarios and local evaluator
infra/               Cloud Run and GCP Terraform
tests/               Unit and API tests
```

## License

MIT. See [LICENSE](LICENSE).
