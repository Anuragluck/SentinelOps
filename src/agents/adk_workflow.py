"""Optional Google ADK incident workflow with parallel investigation and bounded review."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field


class AdkCitation(BaseModel):
    source_type: str
    evidence_id: str
    excerpt: str = Field(max_length=1000)
    uri: str | None = None


class AdkCommand(BaseModel):
    command: str
    rationale: str


class AdkTriageClassification(BaseModel):
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"]
    affected_service: str
    rationale: str


class AdkIncidentDraft(BaseModel):
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"]
    root_cause: str
    confidence: float = Field(ge=0, le=1)
    citations: list[AdkCitation]
    proposed_commands: list[AdkCommand]
    rollback_steps: list[str]
    status: str = "investigated"


def _json(value) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def _state_evidence_ids(state: dict) -> set[str]:
    ids = {row.get("evidence_id") for row in state.get("runbook_evidence", [])
           if isinstance(row, dict) and row.get("evidence_id")}
    telemetry = state.get("telemetry_evidence", {})
    if isinstance(telemetry, dict):
        for rows in telemetry.values():
            if isinstance(rows, list):
                ids.update(row.get("evidence_id") for row in rows
                           if isinstance(row, dict) and row.get("evidence_id"))
    return ids


def build_root_agent():
    """Build the graph using public ADK template agents; importing this requires google-adk."""
    try:
        from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
        from google.adk.tools.tool_context import ToolContext
    except ImportError as exc:
        raise RuntimeError("Install sentinelops[cloud] to use the Google ADK workflow") from exc

    from src.observability.state_pruner import prune

    triage_model = os.getenv("TRIAGE_MODEL", "gemini-3.5-flash-lite")
    synthesis_model = os.getenv("SYNTHESIS_MODEL", "gemini-3.5-flash")

    def collect_model_usage(callback_context, llm_response):
        usage = getattr(llm_response, "usage_metadata", None)
        if usage is None:
            return None
        metrics = callback_context.state.setdefault("model_usage", {"input_tokens": 0, "output_tokens": 0, "calls": 0})
        metrics["input_tokens"] += int(getattr(usage, "prompt_token_count", 0) or 0)
        metrics["output_tokens"] += int(getattr(usage, "candidates_token_count", 0) or 0)
        metrics["calls"] += 1
        return None

    def prune_tool_payload(tool, tool_args, tool_context, result):
        del tool, tool_args, tool_context
        return {"result": prune(result, max_chars=int(os.getenv("MAX_TOOL_PAYLOAD_CHARS", "6000")))}

    def search_runbooks(query: str, tool_context: ToolContext) -> str:
        """Search local indexed runbooks; citations identify exact source chunks."""
        from src.tools.hybrid_rag import HybridRetriever
        directory = os.getenv("RUNBOOK_DIR", "evals/dataset/runbooks")
        retriever = HybridRetriever.from_directory(directory)
        results = retriever.search(query, limit=5)
        evidence = [{"evidence_id": item.chunk_id, "source": item.source, "excerpt": item.text[:700]}
                    for item in results]
        tool_context.state["runbook_evidence"] = evidence
        return _json(evidence)

    def inspect_telemetry(service: str, tool_context: ToolContext) -> str:
        """Query read-only BigQuery error, metric and deployment summaries."""
        from src.tools.bigquery_tools import recent_deployments, recent_errors, recent_metrics
        from src.observability.state_pruner import prune_state
        result = {}
        for key, reader in (("errors", recent_errors), ("metrics", recent_metrics),
                            ("deployments", recent_deployments)):
            try:
                result[key] = reader(service)
            except Exception as exc:  # Cloud integration is optional and read-only.
                result[key] = {"unavailable": type(exc).__name__}
        for section, rows in result.items():
            if isinstance(rows, list):
                for row in rows:
                    timestamp = row.get("timestamp")
                    if timestamp:
                        evidence_id = f"bq:{section}:{timestamp}"
                        row["evidence_id"] = evidence_id
        tool_context.state["telemetry_evidence"] = result
        return _json(prune_state(result, max_chars=5000))

    def finish_if_citations_verify(tool_context: ToolContext) -> dict:
        """Stop review only when every draft citation matches tool-provided evidence."""
        draft = tool_context.state.get("incident_draft", {})
        if hasattr(draft, "model_dump"):
            draft = draft.model_dump()
        if isinstance(draft, str):
            try:
                draft = json.loads(draft)
            except json.JSONDecodeError:
                draft = {}
        expected = _state_evidence_ids(tool_context.state)
        citations = draft.get("citations", []) if isinstance(draft, dict) else []
        missing = [c.get("evidence_id", "") for c in citations
                   if not isinstance(c, dict) or c.get("evidence_id") not in expected]
        if not citations or missing:
            return {"verified": False, "missing_evidence_ids": missing or ["no citations"]}
        tool_context.actions.escalate = True
        return {"verified": True}

    supervisor = LlmAgent(
        name="TriageSupervisor", model=triage_model,
        instruction=("Classify the incoming incident as SEV1-SEV4. Preserve the service and exact alert "
                     "facts. Do not infer a cause. Return the required structured severity and routing rationale."),
        output_schema=AdkTriageClassification,
        output_key="triage_classification", after_model_callback=collect_model_usage,
    )
    researcher = LlmAgent(
        name="RunbookResearcher", model=triage_model,
        instruction=("Use search_runbooks for the affected service and alert terms. Return only facts in "
                     "the retrieved chunks. Attach the exact evidence_id to each claim."),
        tools=[search_runbooks], output_key="runbook_summary",
        after_tool_callback=prune_tool_payload, after_model_callback=collect_model_usage,
    )
    telemetry = LlmAgent(
        name="TelemetryInvestigator", model=triage_model,
        instruction=("Call inspect_telemetry for the affected service. Correlate errors, metrics and recent "
                     "deployments. Cite only evidence_id values returned by the tool."),
        tools=[inspect_telemetry], output_key="telemetry_summary",
        after_tool_callback=prune_tool_payload, after_model_callback=collect_model_usage,
    )
    parallel_investigation = ParallelAgent(
        name="ParallelInvestigation", sub_agents=[researcher, telemetry],
        description="Investigates runbooks and read-only telemetry in parallel.",
    )
    planner = LlmAgent(
        name="RemediationPlanner", model=synthesis_model,
        instruction=("Create a grounded incident report from the alert, triage classification, and investigation state. "
                     "Use the classification severity unless the incoming alert already supplied a severity. Do not "
                     "invent evidence, causes, timestamps, or rollback steps. Use exact evidence IDs. "
                     "Propose diagnostics only; never execute a command. Return the required JSON schema."),
        output_schema=AdkIncidentDraft, output_key="incident_draft", after_model_callback=collect_model_usage,
    )
    critic = LlmAgent(
        name="ReflectionCritic", model=synthesis_model,
        instruction=("Check the draft against available evidence IDs. Identify unsupported claims or missing "
                     "citations. Call finish_if_citations_verify only when every citation is exact and real."),
        tools=[finish_if_citations_verify], output_key="citation_review",
        after_tool_callback=prune_tool_payload, after_model_callback=collect_model_usage,
    )
    synthesis_loop = LoopAgent(
        name="SynthesisVerificationLoop", sub_agents=[planner, critic], max_iterations=2,
    )
    return SequentialAgent(
        name="SentinelOpsRoot", sub_agents=[supervisor, parallel_investigation, synthesis_loop],
        description="Classifies, investigates in parallel, then synthesizes and checks a cited incident report.",
    )


@lru_cache(maxsize=1)
def get_root_agent():
    return build_root_agent()


async def run_adk_triage(alert):
    """Execute ADK for a single alert; session storage can be made persistent via SESSION_SERVICE_URI."""
    import uuid

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from src.api.schemas import Citation, IncidentReport, ProposedCommand, Severity
    from src.tools.safety_policy import apply_safety_policy

    app_name = "sentinelops"
    user_id = "incident-api"
    session_id = uuid.uuid4().hex
    session_uri = os.getenv("SESSION_SERVICE_URI")
    session_service = InMemorySessionService()
    if session_uri:
        try:
            from google.adk.sessions import DatabaseSessionService
            session_service = DatabaseSessionService(db_url=session_uri)
            await session_service.prepare_tables()
        except Exception as exc:
            raise RuntimeError("SESSION_SERVICE_URI could not initialize ADK persistent sessions") from exc
    runner = Runner(agent=get_root_agent(), app_name=app_name, session_service=session_service)
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    message = types.Content(role="user", parts=[types.Part(text=alert.model_dump_json())])
    final_text = ""
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text or ""
        session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        state = session.state if session else {}
        draft = state.get("incident_draft", {})
        if hasattr(draft, "model_dump"):
            draft = draft.model_dump()
        if isinstance(draft, str):
            try:
                draft = json.loads(draft)
            except json.JSONDecodeError:
                draft = json.loads(final_text)
        citations = [Citation.model_validate(item.model_dump() if hasattr(item, "model_dump") else item)
                     for item in draft.get("citations", [])]
        allowed_ids = _state_evidence_ids(state)
        citation_ids = {c.evidence_id for c in citations}
        if not citations or not citation_ids.issubset(allowed_ids):
            raise ValueError("ADK report did not pass deterministic citation verification")
        command_inputs = [item.model_dump() if hasattr(item, "model_dump") else item
                          for item in draft.get("proposed_commands", [])]
        commands = apply_safety_policy(command_inputs)
        severity = alert.severity if alert.severity != Severity.UNKNOWN else Severity(draft["severity"])
        report = IncidentReport(
            incident_id=alert.alert_id, service=alert.service, severity=severity,
            root_cause=draft["root_cause"], confidence=draft["confidence"], citations=citations,
            proposed_commands=[ProposedCommand.model_validate(command) for command in commands],
            rollback_steps=draft.get("rollback_steps", []), status=draft.get("status", "investigated"),
            limitations=[],
        )
        return report, session_id, state.get("model_usage", {})
    finally:
        if session_uri and hasattr(session_service, "close"):
            await session_service.close()
