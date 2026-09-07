import { useEffect, useRef, useState } from "react";
import { FileText, MessageSquareText, Send, ShieldAlert, ShieldCheck, Sparkles } from "lucide-react";
import { api, ApiError } from "../api";
import type { DocumentItem, SourceOut } from "../types";
import { Alert, Spinner, formatDuration, useToast } from "../components/ui";

const SUGGESTIONS = [
  "Who is the registered owner?",
  "What is the survey number?",
  "What is the land area?",
  "Which village does the land belong to?",
  "What is the document date?",
  "What is the record number?",
];

interface Message {
  role: "user" | "assistant";
  content: string;
  grounded?: boolean;
  sources?: SourceOut[];
  model?: string;
  took_ms?: number;
}

export default function RagChat() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [topK, setTopK] = useState(5);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const [loadErr, setLoadErr] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const { push } = useToast();

  useEffect(() => {
    api
      .listDocuments()
      .then((r) => {
        setDocs(r.items);
        // default: only indexed docs
        const indexed = r.items.filter((d) => d.status === "indexed");
        setSelected(new Set(indexed.map((d) => d.id)));
      })
      .catch((e: ApiError) => setLoadErr(e.message));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const ask = async (q?: string) => {
    const text = (q ?? question).trim();
    if (!text || thinking) return;
    setQuestion("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setThinking(true);
    try {
      const answer = await api.ragQuery(text, selected.size ? [...selected] : undefined, topK);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: answer.answer,
          grounded: answer.grounded,
          sources: answer.sources,
          model: answer.model,
          took_ms: answer.took_ms,
        },
      ]);
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Query failed");
      setMessages((m) => [...m, { role: "assistant", content: "⚠ Query failed — please try again." }]);
    } finally {
      setThinking(false);
    }
  };

  const indexedDocs = docs.filter((d) => d.status === "indexed");

  return (
    <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
      {/* Sidebar: sources */}
      <aside className="space-y-4">
        <div className="card p-4">
          <p className="label">Answer from documents</p>
          {docs.length === 0 ? (
            <p className="text-sm text-slate-400">No documents uploaded yet.</p>
          ) : (
            <div className="max-h-72 space-y-1.5 overflow-y-auto">
              {docs.map((d) => (
                <label key={d.id} className={`flex cursor-pointer items-start gap-2 rounded-lg border px-2.5 py-2 text-sm ${selected.has(d.id) ? "border-brand-300 bg-brand-50" : "border-slate-200 hover:bg-slate-50"}`}>
                  <input type="checkbox" checked={selected.has(d.id)} onChange={() => toggle(d.id)} className="mt-0.5 accent-brand-600" />
                  <span className="min-w-0">
                    <span className="block truncate text-slate-700">{d.original_name}</span>
                    <span className="text-[11px] text-slate-400">
                      {d.status === "indexed" ? `${d.chunk_count} chunks indexed` : "not indexed"}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          )}
          {indexedDocs.length === 0 && (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-600">
              <ShieldAlert className="h-3.5 w-3.5" /> Nothing indexed yet — process a document first.
            </p>
          )}
          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-slate-400">Top-k retrieval</span>
            <select value={topK} onChange={(e) => setTopK(Number(e.target.value))} className="input !w-16 !px-2 !py-1">
              {[3, 5, 8, 10].map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
        </div>
        <div className="card p-4">
          <p className="label">Try asking</p>
          <div className="flex flex-col gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => ask(s)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-left text-xs text-slate-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700">
                {s}
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* Chat */}
      <div className="card flex max-h-[calc(100vh-8.5rem)] flex-col">
        {loadErr ? (
          <div className="p-4"><Alert kind="error" title="Backend unreachable">{loadErr}</Alert></div>
        ) : messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
              <MessageSquareText className="h-7 w-7" />
            </div>
            <h3 className="text-lg font-semibold text-slate-800">Grounded RAG chat</h3>
            <p className="max-w-md text-sm text-slate-400">
              Ask questions about your uploaded documents. Answers are grounded in retrieved
              passages with citations — the system refuses to invent facts it cannot find.
            </p>
            <div className="mt-2 flex max-w-lg flex-wrap justify-center gap-2">
              {SUGGESTIONS.slice(0, 4).map((s) => (
                <button key={s} onClick={() => ask(s)} className="badge cursor-pointer border border-brand-200 bg-brand-50 px-3 py-1.5 text-brand-700 hover:bg-brand-100">
                  <Sparkles className="h-3 w-3" /> {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] ${m.role === "user" ? "" : "w-full"}`}>
                  {m.role === "user" ? (
                    <div className="rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-sm text-white shadow-sm">
                      {m.content}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className={`rounded-2xl rounded-bl-md border px-4 py-3 text-sm leading-relaxed shadow-sm ${
                        m.grounded ? "border-slate-200 bg-white text-slate-700" : "border-amber-200 bg-amber-50 text-amber-800"
                      }`}>
                        <div className="mb-1.5 flex flex-wrap items-center gap-2">
                          {m.grounded ? (
                            <span className="badge bg-emerald-100 text-emerald-700"><ShieldCheck className="h-3 w-3" /> grounded</span>
                          ) : (
                            <span className="badge bg-amber-100 text-amber-700"><ShieldAlert className="h-3 w-3" /> not found in corpus</span>
                          )}
                          <span className="text-[11px] text-slate-400">
                            {m.model} · {m.took_ms !== undefined ? formatDuration(m.took_ms) : ""}
                          </span>
                        </div>
                        <p className="whitespace-pre-wrap">{m.content}</p>
                      </div>
                      {m.sources && m.sources.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                            Sources ({m.sources.length})
                          </p>
                          {m.sources.slice(0, 3).map((s, j) => (
                            <SourceCard key={j} source={s} />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {thinking && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <Spinner label="Retrieving passages & grounding answer…" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}

        {/* Input */}
        <div className="border-t border-slate-200 p-3">
          <div className="flex gap-2">
            <input
              className="input"
              placeholder={indexedDocs.length ? "Ask about your documents…" : "Upload & index a document first…"}
              value={question}
              disabled={thinking}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
            />
            <button className="btn-primary !px-4" disabled={thinking || !question.trim()} onClick={() => ask()}>
              {thinking ? <Spinner /> : <Send className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SourceCard({ source }: { source: SourceOut }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="flex items-center gap-1 font-medium text-slate-700">
          <FileText className="h-3.5 w-3.5 text-brand-500" /> {source.filename}
        </span>
        {source.page !== null && <span className="badge bg-slate-200 text-slate-600">page {source.page}</span>}
        {source.chunk_index !== null && <span className="badge bg-slate-200 text-slate-600">chunk #{source.chunk_index}</span>}
        {source.score !== null && <span className="badge bg-brand-100 text-brand-700">similarity {(source.score * 100).toFixed(0)}%</span>}
      </div>
      <p className="mt-1.5 line-clamp-3 text-[13px] leading-relaxed text-slate-500">{source.snippet}</p>
    </div>
  );
}