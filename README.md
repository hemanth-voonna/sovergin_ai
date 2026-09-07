# 🇮🇳 SovereignAI – Workbench

**Secure, sovereign document intelligence for government & enterprise**
Smart India Hackathon 2026 · Problem Statement **SIH117**

SovereignAI Workbench is a complete, on-premise AI platform for secure document processing:
upload → validate → extract text → **OCR** → clean → chunk → embed → store vectors →
**grounded RAG question-answering with citations**, rule-based **document validation**,
five orchestrated **AI agents**, and an **isolated code sandbox** — all deployable with
`docker compose up --build` and fully functional **without any external API key**.

> The system is designed for privacy: documents, embeddings, vectors and the LLM all run
> **on your own infrastructure**. No data ever leaves the deployment.

---

## Table of contents

1. [Problem statement](#problem-statement)
2. [Solution](#solution)
3. [Features](#features)
4. [Architecture](#architecture)
5. [Technology stack](#technology-stack)
6. [Project structure](#project-structure)
7. [Installation](#installation)
8. [Environment variables](#environment-variables)
9. [Running locally](#running-locally)
10. [Docker deployment](#docker-deployment)
11. [RAG workflow](#rag-workflow)
12. [OCR workflow](#ocr-workflow)
13. [Agent workflow](#agent-workflow)
14. [Security](#security)
15. [Testing](#testing)
16. [End-to-end demo](#end-to-end-demo)
17. [SIH presentation / demo flow](#sih-presentation--demo-flow)
18. [Known limitations](#known-limitations)
19. [Future scope](#future-scope)

---

## Problem statement

Government departments handle large volumes of scanned land records, deeds and legacy
documents. These records are unstructured, hard to search, and frequently contain missing
or inconsistent fields. Using cloud AI to process them is often impossible due to data
privacy rules, and generic chatbots hallucinate answers that cannot be verified.

**SIH117** asks for a sovereign (self-hosted) AI workbench that can process documents,
extract text (including scanned ones), answer questions **only from the documents**, flag
record-keeping problems, and execute AI-generated tasks safely — without depending on
foreign cloud services.

## Solution

SovereignAI Workbench is a modular, end-to-end document-intelligence platform:

- **Ingestion pipeline** — upload validation, text extraction, automatic OCR fallback,
  cleaning, chunking, local embeddings, and a persistent vector store.
- **Grounded RAG** — every answer is retrieved from the user's documents and shown with
  source citations (document, page, chunk, similarity). When the answer is not in the
  corpus, the system says so explicitly — **it never hallucinates**.
- **Validation engine** — rule-based checks (required fields, formats, consistency,
  duplicates, suspicious values) that rate records `Valid / Warning / Invalid` with a
  compliance score and per-issue explanations.
- **Agent registry & orchestration** — five agents (Document Analysis, Summarization,
  Research, Validation, Task/Code) with declared inputs, tools, output contracts and
  error handling. They run in fully-offline rule-based mode out of the box, or can use a
  local LLM when one is configured.
- **Secure sandbox** — AI-generated code executes in a throwaway sandbox with hard
  timeouts, memory/CPU limits, blocked system imports, and an optional Docker executor
  (`--network none`). Nothing ever runs directly on the host.
- **Configurable LLM layer — LOCAL-ONLY.** Only the built-in grounded engine (offline,
  zero-config) or a local OpenAI-compatible server you point at (Ollama, vLLM, LM Studio)
  can be used. Cloud endpoints such as `api.openai.com` are refused by the resolver — an
  API key alone can never enable a cloud provider.

## Features

| Area | Capabilities |
|---|---|
| Dashboard | Live statistics (documents, processed, indexed, RAG queries, agent runs, sandbox runs), system health (CPU/RAM/disk/services), 7-day activity chart, audit-trail feed |
| Document management | Upload PDF/DOCX/TXT/images, drag & drop, magic-byte & size validation, per-stage pipeline status, extracted-text viewer with page tabs, delete (DB + vectors) |
| OCR | Auto-detects scanned PDFs (no text layer) and images; per-page confidence; Tesseract (Docker, multi-language) or bundled-ONNX RapidOCR fallback — so OCR also works on hosts with no Tesseract install |
| RAG | Query → embedding → vector search (Chroma) → context → LLM/extractive grounding → answer + sources; per-document filtering; top-k control |
| Vector DB | Chroma persistent store behind a modular `VectorStore` interface (swap-in Qdrant/pgvector); stores text, embeddings, page, chunk index, document metadata |
| LLM | Local-only: built-in grounded extractive engine (zero-config, offline) or a local OpenAI-compatible server (Ollama/vLLM/LM Studio) via `OPENAI_BASE_URL`; cloud endpoints refused by default |
| AI Agents | 5 agents, registry-driven UI, tool calling, execution logs, structured JSON output, rule-based fallbacks |
| Validation | Required fields, date/area/number formats, cross-field consistency, duplicates, suspicious keywords; score 0–100 |
| Sandbox | Python & Bash; timeout + memory limits; import blocking; temp dir; stripped env (POSIX); Docker executor option |
| Security | No secrets in frontend, optional Bearer-token API auth, CORS allow-list, file validation, safe error handling, activity logging, prompt-injection guardrails |
| Sovereignty | Strictly local-only AI: cloud endpoints refused, telemetry disabled, no runtime model downloads, embedded Chroma + SQLite/Postgres on-prem |
| Deployment | Docker Compose (PostgreSQL + API + nginx-served SPA), health checks, non-root runtime |

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + TS + Vite + Tailwind)             │
│   Dashboard · Documents · RAG Chat · AI Agents · OCR · Validation ·        │
│   Sandbox · Settings                    (nginx: static + /api proxy)       │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │ REST (FastAPI)
┌───────────────────────────────▼────────────────────────────────────────────┐
│                          BACKEND (FastAPI + Pydantic)                      │
│  ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐ │
│  │ documents │ │ rag      │ │ agents    │ │ validation│ │ sandbox / ocr │ │
│  └─────┬─────┘ └────┬─────┘ └─────┬─────┘ └─────┬─────┘ └───────┬───────┘ │
│        └────────────┴─────────────┴─────────────┴───────────────┘         │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Services & pipelines                                                 │ │
│  │  upload → validate → extract → OCR? → clean → chunk → embed → store  │ │
│  │  question → embed → search → context → LLM/grounding → sources       │ │
│  └──────────┬───────────────────────────────┬───────────────────────────┘ │
│             │                               │                             │
│  ┌──────────▼──────────┐        ┌───────────▼────────────┐                │
│  │  AI layer           │        │  RAG layer             │                │
│  │  • LLM (configurable)│        │  • chunker             │                │
│  │  • embeddings (local)│       │  • VectorStore (ABC)   │                │
│  └──────────────────────┘        │    Chroma / in-memory  │                │
│                                  └───────────┬────────────┘                │
│  ┌───────────┐ ┌───────────┐ ┌──────────────▼───────────┐ ┌─────────────┐ │
│  │ PostgreSQL│ │ data/     │ │ data/chroma (persistent) │ │ samples/    │ │
│  │ documents │ │ uploads/  │ │ vectors + metadata       │ │ demo docs   │ │
│  │ activity  │ │           │ │                          │ │             │ │
│  └───────────┘ └───────────┘ └──────────────────────────┘ └─────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite 5, Tailwind CSS 3, React Router, Recharts, Lucide icons |
| Backend | Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2, Uvicorn |
| AI/LLM | Built-in grounded engine (offline default); optional LOCAL OpenAI-compatible client (openai SDK against Ollama, vLLM, LM Studio only — cloud endpoints refused) |
| Embeddings | Chroma ONNX `all-MiniLM-L6-v2` (local, no key) with automatic deterministic hashing fallback |
| Vector DB | Chroma (persistent, open source) behind a modular interface |
| OCR | Tesseract 5 + pytesseract (Docker) with RapidOCR/ONNX fallback (pure-Python, models bundled in the wheel, works offline on any host) + PyMuPDF rendering for scanned PDFs |
| Database | PostgreSQL 16 (Docker) / SQLite (local dev) |
| Text extraction | PyMuPDF, python-docx, Pillow |
| Sandbox | subprocess isolation with rlimits/timeouts/import blocking; optional Docker `--network none` executor |
| Deployment | Docker, Docker Compose, nginx |

## Project structure

```
SovereignAI-Workbench/
├── backend/
│   ├── app/                 # FastAPI app: config, models, schemas, security,
│   │   │                    #   database, services, routers (REST API)
│   │   └── routers/         # documents, rag, ocr, agents, validation,
│   │                        #   sandbox, dashboard, health, settings
│   ├── ai/                  # LLM clients + embedding providers
│   ├── rag/                 # chunker, vector store, retrieval pipeline, grounding
│   ├── document/            # text extractor + validation rules
│   ├── ocr/                 # Tesseract engine
│   ├── agents/              # registry, tools, orchestrator, agent logic
│   ├── sandbox/             # isolated code executor
│   ├── samples/             # demo land-record documents (txt/pdf/docx/png)
│   ├── scripts/             # sample-document generator
│   ├── tests/               # pytest suite (85 tests + 4 OCR skips)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api.ts           # typed API client (single source of endpoints)
│   │   ├── types.ts         # API contract types
│   │   ├── components/      # layout + UI primitives
│   │   └── pages/           # Dashboard, Documents, RAG Chat, Agents, OCR,
│   │                        #   Validation, Sandbox, Settings
│   ├── nginx.conf
│   └── Dockerfile
├── docs/
│   └── DEMO_SCRIPT.md       # step-by-step SIH presentation script
├── docker-compose.yml
├── .env.example
└── README.md
```

## Installation

### Prerequisites

- **Docker + Docker Compose** (recommended path) — or
- Python 3.10+ and Node.js 18+ for local development.

### 1. Clone & configure

```bash
git clone <your-repo-url> SovereignAI-Workbench
cd SovereignAI-Workbench
cp .env.example .env      # optional: set ACCESS_TOKEN etc. (all AI is local — see below)
```

### 2. Start everything

```bash
docker compose up --build
```

- Frontend UI → **http://localhost:8080**
- Backend API → http://localhost:8000 (docs at `/docs`)
- Health check → http://localhost:8000/api/health

> At **build/provisioning time** (once, while online) the Docker image downloads the
> ONNX embedding model (~80 MB) and the OCR trained data. At **runtime** the app never
> downloads anything — every component runs locally. Skip the download entirely by
> setting `EMBEDDINGS_PROVIDER=hash` (zero-model mode).

## Environment variables

All AI is **local-only** — see [Offline operation & data sovereignty](#offline-operation--data-sovereignty).

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `auto` | `auto` \| `builtin` \| `mock` \| `ollama` \| `openai-compatible` (all local) |
| `LLM_MODEL` | `local-llm` | Model name for a LOCAL endpoint (inert with the built-in engine) |
| `OPENAI_API_KEY` | *(empty)* | Key for a LOCAL OpenAI-compatible server (never sent to the cloud) |
| `OPENAI_BASE_URL` | *(empty)* | Local endpoint, e.g. `http://127.0.0.1:11434/v1` (Ollama) — loopback required |
| `ALLOW_REMOTE_LLM` | `false` | `true` = allow a non-loopback `OPENAI_BASE_URL` (explicit opt-in) |
| `EMBEDDINGS_PROVIDER` | `auto` | `auto` \| `chroma` \| `hash` (hash = zero-model, fully offline) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model (cached locally, never downloaded at runtime) |
| `ANONYMIZED_TELEMETRY` | `false` | Chroma product telemetry is always disabled |
| `DATABASE_URL` | `sqlite:///./data/sovereignai.db` | PostgreSQL in Docker, SQLite locally |
| `UPLOAD_DIR` / `VECTOR_DB_PATH` / `DATA_DIR` | `./data/...` | Storage locations |
| `MAX_UPLOAD_MB` | `25` | Upload size limit |
| `ACCESS_TOKEN` | *(empty)* | If set, all API calls require `Authorization: Bearer <token>` |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allow-list |
| `OCR_LANG` | `eng` | Tesseract language(s) |
| `RAG_TOP_K` / `CHUNK_SIZE` / `CHUNK_OVERLAP` | `5 / 900 / 120` | Retrieval & chunking |
| `SANDBOX_EXECUTOR` | `subprocess` | `subprocess` \| `docker` |

Full reference in [`.env.example`](.env.example).

## Running locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# OCR works out of the box: Tesseract if installed, else the built-in
# RapidOCR/ONNX fallback (no system install needed)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173 (proxies /api → :8000)
```

### One-click launch from the project folder (Windows)

After the setup steps above (`.venv` + `frontend/node_modules`), double-click
**`start.bat`** in the project folder. It starts the backend and frontend (or
reuses already-running ones), waits for both to answer, and opens your browser
at http://127.0.0.1:5173. Use **`stop.bat`** to shut both down.

> Note: double-clicking `frontend/index.html` will **not** open the app — it is a
> dev entry point that needs the dev servers (Vite) running. Always use
> `start.bat` or `npm run dev` from the `frontend/` folder.

## Docker deployment

```bash
docker compose up --build -d     # detached
docker compose ps                # status
docker compose logs -f backend   # logs
docker compose down              # stop
docker compose down -v           # stop + wipe data volumes
```

Compose services:

- **db** — PostgreSQL 16 (persistent volume, health-checked)
- **backend** — FastAPI + Tesseract + Chroma (persistent `sovereign_data` volume, non-root user)
- **frontend** — nginx serving the built SPA and proxying `/api` to the backend

## RAG workflow

```
User question
   │
   ▼
Query processing (trim, validate)
   │
   ▼
Embedding (local ONNX / hash fallback)
   │
   ▼
Vector search (Chroma, optional document filter, top-k)
   │
   ▼
Context construction (numbered excerpts w/ doc name + page)
   │
   ▼
LLM (grounded system prompt, prompt-injection guardrails)
   OR built-in extractive engine (sovereign mode)
   │
   ▼
Grounded answer + Sources (document, page, chunk, similarity)
```

- **Grounded**: answers must come from retrieved excerpts; citations are rendered as
  source cards in the UI.
- **Anti-hallucination**: if no passage supports the answer, the response is exactly
  *“The requested information could not be found in the provided documents.”*

## OCR workflow

```
Document / Image
   │
   ├─ PDF with text layer ──► direct extraction (no OCR)
   │
   └─ Scanned PDF / image ──► render pages (PyMuPDF @ 220 DPI)
                              │
                              ▼
                         Tesseract OCR (eng/hin/mar)
                              │
                              ▼
                         Extracted text + per-page confidence
                              │
                              ▼
                         Clean → chunk → embeddings → vectors (ready for RAG)
```

The OCR page shows extracted text per page with confidence bars, and can ingest the
result straight into the corpus.

## Agent workflow

```
User picks an agent + inputs (registry-driven UI)
   │
   ▼
Orchestrator validates inputs against the agent schema
   │
   ▼
Agent implementation runs tools (read_document, rag_search, extract_fields, run_validation)
   │
   ├─ LLM configured ──► prompt-based execution (JSON output contract)
   │
   └─ Sovereign mode  ──► deterministic rule-based engines (same output shape)
   │
   ▼
Execution log + structured result (timing, mode, status)
```

| Agent | Input | Tools | Output |
|---|---|---|---|
| Document Analysis | `document_id` | read, extract_fields, rag_search | fields, entities, structure, statistics |
| Summarization | `document_id`, `length` | read, rag_search | summary, key_points, word_count |
| Research | `question`, `document_ids?` | rag_search | grounded answer + sources + related topics |
| Validation | `document_id` | read, run_validation | status, score, issues, explanation, actions |
| Task/Code | `prompt`, `language` | generate_code, sandbox_run | code (executed ONLY in the Sandbox) |

## Security

- **No secrets in the frontend** — API keys are server-side environment variables only.
- **Upload validation** — extension allow-list, size cap, magic-byte checks (PDF/PNG/JPEG/DOCX).
- **Optional API auth** — set `ACCESS_TOKEN`; every request then needs a Bearer token.
- **CORS allow-list** — only the configured frontend origin.
- **Prompt-injection guardrails** — document text is treated as data, not instructions;
  the grounding prompt explicitly forbids following instruction-like content.
- **Sandbox isolation** — untrusted code runs in a throwaway temp dir with timeout,
  memory/CPU rlimits (POSIX), blocked system imports (`os`, `subprocess`, `sys`, …),
  stripped environment; optional Docker executor with `--network none`.
- **Safe errors** — no stack traces leak to clients; unhandled errors return a generic 500.
- **Audit logging** — every upload/process/index/query/agent/sandbox/validation action
  is recorded and shown on the dashboard.
- **Local-only AI / no outbound calls** — the LLM resolver refuses non-loopback endpoints
  (an API key alone can never dial a cloud provider), embeddings always run locally, and
  Chroma product telemetry is disabled (`ANONYMIZED_TELEMETRY=false`).
- **No runtime downloads** — the embedding model is used only from the local cache; if it
  is absent the app falls back to zero-download hashing embeddings instead of fetching it.
- **Non-root runtime** in Docker.

## Offline operation & data sovereignty

The workbench is designed to run **completely offline** once installed, and to keep every
document, embedding, vector, query and response on the machine:

- **No cloud AI APIs** — OpenAI, Gemini, Claude, Azure OpenAI and other hosted services are
  never called. `resolve_llm()` only ever returns the built-in grounded engine or a client
  for an endpoint you explicitly configured via `OPENAI_BASE_URL`, which must point at the
  loopback interface unless you set `ALLOW_REMOTE_LLM=true`.
- **Local LLM (optional)** — install Ollama (`ollama pull llama3.1:8b`) or start LM
  Studio/vLLM/llama.cpp on the same machine, then set `LLM_PROVIDER=ollama` and
  `OPENAI_BASE_URL=http://127.0.0.1:11434/v1`. Without any of this the built-in grounded
  engine already answers from your documents with citations.
- **Local embeddings** — ONNX `all-MiniLM-L6-v2` runs on-device from the local cache
  (`~/.cache/chroma/onnx_models/…`). The app **never downloads it at runtime**: provision
  it once while online with `python backend/scripts/embed_setup.py` (the Docker image
  bakes it in at build time), or run with `EMBEDDINGS_PROVIDER=hash` for a zero-model,
  fully-offline mode.
- **Local vector store** — Chroma persists to disk on the machine (`./data/chroma`); no
  hosted vector service is used.
- **Local OCR & database** — Tesseract runs on-device; SQLite (local dev) or PostgreSQL 16
  (in the Docker Compose stack, on this machine) store metadata.
- **Frontend** — a static SPA served locally; it talks only to the local FastAPI backend.
  There are no CDN scripts or external font hosts.
- **Verified by tests** — `tests/test_offline.py` locks in these guarantees (cloud URLs
  refused, API key alone never enables a provider, telemetry off, no-download fallback).

## Testing

```bash
cd backend
python -m pytest                 # 85 tests (4 OCR tests skip without Tesseract)
```

Coverage by area:

| Area | Test file |
|---|---|
| File upload & security (magic bytes, sizes, auth) | `tests/test_api.py` |
| Document processing pipeline (API) | `tests/test_api.py` |
| Text extraction (TXT/DOCX/PDF/cleaning) | `tests/test_extraction.py` |
| OCR (skipped without Tesseract) | `tests/test_ocr.py` |
| Chunking | `tests/test_chunking.py` |
| Embeddings (determinism, fallback) | `tests/test_embeddings.py` |
| Vector search (in-memory + Chroma integration) | `tests/test_vectorstore.py` |
| RAG & source citations & anti-hallucination | `tests/test_rag.py` |
| Validation rules | `tests/test_validation.py` |
| Agents (registry, all five agents) | `tests/test_agents.py` |
| Sandbox (execution, blocking, timeout) | `tests/test_sandbox.py` |
| API endpoints (all routers) | `tests/test_api.py` |
| Offline/local-only guarantees (cloud refused, telemetry off, no-download) | `tests/test_offline.py` |

Frontend is verified with `npm run build` (strict TypeScript + production build).

## End-to-end demo

A 20-step flow that works out of the box (see also [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)):

1. Open the Dashboard.
2. Click **“Load sample document”** (or upload a land record — PDF/DOCX/TXT/image).
3. The system validates the file (type, size, magic bytes).
4. Text is extracted (PDF text layer → direct; scanned → OCR).
5. OCR runs automatically when the document is scanned.
6. Text is cleaned and chunked (900 chars, 120 overlap, page-tracked).
7. Embeddings are generated (local, no key).
8. Vectors are stored in Chroma.
9. Open **RAG Chat**.
10. Ask, e.g., *“Who is the registered owner?”*.
11. The retriever finds the relevant chunk.
12. The answer is grounded in the document (LLM or built-in engine).
13. The UI shows the answer **with source cards** (document, page, chunk, similarity).
14. Open **Validation**, pick the document, run checks.
15. Missing/inconsistent fields are reported with severity and a compliance score.
16. Open **AI Agents**.
17. Run the **Document Analysis** (or Summarization / Research) agent.
18. Structured results are displayed with an execution log.
19. Open **Sandbox** and execute the Task Agent's code — isolated, timed, logged.
20. Dashboard statistics update in real time.

Bundled sample documents (`backend/samples/`):

- `land_record.txt` — clean, fully valid record (RAG answers all demo questions).
- `land_record_with_issues.txt` — contains missing district, N/A area, duplicated record
  number, future date → demonstrates `Invalid` validation.
- `.pdf`, `.docx`, `_scanned.png`, `_scanned.pdf` — same records in other formats
  (scanned versions demo OCR).

## SIH presentation / demo flow

See [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — a timed, presenter-friendly script covering
the problem, the architecture diagram walkthrough, the 20-step live demo, and the security
deep-dive talking points.

## Known limitations

- **OCR quality** depends on the engine and scan quality. Tesseract (Docker image)
  offers multi-language trained data (Hindi/Marathi); on hosts without Tesseract the
  pure-Python RapidOCR/ONNX fallback reads English documents fully offline. Multi-lingual
  accuracy can be improved with custom trained data.
- **Rule-based validation** targets land-record style documents; other document types
  need their own field patterns (the rules are easy to extend).
- **Embedding quality** in `hash` fallback mode is weaker than ONNX MiniLM; the default
  `auto` mode uses MiniLM and only falls back when the model cannot be loaded.
- **Sandbox** subprocess mode is hardened but not a full OS container; production
  deployments should set `SANDBOX_EXECUTOR=docker`.
- **No multi-user authentication/authorization** yet — the optional API token gates the
  API, but there is no per-user role model.
- Frontend currently polls for pipeline progress rather than using websockets/SSE.

## Future scope

- **On-prem LLM by default** — pre-bundled Ollama service in Compose (`llama3.1`/`qwen2.5`)
  so even the LLM tier is 100% sovereign out of the box.
- **Qdrant / pgvector** backends behind the existing `VectorStore` interface.
- **Multi-language OCR** with UDISE-trained Tesseract models; native Hindi/Marathi RAG.
- **RBAC & SSO** (Keycloak/LDAP), per-department document namespaces, audit exports.
- **Streaming chat (SSE)**, document versioning, batch ingestion of folder archives.
- **More agents** — e.g. Cross-record Anomaly Detection, GIS-linked Land Parcel agent,
  Dispute/Litigation Triage agent; agent-to-agent orchestration.
- **Evaluation harness** — golden-question sets, RAGAS-style retrieval/grounding scores,
  validation-rule coverage reports.
- **Digital-signature verification** of records and tamper-evident hash chains.

---

Built with ❤️ for **Smart India Hackathon 2026 · SIH117** — sovereign, private,
document-grounded AI for the nation.