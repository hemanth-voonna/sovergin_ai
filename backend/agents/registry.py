"""Agent registry.

Every agent declares: id, name, description, category, icon, input schema,
output contract, available tools and instruction prompt. The registry is the
single source of truth shown in the Agents UI.
"""
from __future__ import annotations

AGENT_REGISTRY: list[dict] = [
    {
        "id": "document_analysis",
        "name": "Document Analysis Agent",
        "description": (
            "Extracts the structure and key entities from a document — fields, "
            "owner details, survey/record numbers, dates, amounts and section layout."
        ),
        "category": "Analysis",
        "icon": "search",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID of the document to analyse"}
            },
            "required": ["document_id"],
        },
        "output": "Structured JSON: {fields, entities, structure, statistics}",
        "tools": ["read_document", "extract_fields", "rag_search"],
        "instructions": (
            "Analyse the given government document. Extract all named fields, "
            "identify entities (people, places, organisations), describe the "
            "section structure and return statistics. Do not invent data."
        ),
        "requires_llm": False,
    },
    {
        "id": "summarization",
        "name": "Summarization Agent",
        "description": (
            "Produces a concise, faithful summary of a document plus key points, "
            "tuned to a requested length."
        ),
        "category": "Analysis",
        "icon": "file-text",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
                "length": {"type": "string", "enum": ["short", "detailed"], "default": "short"},
            },
            "required": ["document_id"],
        },
        "output": "JSON: {summary, key_points[], word_count, source_document}",
        "tools": ["read_document", "rag_search"],
        "instructions": (
            "Summarise the document faithfully. Never add facts that are not in "
            "the text. Return a summary and 3-6 key points with page references where possible."
        ),
        "requires_llm": False,
    },
    {
        "id": "research",
        "name": "Research Agent",
        "description": (
            "Answers research questions by searching across the document corpus "
            "and synthesising grounded findings with citations."
        ),
        "category": "Research",
        "icon": "compass",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "document_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question"],
        },
        "output": "JSON: {answer, grounded, sources[], related_topics[]}",
        "tools": ["rag_search"],
        "instructions": (
            "Break the question into sub-queries, search the vector store, then "
            "synthesise a grounded answer with source citations. If evidence is "
            "insufficient, say so explicitly."
        ),
        "requires_llm": False,
    },
    {
        "id": "validation",
        "name": "Validation Agent",
        "description": (
            "Runs the full validation suite on a document (missing fields, "
            "formats, inconsistencies, duplicates, suspicious values) and explains "
            "every finding in plain language."
        ),
        "category": "Compliance",
        "icon": "shield-check",
        "input_schema": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
        "output": "JSON: {status, score, issues[], explanation}",
        "tools": ["read_document", "run_validation"],
        "instructions": (
            "Validate the document against land-record rules. Report each issue "
            "with severity and a human-readable explanation of why it matters and "
            "how it could be fixed."
        ),
        "requires_llm": False,
    },
    {
        "id": "task",
        "name": "Task / Code Agent",
        "description": (
            "Turns a task description into runnable code (Python or Bash). The "
            "generated code is executed ONLY in the isolated sandbox — never on "
            "the host."
        ),
        "category": "Automation",
        "icon": "terminal",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "What should the code do?"},
                "language": {"type": "string", "enum": ["python", "bash"], "default": "python"},
            },
            "required": ["prompt"],
        },
        "output": "JSON: {code, language, notes, sandbox_hint}",
        "tools": ["generate_code", "sandbox_run"],
        "instructions": (
            "Generate safe, self-contained code that accomplishes the requested "
            "task using only the standard library. Prefer reading stdin and "
            "writing stdout. Never generate destructive commands. The code will "
            "run in an isolated sandbox with no network and no host access."
        ),
        "requires_llm": False,
    },
]

AGENTS_BY_ID = {a["id"]: a for a in AGENT_REGISTRY}


def list_agents() -> list[dict]:
    return AGENT_REGISTRY


def get_agent(agent_id: str) -> dict | None:
    return AGENTS_BY_ID.get(agent_id)