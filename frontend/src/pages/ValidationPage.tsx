import { useEffect, useState } from "react";
import { Bot, CheckCircle2, ClipboardCheck, Loader2, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { api, ApiError } from "../api";
import type { AgentRun, DocumentItem, ValidationResult } from "../types";
import { Alert, EmptyState, Spinner, formatDuration, useToast } from "../components/ui";

export default function ValidationPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [docId, setDocId] = useState("");
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState<AgentRun | null>(null);
  const { push } = useToast();

  useEffect(() => {
    api.listDocuments().then((r) => setDocs(r.items)).catch((e: ApiError) => push("error", e.message));
  }, [push]);

  const processed = docs.filter((d) => d.status === "processed" || d.status === "indexed");

  const check = async (id?: string) => {
    const target = id ?? docId;
    if (!target) return;
    setBusy(true);
    setResult(null);
    setExplanation(null);
    try {
      setResult(await api.validate(target));
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  };

  const explain = async () => {
    if (!docId) return;
    setExplaining(true);
    try {
      setExplanation(await api.runAgent("validation", { document_id: docId }));
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Agent failed");
    } finally {
      setExplaining(false);
    }
  };

  const statusIcon = result?.status === "valid" ? <CheckCircle2 className="h-6 w-6" /> :
    result?.status === "invalid" ? <ShieldX className="h-6 w-6" /> :
    <ShieldAlert className="h-6 w-6" />;

  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-end gap-3 p-5">
        <div className="min-w-64 flex-1">
          <label className="label">Document to validate</label>
          <select className="input" value={docId} onChange={(e) => { setDocId(e.target.value); setResult(null); }}>
            <option value="">— select a processed document —</option>
            {processed.map((d) => (
              <option key={d.id} value={d.id}>{d.original_name}</option>
            ))}
          </select>
        </div>
        <button className="btn-primary" disabled={busy || !docId} onClick={() => check()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardCheck className="h-4 w-4" />}
          Run validation checks
        </button>
      </div>

      {processed.length === 0 && (
        <Alert kind="info" title="Nothing to validate yet">Process a document first (Documents page).</Alert>
      )}

      {result && (
        <>
          <div className={`card flex flex-wrap items-center gap-4 p-5 ${
            result.status === "valid" ? "border-emerald-200 bg-emerald-50" :
            result.status === "invalid" ? "border-rose-200 bg-rose-50" : "border-amber-200 bg-amber-50"
          }`}>
            <div className={`flex h-12 w-12 items-center justify-center rounded-full ${
              result.status === "valid" ? "bg-emerald-100 text-emerald-600" :
              result.status === "invalid" ? "bg-rose-100 text-rose-600" : "bg-amber-100 text-amber-600"
            }`}>
              {statusIcon}
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold capitalize text-slate-800">{result.status}</h3>
              <p className="text-sm text-slate-500">
                {result.issues.length} issue(s) found · {formatDuration(result.took_ms)}
              </p>
            </div>
            <div className="w-40">
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>Compliance score</span>
                <span className="font-bold">{result.score}/100</span>
              </div>
              <div className="h-2.5 rounded-full bg-white">
                <div className={`h-2.5 rounded-full ${
                  result.score >= 80 ? "bg-emerald-500" : result.score >= 50 ? "bg-amber-500" : "bg-rose-500"
                }`} style={{ width: `${result.score}%` }} />
              </div>
            </div>
            <button className="btn-secondary" disabled={explaining} onClick={explain}>
              {explaining ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
              Explain with Validation Agent
            </button>
          </div>

          {explanation && (
            <div className="card p-5">
              <div className="mb-2 flex items-center gap-2">
                <h4 className="font-semibold text-slate-800">Agent explanation</h4>
                <span className="badge bg-slate-100 text-slate-500">{explanation.mode}</span>
              </div>
              {typeof explanation.output.explanation === "string" && (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-600">{String(explanation.output.explanation)}</p>
              )}
              {Array.isArray(explanation.output.recommended_actions) && (
                <ul className="mt-3 space-y-1 text-sm text-slate-600">
                  {(explanation.output.recommended_actions as string[]).map((a, i) => (
                    <li key={i} className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />{a}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            <div className="card p-5">
              <h4 className="mb-3 font-semibold text-slate-800">Issues ({result.issues.length})</h4>
              {result.issues.length === 0 ? (
                <p className="text-sm text-slate-400">No issues — the record is complete and consistent.</p>
              ) : (
                <div className="space-y-2">
                  {result.issues.map((iss, i) => (
                    <div key={i} className={`rounded-lg border px-3 py-2.5 text-sm ${
                      iss.severity === "error" ? "border-rose-200 bg-rose-50" :
                      iss.severity === "warning" ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50"
                    }`}>
                      <div className="mb-0.5 flex flex-wrap items-center gap-1.5">
                        <span className={`badge ${iss.severity === "error" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"}`}>
                          {iss.severity}
                        </span>
                        <span className="badge bg-white/70 text-slate-500">{iss.category}</span>
                        {iss.field && <span className="badge bg-white/70 text-slate-500">{iss.field}</span>}
                      </div>
                      <p className="text-[13px] text-slate-600">{iss.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="card p-5">
              <h4 className="mb-3 font-semibold text-slate-800">Extracted fields</h4>
              {Object.keys(result.fields).length === 0 ? (
                <p className="text-sm text-slate-400">No known fields detected in this text.</p>
              ) : (
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-slate-100">
                    {Object.entries(result.fields).map(([k, v]) => (
                      <tr key={k}>
                        <td className="py-1.5 pr-2 font-medium capitalize text-slate-500">{k.replace(/_/g, " ")}</td>
                        <td className="py-1.5 text-slate-800">{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}

      {!result && !busy && (
        <EmptyState
          icon={<ShieldCheck className="h-8 w-8 text-slate-300" />}
          title="Run a validation"
          hint="Checks required fields, formats, consistency, duplicates and suspicious values, then rates the record Valid / Warning / Invalid."
        />
      )}
      {busy && <Spinner label="Running validation rules…" />}
    </div>
  );
}