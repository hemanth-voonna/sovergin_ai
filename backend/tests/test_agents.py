"""Agent tests."""
from __future__ import annotations

import pytest

from agents.orchestrator import run_agent
from agents.registry import list_agents


def test_registry_has_five_agents():
    agents = list_agents()
    ids = {a["id"] for a in agents}
    assert ids == {
        "document_analysis", "summarization", "research", "validation", "task",
    }
    for a in agents:
        assert a["name"] and a["description"] and a["tools"] and a["instructions"]


def test_unknown_agent_returns_error():
    result = run_agent("nope", {})
    assert result["status"] == "error"


def test_missing_required_input_returns_error():
    result = run_agent("document_analysis", {})
    assert result["status"] == "error"
    assert "document_id" in result["output"]["error"]


def test_document_analysis_agent(sample_doc_id):
    result = run_agent("document_analysis", {"document_id": sample_doc_id})
    assert result["status"] == "completed"
    fields = result["output"].get("fields", {})
    assert fields.get("owner_name") == "Mrs. Sunita Vishnu Patil"
    assert fields.get("survey_number") == "124/3"


def test_summarization_agent(sample_doc_id):
    result = run_agent("summarization", {"document_id": sample_doc_id, "length": "short"})
    assert result["status"] == "completed"
    assert len(result["output"]["summary"]) > 20
    assert result["output"]["source_document"] == "land_record.txt"


def test_research_agent(sample_doc_id):
    result = run_agent("research", {"question": "Who owns the land?"})
    assert result["status"] == "completed"
    assert result["output"]["grounded"] is True
    assert "Sunita" in result["output"]["answer"]
    assert result["output"]["sources"]


def test_validation_agent(sample_doc_id, issues_doc_id):
    good = run_agent("validation", {"document_id": sample_doc_id})
    assert good["status"] == "completed"
    assert good["output"]["status"] == "valid"

    bad = run_agent("validation", {"document_id": issues_doc_id})
    assert bad["output"]["status"] == "invalid"
    assert bad["output"]["issues"]


def test_task_agent_generates_code():
    result = run_agent("task", {"prompt": "write python code to compute statistics", "language": "python"})
    assert result["status"] == "completed"
    assert "def " in result["output"]["code"] or "print(" in result["output"]["code"]
    assert result["output"]["language"] == "python"
    assert "sandbox" in result["output"]["sandbox_hint"].lower()


def test_task_agent_bash():
    result = run_agent("task", {"prompt": "list files", "language": "bash"})
    assert result["status"] == "completed"
    assert result["output"]["language"] == "bash"


def test_agents_all_run_without_error(sample_doc_id):
    for agent_id in ["document_analysis", "summarization", "research", "validation"]:
        inputs = {"document_id": sample_doc_id}
        if agent_id == "research":
            inputs = {"question": "What is the village?"}
        result = run_agent(agent_id, inputs)
        assert result["status"] == "completed", (agent_id, result)