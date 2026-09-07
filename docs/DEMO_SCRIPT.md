# SIH 2026 · SIH117 — SovereignAI Workbench: Presentation & Demo Script

A timed walkthrough (~12–15 minutes) for judges. Everything below runs on the shipped
demo, offline, with **no API keys**.

---

## 0. Setup before the demo (2 min)

```bash
docker compose up --build -d
```

Open **http://localhost:8080**. Verify the top-right pill shows **“API online”**.

## 1. Problem statement (90 s)

> “Departments hold lakhs of scanned land records. They can't be searched, they can't be
> answered, and they often contain errors. Cloud AI is blocked by data-privacy rules, and
> generic chatbots hallucinate.”
>
> “SovereignAI Workbench fixes all three: it reads the documents **on-premise**, answers
> **only from them with citations**, flags record defects, and executes AI tasks **safely**
> — zero external dependencies.”

## 2. Architecture walkthrough (90 s)

Show the README architecture diagram:

- Frontend (React) → FastAPI backend → services → **AI layer** (configurable LLM + local
  embeddings) and **RAG layer** (Chroma behind a modular interface) → PostgreSQL +
  persistent vector store.
- Emphasise: *modular vector store, configurable LLM, local embeddings, sandboxed
  execution — every layer is replaceable and every layer stays in your infrastructure.*

## 3. Live demo (8 min)

### Step 1 — Dashboard (30 s)
Show the stat cards (all zero), health panel (services), activity chart.
> “This is the control room — every action in the platform is tracked here.”

### Step 2 — Load the sample document (60 s)
Click **“Load sample document”** on the Dashboard (or upload a file on Documents page —
drag & drop a PDF). Open **Documents**, click the **eye icon**:
- Pipeline stepper: Validated → Extracted → Cleaned & chunked → Indexed.
- Show the **extracted text** panel (page tabs) and the OCR badge.
> “Validation, extraction, chunking, embeddings and vector storage ran end-to-end.
> Notice the checksum — content is fingerprinted on upload.”

### Step 3 — RAG Chat (2 min)
Open **RAG Chat**. Ask:

- *“Who is the registered owner?”* → answer + source cards (document, page, chunk,
  similarity).
- *“What is the survey number?”* → **Survey Number: 124/3**.
- *“What is the capital of France?”* → amber **“not found in corpus”** — the refusal.
> “Every answer is grounded in retrieved passages with citations. When the information
> isn't in the documents, the system says so instead of making things up — that's the
> anti-hallucination guarantee.”

### Step 4 — Validation (60 s)
Open **Validation** → select the sample → **Run validation checks** → **Valid · 100/100**
with all fields extracted (owner, survey number, village, district, area, dates).
Then upload `land_record_with_issues.txt` and re-run:
- `Invalid`, score drops, issues listed: missing district, area `N/A`, duplicated record
  number, future date — each with severity and category.
> “The same engine powers the Validation Agent's plain-language explanations.”

### Step 5 — AI Agents (90 s)
Open **AI Agents**. Run **Document Analysis Agent** on the sample:
- Execution log → structured JSON (fields, entities, statistics).
Run **Research Agent** (“Who owns the land?”) → grounded answer with sources.
Open the **Task / Code Agent** → *“write code to compute statistics”* → generated code +
**Run in Sandbox** button.

### Step 6 — Secure Sandbox (60 s)
Click **Run in Sandbox** (code arrives pre-filled). Run it:
- Status `completed`, stdout, exit code, sandbox log.
Demonstrate the guardrails: paste `import os` → blocked. Set timeout to 1 s and run
`time.sleep(30)` → `timed_out`.
> “AI-generated code only ever executes here — throwaway directory, hard timeouts,
> memory limits, blocked system imports, no network. Docker executor available for
> production-grade isolation.”

### Step 7 — Close the loop (30 s)
Return to the **Dashboard** — documents/processed/indexed counts, RAG query counter,
agent/sandbox counters and the activity feed have all updated live.

## 4. Security deep-dive (60 s)

- No API keys in the browser — env-only, server-side.
- Upload validation (extension, size, **magic bytes**).
- Prompt-injection guardrails in the grounding prompt.
- Optional Bearer-token auth (`ACCESS_TOKEN`).
- Audit logging of every action.
- Non-root container runtime.

## 5. Q&A ammo

| Question | Answer |
|---|---|
| What if there's no internet? | Fully offline: local embeddings (ONNX, with hashing fallback), built-in grounded engine, Docker-shipped Tesseract data. |
| Can we use our own LLM? | Yes — `LLM_PROVIDER`, `OPENAI_BASE_URL` (Ollama/vLLM/LM Studio). Compose ships with sovereign mode. |
| Why Chroma? | Local, persistent, open source — and it's behind an interface, so Qdrant/pgvector swap in without touching the pipeline. |
| How do you prevent hallucination? | Answers are constructed from retrieved excerpts only; unanswerable questions produce an explicit refusal; citations are shown. |
| How do you validate records? | Rule engine: required fields, formats, consistency, duplicates, suspicious values → Valid/Warning/Invalid + score. |
| Is the sandbox safe? | Subprocess isolation + rlimits + import blocking; optional Docker `--network none` executor. |
| Scaling? | PostgreSQL, stateless API, Chroma on persistent volume; batch ingestion is on the roadmap. |