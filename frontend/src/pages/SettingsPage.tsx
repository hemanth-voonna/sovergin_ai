import { useEffect, useState } from "react";
import { Bot, Cpu, Database, KeyRound, Lock, ScanText, Server, ShieldCheck } from "lucide-react";
import { api, ApiError, getToken, setToken } from "../api";
import type { SettingsInfo } from "../types";
import { Alert, Spinner, useToast } from "../components/ui";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2.5 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="max-w-[60%] truncate text-right text-sm font-medium text-slate-800">{value}</span>
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <h3 className="mb-3 flex items-center gap-2 font-semibold text-slate-800">{icon}{title}</h3>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const [s, setS] = useState<SettingsInfo | null>(null);
  const [services, setServices] = useState<Record<string, string>>({});
  const [token, setTokenState] = useState(getToken());
  const [err, setErr] = useState("");
  const { push } = useToast();

  useEffect(() => {
    api.settings().then(setS).catch((e: ApiError) => setErr(e.message));
    api.health().then((h) => setServices((h.services as Record<string, string>) ?? {})).catch(() => {});
  }, []);

  const saveToken = () => {
    setToken(token.trim());
    push("success", token.trim() ? "API token saved for this session (stored only in your browser)." : "Token cleared.");
  };

  if (err && !s) return <Alert kind="error" title="Backend unreachable">{err}</Alert>;
  if (!s) return <Spinner label="Loading settings…" />;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Section icon={<Bot className="h-4 w-4 text-brand-600" />} title="Large Language Model">
        <Row label="Provider" value={s.llm_provider} />
        <Row label="Model" value={s.llm_model} />
        <Row
          label="Status"
          value={s.llm_configured
            ? <span className="badge bg-emerald-100 text-emerald-700">external LLM connected</span>
            : <span className="badge bg-amber-100 text-amber-700">sovereign mode (built-in grounded engine)</span>}
        />
        <p className="mt-3 text-xs leading-relaxed text-slate-400">
          Configure via environment: <code className="rounded bg-slate-100 px-1">LLM_PROVIDER</code> (auto | mock | openai | ollama),{" "}
          <code className="rounded bg-slate-100 px-1">LLM_MODEL</code>,{" "}
          <code className="rounded bg-slate-100 px-1">OPENAI_API_KEY</code>,{" "}
          <code className="rounded bg-slate-100 px-1">OPENAI_BASE_URL</code>. Works with Ollama, vLLM, LM Studio and OpenAI-compatible APIs.
        </p>
      </Section>

      <Section icon={<Cpu className="h-4 w-4 text-brand-600" />} title="Embeddings & RAG">
        <Row label="Embedding provider" value={s.embedding_provider} />
        <Row label="Embedding model" value={s.embedding_model} />
        <Row label="Vector database" value={s.vector_db} />
        <Row label="Chunk size / overlap" value={`${s.chunk_size} / ${s.chunk_overlap}`} />
        <Row label="Default top-k" value={s.top_k} />
        <p className="mt-3 text-xs leading-relaxed text-slate-400">
          Embeddings run locally (Chroma ONNX, no API key) with an automatic offline fallback. The
          vector layer is modular — Chroma today, Qdrant / pgvector tomorrow.
        </p>
      </Section>

      <Section icon={<ScanText className="h-4 w-4 text-brand-600" />} title="OCR">
        <Row label="Engine" value="Tesseract (pytesseract)" />
        <Row label="Language" value={s.ocr_lang} />
        <Row label="Availability" value={String(services.ocr ?? "unknown")} />
      </Section>

      <Section icon={<Server className="h-4 w-4 text-brand-600" />} title="Uploads & Sandbox">
        <Row label="Max upload size" value={`${s.max_upload_mb} MB`} />
        <Row label="Allowed types" value="pdf, docx, txt, png, jpg, jpeg" />
        <Row label="Sandbox executor" value={s.sandbox_executor} />
        <p className="mt-3 text-xs leading-relaxed text-slate-400">
          Uploads are validated by extension, size and magic bytes. Code execution is sandboxed with
          timeouts, memory/CPU limits and optional Docker isolation (no network).
        </p>
      </Section>

      <Section icon={<Lock className="h-4 w-4 text-brand-600" />} title="Access control">
        <Row label="API authentication" value={s.auth_enabled
          ? <span className="badge bg-emerald-100 text-emerald-700">enabled (Bearer token)</span>
          : <span className="badge bg-slate-100 text-slate-500">disabled — trusted network</span>} />
        <div className="mt-3">
          <label className="label">Session API token (browser-local)</label>
          <div className="flex gap-2">
            <input className="input" type="password" placeholder="Only needed if ACCESS_TOKEN is set on the server"
              value={token} onChange={(e) => setTokenState(e.target.value)} />
            <button className="btn-secondary shrink-0" onClick={saveToken}><KeyRound className="h-4 w-4" /> Save</button>
          </div>
          <p className="mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-slate-400">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
            Secrets live only in server-side environment variables — never in the frontend bundle.
            Set <code className="rounded bg-slate-100 px-1">ACCESS_TOKEN</code> in <code className="rounded bg-slate-100 px-1">.env</code> to require a token on every API call.
          </p>
        </div>
      </Section>

      <Section icon={<Database className="h-4 w-4 text-brand-600" />} title="Services health">
        <div className="flex flex-wrap gap-2">
          {Object.entries(services).map(([name, state]) => (
            <span key={name} className={`badge ${String(state).startsWith("unavailable") ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
              {name}: {String(state).slice(0, 30)}
            </span>
          ))}
        </div>
      </Section>
    </div>
  );
}