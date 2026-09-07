import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot,
  Compass,
  FileSearch,
  FileText,
  Play,
  ShieldCheck,
  Terminal,
  TerminalSquare,
} from "lucide-react";
import { api, ApiError } from "../api";
import type { AgentInfo, AgentRun, DocumentItem } from "../types";
import { Alert, Spinner, formatDuration, useToast } from "../components/ui";

const ICONS: Record<string, React.ReactNode> = {
  search: <FileSearch className="h-5 w-5" />,
  "file-text": <FileText className="h-5 w-5" />,
  compass: <Compass className="h-5 w-5" />,
  "shield-check": <ShieldCheck className="h-5 w-5" />,
  terminal: <Terminal className="h-5 w-5" />,
};

export default function Agents() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [run, setRun] = useState<AgentRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const { push } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    api.listAgents().then(setAgents).catch((e: ApiError) => setErr(e.message));
    api.listDocuments().then((r) => setDocs(r.items)).catch(() => {});
  }, []);

  const selected = agents.find((a) => a.id === selectedId) ?? null;

  const select = (id: string) => {
    setSelectedId(id);
    setRun(null);
    setInputs({});
  };

  const runAgent = async () => {
    if (!selected) return;
    setBusy(true);
    setRun(null);
    try {
      const payload: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(inputs)) {
        if (key === "document_ids") {
          payload[key] = value.split(",").map((s) => s.trim()).filter(Boolean);
        } else {
          payload[key] = value;
        }
      }
      const result = await api.runAgent(selected.id, payload);
      setRun(result);
      push(result.status === "completed" ? "success" : "error",
        result.status === "completed" ? `Agent finished (${result.mode})` : result.output?.error as string ?? "Agent failed");
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Agent run failed");
    } finally {
      setBusy(false);
    }
  };

  const processedDocs = docs.filter((d) => d.status === "processed" || d.status === "indexed");
  const indexedDocs = docs.filter((d) => d.status === "indexed");

  if (err && agents.length === 0) return <Alert kind="error" title="Backend unreachable">{err}</Alert>;

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-500">
        Five specialised agents, one registry. Each agent has declared inputs, tools and an output
        contract, and works with or without an external LLM (sovereign mode uses deterministic
        rule-based engines).
      </p>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((a) => (
          <button
            key={a.id}
            onClick={() => select(a.id)}
            className={`card cursor-pointer p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md ${
              selectedId === a.id ? "ring-2 ring-brand-500" : ""
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                {ICONS[a.icon] ?? <Bot className="h-5 w-5" />}
              </div>
              <span className="badge bg-slate-100 text-slate-500">{a.category}</span>
            </div>
            <h3 className="mt-3 font-semibold text-slate-800">{a.name}</h3>
            <p className="mt-1 line-clamp-3 text-sm text-slate-500">{a.description}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {a.tools.map((t) => (
                <span key={t} className="badge bg-slate-50 text-slate-500 ring-1 ring-slate-200">{t}</span>
              ))}
            </div>
          </button>
        ))}
      </div>

      {selected && (
        <div className="card p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="font-semibold text-slate-800">{selected.name}</h3>
              <p className="text-sm text-slate-500">{selected.output}</p>
            </div>
            <span className="badge bg-slate-100 text-slate-500">
              {selected.requires_llm ? "requires LLM" : "works offline"}
            </span>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {Object.entries(selected.input_schema.properties ?? {}).map(([key, prop]) => (
              <div key={key}>
                <label className="label">{key.replace(/_/g, " ")}</label>
                {key === "document_id" ? (
                  <select className="input" value={inputs[key] ?? ""} onChange={(e) => setInputs({ ...inputs, [key]: e.target.value })}>
                    <option value="">— select a processed document —</option>
                    {processedDocs.map((d) => (
                      <option key={d.id} value={d.id}>{d.original_name}</option>
                    ))}
                  </select>
                ) : key === "document_ids" ? (
                  <select className="input" multiple value={(inputs[key] ?? "").split(",").filter(Boolean)}
                    onChange={(e) => setInputs({ ...inputs, [key]: [...e.target.selectedOptions].map((o) => o.value).join(",") })}>
                    {indexedDocs.map((d) => (
                      <option key={d.id} value={d.id}>{d.original_name}</option>
                    ))}
                  </select>
                ) : prop.enum ? (
                  <select className="input" value={inputs[key] ?? prop.default ?? ""} onChange={(e) => setInputs({ ...inputs, [key]: e.target.value })}>
                    {prop.enum.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                  </select>
                ) : (
                  <textarea
                    className="input min-h-20"
                    placeholder={prop.description ?? key}
                    value={inputs[key] ?? ""}
                    onChange={(e) => setInputs({ ...inputs, [key]: e.target.value })}
                  />
                )}
              </div>
            ))}
          </div>

          <button className="btn-primary mt-4" disabled={busy} onClick={runAgent}>
            {busy ? <Spinner /> : <Play className="h-4 w-4" />}
            {busy ? "Agent working…" : `Run ${selected.name}`}
          </button>

          {run && (
            <div className="mt-5 space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className={`badge ${run.status === "completed" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
                  {run.status}
                </span>
                <span className="badge bg-slate-100 text-slate-500">mode: {run.mode}</span>
                <span className="text-xs text-slate-400">{formatDuration(run.took_ms)}</span>
              </div>
              {run.logs.length > 0 && (
                <div>
                  <p className="label">Execution log</p>
                  <div className="codeblock max-h-36 overflow-auto text-xs">
                    {run.logs.map((l, i) => <div key={i}>$ {l}</div>)}
                  </div>
                </div>
              )}
              <AgentOutput run={run} onRunInSandbox={(code) => {
                localStorage.setItem("sovereignai_sandbox_draft", code);
                navigate("/sandbox");
              }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AgentOutput({ run, onRunInSandbox }: { run: AgentRun; onRunInSandbox: (code: string) => void }) {
  const out = run.output;
  const code = typeof out.code === "string" ? out.code : "";
  const issues = Array.isArray(out.issues) ? out.issues as { severity: string; category: string; message: string }[] : [];
  const sources = Array.isArray(out.sources) ? out.sources as { filename: string; page: number | null }[] : [];

  if (code) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="label mb-0">Generated code ({String(out.language ?? "python")})</p>
          <button className="btn-secondary px-2.5 py-1.5" onClick={() => onRunInSandbox(code)}>
            <TerminalSquare className="h-4 w-4" /> Run in Sandbox
          </button>
        </div>
        <pre className="codeblock max-h-80 overflow-auto text-[12.5px]">{code}</pre>
        {typeof out.notes === "string" && <p className="text-xs text-slate-400">{out.notes}</p>}
      </div>
    );
  }

  if (issues.length > 0 || typeof out.status === "string") {
    return (
      <div className="space-y-2">
        <p className="label">Validation findings</p>
        {typeof out.explanation === "string" && <p className="text-sm text-slate-600">{out.explanation}</p>}
        <div className="max-h-64 space-y-1.5 overflow-y-auto">
          {issues.map((iss, i) => (
            <div key={i} className={`rounded-lg border px-3 py-2 text-sm ${
              iss.severity === "error" ? "border-rose-200 bg-rose-50 text-rose-700" :
              iss.severity === "warning" ? "border-amber-200 bg-amber-50 text-amber-700" :
              "border-slate-200 bg-slate-50 text-slate-600"
            }`}>
              <span className="mr-1.5 font-semibold uppercase text-xs">{iss.severity}</span>
              <span className="badge mr-1.5 bg-white/60">{iss.category}</span>
              {iss.message}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (typeof out.answer === "string") {
    return (
      <div className="space-y-2">
        <p className="label">Research findings</p>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-relaxed text-slate-700">
          {String(out.answer)}
        </div>
        {sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {sources.map((s, i) => (
              <span key={i} className="badge bg-brand-50 text-brand-700 ring-1 ring-brand-100">
                {s.filename}{s.page ? ` · p.${s.page}` : ""}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <p className="label">Agent output</p>
      <pre className="codeblock max-h-96 overflow-auto text-[12.5px]">{JSON.stringify(out, null, 2)}</pre>
    </div>
  );
}