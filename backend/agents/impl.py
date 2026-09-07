"""Agent implementations.

Every agent has two execution paths:
  * LLM path — prompt-based, used when a real LLM is configured.
  * rule-based path — deterministic, fully offline (sovereign mode).
Both produce the same output contract, so the UI never depends on a key.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter

from ai.llm import get_llm
from app.database import SessionLocal
from app.models import Document
from document.validator import validate_text
from rag.grounding import STOPWORDS
from rag.pipeline import get_rag_pipeline
from .tools import call_tool

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


# ------------------------------------------------------------------ helpers
def _get_document(document_id: str) -> Document | None:
    db = SessionLocal()
    try:
        return db.get(Document, document_id)
    finally:
        db.close()


def _extract_json(text: str) -> dict | None:
    """Pull the first balanced JSON object out of an LLM reply."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _top_keywords(text: str, n: int = 8) -> list[str]:
    counts = Counter(t for t in _tokens(text) if t not in STOPWORDS and len(t) > 2)
    return [w for w, _c in counts.most_common(n)]


def _extractive_summary(text: str, sentences_out: int = 4) -> tuple[str, list[str]]:
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if len(s.strip()) > 20]
    if not sentences:
        return text[:400], []
    counts = Counter(t for t in _tokens(text) if t not in STOPWORDS and len(t) > 2)
    scored = [(s, sum(counts.get(w, 0) for w in set(_tokens(s)))) for s in sentences]
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:sentences_out]
    top_sorted = sorted(top, key=lambda x: sentences.index(x[0]))
    key_points = [s[:200] for s, _sc in top[:5]]
    return " ".join(s for s, _sc in top_sorted), key_points


def _llm_json(messages: list[dict]) -> dict | None:
    llm = get_llm()
    if getattr(llm, "mode", "llm") == "mock":
        return None
    reply = llm.chat(messages, temperature=0.2, max_tokens=1500)
    return _extract_json(reply)


# ------------------------------------------------------------------ 1. Document analysis
def run_document_analysis(inputs: dict) -> tuple[dict, str, list[str]]:
    logs: list[str] = []
    doc_id = inputs.get("document_id")
    doc = _get_document(doc_id) if doc_id else None
    if doc is None:
        return {"error": "Provide a valid processed document_id."}, "error", logs

    text = doc.extracted_text or ""
    logs.append(f"Loaded document '{doc.filename}' ({doc.page_count} pages, {doc.char_count} chars).")
    fields = validate_text(text).fields
    logs.append(f"Extracted {len(fields)} known fields.")

    llm_json = _llm_json(
        [
            {
                "role": "system",
                "content": (
                    "You are the Document Analysis Agent of a government land-records workbench. "
                    "Analyse the document and reply ONLY with JSON: "
                    '{"fields": {...}, "entities": {...}, "structure": {...}, "statistics": {...}}. '
                    "Do not invent data that is not present."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Document: {doc.filename}\n\n--- DOCUMENT TEXT ---\n{text[:14000]}\n\n"
                    f"Pre-extracted fields: {json.dumps(fields)}\n"
                    "Return the JSON analysis."
                ),
            },
        ]
    )
    if llm_json:
        logs.append("Analysed with LLM.")
        return llm_json, "llm", logs

    sentences = [s for s in SENTENCE_RE.split(text) if s.strip()]
    names = sorted(
        set(
            re.findall(
                r"(?:owner|co-owner|registrar|witness)\s*[:#-]?\s*([A-Z][a-zA-Z.\s]{3,60})",
                text,
            )
        )
    )
    output = {
        "fields": fields,
        "entities": {
            "named_people": names,
            "places": [v for k, v in fields.items() if k in ("village", "district", "taluka")],
        },
        "structure": {
            "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
            "sentences": len(sentences),
            "lines": len(text.splitlines()),
            "sections": _top_keywords(text, 5),
        },
        "statistics": {
            "characters": doc.char_count,
            "words": len(_tokens(text)),
            "pages": doc.page_count,
            "top_keywords": _top_keywords(text),
            "ocr_used": doc.ocr_used,
        },
    }
    logs.append("Rule-based analysis (no LLM configured).")
    return output, "rule_based", logs


# ------------------------------------------------------------------ 2. Summarization
def run_summarization(inputs: dict) -> tuple[dict, str, list[str]]:
    logs: list[str] = []
    doc_id = inputs.get("document_id")
    length = inputs.get("length", "short")
    doc = _get_document(doc_id) if doc_id else None
    if doc is None:
        return {"error": "Provide a valid processed document_id."}, "error", logs
    text = doc.extracted_text or ""
    logs.append(f"Loaded '{doc.filename}' for summarisation.")

    n = 2 if length == "short" else 6
    llm_json = _llm_json(
        [
            {
                "role": "system",
                "content": (
                    "You are the Summarization Agent. Summarise the document faithfully "
                    "using ONLY its content. Reply ONLY with JSON: "
                    '{"summary": "...", "key_points": ["..."], "word_count": n, '
                    '"source_document": "..."}'
                ),
            },
            {
                "role": "user",
                "content": f"Document: {doc.filename}\n\n--- TEXT ---\n{text[:14000]}\n\n"
                f"Length: {length}. Return the JSON summary."
            },
        ]
    )
    if llm_json:
        logs.append("Summarised with LLM.")
        llm_json.setdefault("source_document", doc.filename)
        return llm_json, "llm", logs

    summary, key_points = _extractive_summary(text, sentences_out=n)
    output = {
        "summary": summary,
        "key_points": key_points,
        "word_count": len(summary.split()),
        "source_document": doc.original_name or doc.filename,
    }
    logs.append("Extractive summary (no LLM configured).")
    return output, "rule_based", logs


# ------------------------------------------------------------------ 3. Research
def run_research(inputs: dict) -> tuple[dict, str, list[str]]:
    logs: list[str] = []
    question = (inputs.get("question") or "").strip()
    doc_ids = inputs.get("document_ids") or None
    if not question:
        return {"error": "Provide a question."}, "error", logs
    logs.append(f"Researching: {question}")

    pipeline = get_rag_pipeline()
    answer = pipeline.answer(question, document_ids=doc_ids, top_k=6)
    related = _top_keywords(" ".join(s["snippet"] for s in answer.sources), 5)
    output = {
        "question": question,
        "answer": answer.answer,
        "grounded": answer.grounded,
        "sources": answer.sources,
        "related_topics": related,
        "mode": answer.mode,
    }
    logs.append(f"Retrieved {len(answer.sources)} source passages in {answer.took_ms}ms.")
    return output, answer.mode, logs


# ------------------------------------------------------------------ 4. Validation
def run_validation_agent(inputs: dict) -> tuple[dict, str, list[str]]:
    logs: list[str] = []
    doc_id = inputs.get("document_id")
    doc = _get_document(doc_id) if doc_id else None
    if doc is None:
        return {"error": "Provide a valid processed document_id."}, "error", logs
    text = doc.extracted_text or ""
    result = validate_text(text)
    logs.append(f"Rule checks: {len(result.issues)} issue(s), status={result.status}.")

    issues_text = "\n".join(
        f"- [{i.severity.upper()}] ({i.category}) {i.field or 'document'}: {i.message}"
        for i in result.issues
    ) or "No issues found."

    llm_json = _llm_json(
        [
            {
                "role": "system",
                "content": (
                    "You are the Validation Agent. Explain each validation issue in plain "
                    "language for a government clerk: why it matters and how to fix it. "
                    "Reply ONLY with JSON: {\"explanation\": \"...\", \"recommended_actions\": [...]}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Document: {doc.filename}\nValidation status: {result.status}\n\n"
                    f"ISSUES:\n{issues_text}\n\nExplain the findings."
                ),
            },
        ]
    )
    if llm_json:
        logs.append("Explanations generated with LLM.")
        output = result.to_dict()
        output.update(llm_json)
        return output, "llm", logs

    output = result.to_dict()
    output["explanation"] = (
        f"The document was checked against land-record rules and is rated {result.status.upper()} "
        f"(score {result.score}/100)."
        if not result.issues
        else "The document has the following issues:\n" + issues_text
    )
    output["recommended_actions"] = [
        f"Fix {i.category} issue on {i.field or 'the document'}." for i in result.issues
    ] or ["No action required."]
    logs.append("Rule-based explanation (no LLM configured).")
    return output, "rule_based", logs


# ------------------------------------------------------------------ 5. Task / Code
_TASK_TEMPLATES: list[tuple[list[str], str]] = [
    (
        ["statistics", "stats", "summary", "analyse", "analyze", "word count"],
        """# Task Agent output: text statistics tool (safe, sandbox-only)
import sys
import re

text = sys.stdin.read() if not sys.stdin.isatty() else \"\"
if not text:
    text = \"SovereignAI Workbench — secure document processing.\"

words = re.findall(r\"[a-zA-Z0-9']+\", text)
print(f\"characters: {len(text)}\")
print(f\"words: {len(words)}\")
print(f\"lines: {text.count(chr(10)) + 1}\")
print(f\"unique words: {len(set(w.lower() for w in words))}\")
print(\"sandbox execution OK\")
""",
    ),
    (
        ["search", "find", "lookup", "query"],
        """# Task Agent output: lookup tool (safe, sandbox-only)
import sys

records = [
    {\"record\": \"RL-2023-04512\", \"owner\": \"Sunita Vishnu Patil\", \"survey\": \"124/3\"},
    {\"record\": \"RL-2023-04513\", \"owner\": \"Rajesh Kumar\", \"survey\": \"98/2\"},
]
term = sys.argv[1] if len(sys.argv) > 1 else \"124/3\"
for r in records:
    if term.lower() in \" \".join(r.values()).lower():
        print(f\"match: {r}\")
        break
else:
    print(\"no match found\")
""",
    ),
    (
        ["compute", "calculate", "math", "fibonacci", "prime", "sum", "average"],
        """# Task Agent output: computation tool (safe, sandbox-only)
import math

print(\"SovereignAI computation sandbox\")
print(\"pi =\", round(math.pi, 6))
print(\"first 8 primes:\", [n for n in range(2, 30) if all(n % d for d in range(2, int(n**0.5) + 1))][:8])
print(\"100 + 25 =\", 100 + 25)
""",
    ),
]

_DEFAULT_TEMPLATE = """# Task Agent output: safe demonstration script (sandbox-only)
import platform
import time

print(\"SovereignAI secure sandbox\")
print(f\"python: {platform.python_version()}\")
print(f\"platform: {platform.platform()}\")
start = time.monotonic()
total = sum(i * i for i in range(100_000))
print(f\"computed sum of squares: {total} in {(time.monotonic() - start) * 1000:.1f} ms\")
print(\"exit: OK\")
"""


def _template_code(prompt: str, language: str) -> str:
    if language == "bash":
        return (
            "#!/bin/bash\n"
            "# Task Agent output: safe shell demo (sandbox-only)\n"
            'echo "SovereignAI bash sandbox: $(pwd)"\n'
            "echo \"files: $(ls -1 | wc -l)\"\n"
            "echo 'exit: OK'\n"
        )
    for keywords, code in _TASK_TEMPLATES:
        if any(k in prompt.lower() for k in keywords):
            return code
    return _DEFAULT_TEMPLATE


def run_task(inputs: dict) -> tuple[dict, str, list[str]]:
    logs: list[str] = []
    prompt = (inputs.get("prompt") or "").strip()
    language = inputs.get("language", "python")
    if not prompt:
        return {"error": "Provide a task prompt."}, "error", logs
    logs.append(f"Task prompt: {prompt}")

    llm = get_llm()
    if getattr(llm, "mode", "llm") != "mock":
        try:
            reply = llm.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are the Task/Code Agent. Write SAFE, self-contained "
                            f"{language} code that accomplishes the user's task using only the "
                            "standard library. Never use network, filesystem writes outside "
                            "the current directory, or destructive commands. Reply ONLY with "
                            "the code inside a fenced block."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1200,
            )
            code = re.search(r"```(?:\w+)?\s*(.*?)```", reply, re.S)
            code = code.group(1).strip() if code else reply.strip()
            logs.append("Code generated with LLM.")
            return {
                "code": code,
                "language": language,
                "notes": "Generated by the LLM — review before executing.",
                "sandbox_hint": "Execute this code only through the Sandbox (isolated, no network, no host access).",
            }, "llm", logs
        except Exception as exc:
            logs.append(f"LLM generation failed ({exc}); using template fallback.")

    code = _template_code(prompt, language)
    logs.append("Template code generated (no LLM configured).")
    return {
        "code": code,
        "language": language,
        "notes": (
            "Template generated locally. For arbitrary task-specific code, configure an LLM "
            "(see Settings)."
        ),
        "sandbox_hint": "Execute this code only through the Sandbox (isolated, no network, no host access).",
    }, "rule_based", logs