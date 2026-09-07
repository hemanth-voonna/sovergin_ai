import { useEffect, useState } from "react";
import { Braces, Loader2, Play, RefreshCw, ShieldCheck, Terminal, Trash2 } from "lucide-react";
import { api } from "../api";
import type { SandboxResult } from "../types";
import { EmptyState, Spinner, formatDuration, useToast } from "../components/ui";

const SAMPLES: Record<string, string> = {
  "Python: hello sandbox": `print("SovereignAI secure sandbox")
print("6 * 7 =", 6 * 7)
for i in range(3):
    print(f"tick {i}")`,
  "Python: word statistics": `import sys
import re

text = sys.stdin.read() if not sys.stdin.isatty() else "SovereignAI — secure document processing"
words = re.findall(r"[a-zA-Z0-9']+", text)
print(f"characters: {len(text)}")
print(f"words: {len(words)}")
print(f"unique: {len(set(w.lower() for w in words))}")`,
  "Python: compute primes": `def primes(n):
    out = []
    for num in range(2, n):
        if all(num % d for d in range(2, int(num**0.5) + 1)):
            out.append(num)
    return out

print("primes under 30:", primes(30))`,
  "Bash: inspect workspace": `echo "working directory: $(pwd)"
echo "files here: $(ls -1 | wc -l)"
echo "date: $(date)"`,
};

const DEFAULT_CODE = SAMPLES["Python: hello sandbox"];

export default function SandboxPage() {
  const [code, setCode] = useState(DEFAULT_CODE);
  const [language, setLanguage] = useState("python");
  const [timeout, setTimeoutSec] = useState(10);
  const [memory, setMemory] = useState(256);
  const [result, setResult] = useState<SandboxResult | null>(null);
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  useEffect(() => {
    const draft = localStorage.getItem("sovereignai_sandbox_draft");
    if (draft) {
      setCode(draft);
      localStorage.removeItem("sovereignai_sandbox_draft");
    }
  }, []);

  const run = async () => {
    if (!code.trim() || busy) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await api.sandboxRun(code, language, timeout, memory);
      setResult(res);
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Sandbox run failed");
    } finally {
      setBusy(false);
    }
  };

  const pickSample = (key: string) => {
    setCode(SAMPLES[key] ?? "");
    setLanguage(key.startsWith("Bash") ? "bash" : "python");
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
      {/* Editor */}
      <div className="card flex flex-col overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-brand-600" />
            <span className="text-sm font-semibold text-slate-700">Untrusted code — runs in isolation</span>
          </div>
          <div className="flex items-center gap-1.5">
            <select className="input !w-auto !px-2 !py-1.5" value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="python">python</option>
              <option value="bash">bash</option>
            </select>
            <button className="btn-secondary px-2.5 py-1.5" title="Reset" onClick={() => setCode(DEFAULT_CODE)}>
              <RefreshCw className="h-4 w-4" />
            </button>
            <button className="btn-secondary px-2.5 py-1.5 text-rose-600" title="Clear" onClick={() => setCode("")}>
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
        <textarea
          className="min-h-[380px] flex-1 resize-none bg-slate-950 p-4 font-mono text-[13px] leading-relaxed text-slate-100 outline-none placeholder:text-slate-600"
          spellCheck={false}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="# write or paste code here — it will be executed in the SovereignAI sandbox"
        />
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 px-4 py-3">
          <label className="flex items-center gap-1.5 text-xs text-slate-500">
            timeout
            <input type="number" min={1} max={60} value={timeout}
              onChange={(e) => setTimeoutSec(Number(e.target.value))}
              className="input !w-16 !px-2 !py-1" />
            s
          </label>
          <label className="flex items-center gap-1.5 text-xs text-slate-500">
            memory
            <input type="number" min={16} max={1024} value={memory}
              onChange={(e) => setMemory(Number(e.target.value))}
              className="input !w-20 !px-2 !py-1" />
            MB
          </label>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden items-center gap-1 text-xs text-slate-400 sm:flex">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" /> no network · no host FS · hard limits
            </span>
            <button className="btn-primary" disabled={busy || !code.trim()} onClick={run}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {busy ? "Running…" : "Run in sandbox"}
            </button>
          </div>
        </div>
      </div>

      {/* Results + samples */}
      <div className="space-y-4">
        <div className="card p-4">
          <p className="label">Sample snippets</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.keys(SAMPLES).map((k) => (
              <button key={k} onClick={() => pickSample(k)}
                className="badge cursor-pointer border border-slate-200 bg-white px-2.5 py-1.5 text-slate-600 hover:border-brand-300 hover:text-brand-700">
                {k}
              </button>
            ))}
          </div>
        </div>

        {busy && <div className="card p-4"><Spinner label="Executing in sandbox…" /></div>}

        {result && (
          <div className="card overflow-hidden">
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-3">
              <StatusPill status={result.status} />
              {result.exit_code !== null && <span className="badge bg-slate-100 text-slate-500">exit {result.exit_code}</span>}
              <span className="badge bg-slate-100 text-slate-500">{formatDuration(result.duration_ms)}</span>
            </div>
            <div className="space-y-3 p-4">
              {result.stdout && (
                <div>
                  <p className="label !text-emerald-600">stdout</p>
                  <pre className="codeblock max-h-56 overflow-auto whitespace-pre-wrap bg-slate-900">{result.stdout}</pre>
                </div>
              )}
              {result.stderr && (
                <div>
                  <p className="label !text-rose-500">stderr</p>
                  <pre className="codeblock max-h-40 overflow-auto whitespace-pre-wrap bg-rose-950 text-rose-100">{result.stderr}</pre>
                </div>
              )}
              <div>
                <p className="label">sandbox log</p>
                <div className="rounded-lg bg-slate-100 px-3 py-2 font-mono text-xs text-slate-500">
                  {result.log.map((l, i) => <div key={i}>{l}</div>)}
                </div>
              </div>
            </div>
          </div>
        )}

        {!result && !busy && (
          <EmptyState
            icon={<Braces className="h-8 w-8 text-slate-300" />}
            title="Nothing executed yet"
            hint="Generated code from the Task Agent lands here automatically. Execution happens in a throwaway sandbox — never on the host."
          />
        )}
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-700",
    timed_out: "bg-amber-100 text-amber-700",
    error: "bg-rose-100 text-rose-700",
    killed: "bg-rose-100 text-rose-700",
  };
  return <span className={`badge ${styles[status] ?? "bg-slate-100 text-slate-600"}`}>{status}</span>;
}