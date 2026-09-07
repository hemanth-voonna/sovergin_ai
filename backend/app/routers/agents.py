"""AI Agents API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..activity import log_event
from agents.orchestrator import run_agent
from agents.registry import get_agent, list_agents
from ..schemas import AgentInfo, AgentRunIn, AgentRunOut
from . import deps  # noqa: F401

router = APIRouter(prefix="/api/agents", tags=["agents"], dependencies=[deps.auth])


@router.get("", response_model=list[AgentInfo])
def agents_list():
    return [AgentInfo(**a) for a in list_agents()]


@router.get("/{agent_id}", response_model=AgentInfo)
def agent_detail(agent_id: str):
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentInfo(**agent)


@router.post("/run", response_model=AgentRunOut)
def agents_run(payload: AgentRunIn):
    result = run_agent(payload.agent_id, payload.inputs or {})
    log_event(
        "agent_run",
        f"Agent '{payload.agent_id}' -> {result['status']}",
        details={"agent_id": payload.agent_id, "status": result["status"], "mode": result["mode"]},
    )
    return AgentRunOut(**result)