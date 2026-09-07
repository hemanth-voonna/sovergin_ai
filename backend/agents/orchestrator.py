"""Orchestration layer.

Validates inputs against the registry, dispatches to the right implementation,
wraps everything with timing, logging and safe error handling.
"""
from __future__ import annotations

import time

from .impl import (
    run_document_analysis,
    run_research,
    run_summarization,
    run_task,
    run_validation_agent,
)
from .registry import get_agent, list_agents

_IMPLS = {
    "document_analysis": run_document_analysis,
    "summarization": run_summarization,
    "research": run_research,
    "validation": run_validation_agent,
    "task": run_task,
}


def _validate_inputs(agent: dict, inputs: dict) -> list[str]:
    schema = agent.get("input_schema", {})
    required = schema.get("required", [])
    errors = [f"Missing required input: {r}" for r in required if not inputs.get(r)]
    if not errors and not required and not inputs:
        errors.append("This agent requires at least one input.")
    return errors


def run_agent(agent_id: str, inputs: dict) -> dict:
    agent = get_agent(agent_id)
    if agent is None:
        return {
            "agent_id": agent_id,
            "status": "error",
            "output": {"error": f"Unknown agent: {agent_id}"},
            "logs": [],
            "took_ms": 0,
            "mode": "rule_based",
        }

    errors = _validate_inputs(agent, inputs)
    if errors:
        return {
            "agent_id": agent_id,
            "status": "error",
            "output": {"error": "; ".join(errors)},
            "logs": [f"Input validation failed: {'; '.join(errors)}"],
            "took_ms": 0,
            "mode": "rule_based",
        }

    start = time.monotonic()
    try:
        output, mode, logs = _IMPLS[agent_id](inputs)
        status = "completed" if mode != "error" else "error"
        if mode == "error":
            output = {"error": output.get("error", "Agent failed.")}
            mode = "rule_based"
    except Exception as exc:
        status, output, mode, logs = "error", {"error": f"Agent crashed: {exc}"}, "rule_based", [
            f"Exception: {exc}"
        ]

    return {
        "agent_id": agent_id,
        "status": status,
        "output": output,
        "logs": logs,
        "took_ms": int((time.monotonic() - start) * 1000),
        "mode": mode,
    }