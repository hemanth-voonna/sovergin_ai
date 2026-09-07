import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Database,
  Eye,
  FileText,
  FileUp,
  Files,
  Loader2,
  ScanText,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";
import { api } from "../api";
import type { DocumentDetail, DocumentItem } from "../types";
import {
  EmptyState,
  Modal,
  Spinner,
  StatusBadge,
  ValidationBadge,
  formatBytes,
  timeAgo,
  useToast,
} from "../components/ui";

const STAGES = [
  { key: "uploaded", label: "Validated & stored" },
  { key: "processing", label: "Text extraction / OCR" },
  { key: "processed", label: "Cleaned & chunked" },
  { key: "indexing", label: "Embeddings & vectors" },
  { key: "indexed", label: "Ready for RAG" },
];

export default function Documents() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { push } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await api.listDocuments();
      setDocs(res.items);
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    load();
  }, [load]);

  // poll while anything is processing
  useEffect(() => {
    if (!docs.some((d) => ["processing", "indexing", "validating"].includes(d.status))) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [docs, load]);

  const upload = async (file: File) => {
    setUploading(true);
    try {
      const doc = await api.uploadDocument(file);
      push("success", `Uploaded "${doc.original_name}". Processing & indexing…`);
      const done = await api.pipelineDocument(doc.id);
      push("success", `"${done.original_name}" is now indexed (${done.chunk_count} chunks). Ask questions in RAG Chat!`);
      load();
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) upload(file);
  };

  const act = async (id: string, fn: () => Promise<unknown>, okMsg: string) => {
    setBusy(id);
    try {
      await fn();
      push("success", okMsg);
      load();
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (doc: DocumentItem) => {
    if (!confirm(`Delete "${doc.original_name}" and remove its vectors?`)) return;
    await act(doc.id, () => api.deleteDocument(doc.id), "Document deleted");
    if (detail?.id === doc.id) setDetail(null);
  };

  const openDetail = async (doc: DocumentItem) => {
    try {
      setDetail(await api.getDocument(doc.id));
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Failed to open document");
    }
  };

  return (
    <div className="space-y-5">
      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`card flex flex-col items-center justify-center gap-3 border-2 border-dashed p-8 text-center transition-colors ${
          dragOver ? "border-brand-500 bg-brand-50" : "border-slate-300"
        }`}
      >
        <FileUp className="h-10 w-10 text-slate-300" />
        <div>
          <p className="font-medium text-slate-700">
            {uploading ? "Uploading & processing…" : "Drop a document here, or browse"}
          </p>
          <p className="mt-1 text-sm text-slate-400">
            PDF · DOCX · TXT · PNG · JPG — validated by type, size &amp; magic bytes. Scanned
            documents get OCR automatically.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-primary" disabled={uploading} onClick={() => fileRef.current?.click()}>
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
            Choose file
          </button>
          <button
            className="btn-secondary"
            disabled={uploading}
            onClick={async () => {
              try {
                const doc = await api.loadSample();
                push("success", "Sample loaded. Processing…");
                await api.pipelineDocument(doc.id);
                push("success", "Sample document indexed — try the RAG Chat!");
                load();
              } catch (e) {
                push("error", e instanceof Error ? e.message : "Sample load failed");
              }
            }}
          >
            <Sparkles className="h-4 w-4" /> Load sample land record
          </button>
          <input ref={fileRef} type="file" hidden accept=".pdf,.docx,.txt,.png,.jpg,.jpeg" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </div>
      </div>

      {/* List */}
      {loading ? (
        <Spinner label="Loading documents…" />
      ) : docs.length === 0 ? (
        <EmptyState
          icon={<Files className="h-8 w-8 text-slate-300" />}
          title="No documents yet"
          hint="Upload a land record or click 'Load sample land record' to start the demo pipeline."
        />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-semibold">Document</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Validation</th>
                <th className="px-4 py-3 font-semibold">Pages / Chunks</th>
                <th className="px-4 py-3 font-semibold">Uploaded</th>
                <th className="px-4 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {docs.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                        <FileText className="h-[18px] w-[18px]" />
                      </div>
                      <div className="min-w-0">
                        <p className="max-w-52 truncate font-medium text-slate-800" title={d.original_name}>
                          {d.original_name}
                        </p>
                        <p className="text-xs text-slate-400">
                          {d.file_type.toUpperCase()} · {formatBytes(d.size_bytes)}
                          {d.ocr_used && <span className="ml-1 text-indigo-500">· OCR</span>}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={d.status} />
                    {d.error_message && <p className="mt-1 max-w-52 truncate text-xs text-rose-500" title={d.error_message}>{d.error_message}</p>}
                  </td>
                  <td className="px-4 py-3"><ValidationBadge status={d.validation_status} /></td>
                  <td className="px-4 py-3 text-slate-600">{d.page_count} / {d.chunk_count}</td>
                  <td className="px-4 py-3 text-slate-500">{timeAgo(d.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1.5">
                      {d.status === "uploaded" && (
                        <button className="btn-secondary px-2.5 py-1.5" disabled={busy === d.id} onClick={() => act(d.id, () => api.pipelineDocument(d.id), "Document processed & indexed")}>
                          <Sparkles className="h-4 w-4" /> Process & index
                        </button>
                      )}
                      {d.status === "processed" && (
                        <button className="btn-secondary px-2.5 py-1.5" disabled={busy === d.id} onClick={() => act(d.id, () => api.indexDocument(d.id), "Document indexed")}>
                          <Database className="h-4 w-4" /> Index
                        </button>
                      )}
                      <button className="btn-secondary px-2.5 py-1.5" onClick={() => openDetail(d)}>
                        <Eye className="h-4 w-4" />
                      </button>
                      <button className="btn-secondary px-2.5 py-1.5 text-rose-600 hover:bg-rose-50" disabled={busy === d.id} onClick={() => remove(d)}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail modal */}
      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail?.original_name ?? ""} wide>
        {detail && <DetailView doc={detail} />}
      </Modal>
    </div>
  );
}

function DetailView({ doc }: { doc: DocumentDetail }) {
  const [page, setPage] = useState(0);
  const stageIdx = STAGES.findIndex((s) => s.key === doc.status);
  const pages = doc.pages ?? [];
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={doc.status} />
        <ValidationBadge status={doc.validation_status} />
        <span className="badge bg-slate-100 text-slate-600">{doc.file_type.toUpperCase()} · {formatBytes(doc.size_bytes)}</span>
        {doc.ocr_used && <span className="badge bg-indigo-100 text-indigo-700">OCR used</span>}
        <span className="text-xs text-slate-400">checksum {doc.checksum.slice(0, 12)}…</span>
      </div>

      {/* Pipeline stepper */}
      <div>
        <p className="label">Ingestion pipeline</p>
        <div className="flex items-center gap-1 overflow-x-auto">
          {STAGES.map((s, i) => {
            const done = i < stageIdx || doc.status === s.key;
            const active = doc.status === s.key;
            return (
              <div key={s.key} className="flex items-center gap-1">
                <div className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                  done ? "bg-emerald-100 text-emerald-700" : active ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-400"
                }`}>
                  {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : active ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5 opacity-50" />}
                  {s.label}
                </div>
                {i < STAGES.length - 1 && <span className="text-slate-300">→</span>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center sm:grid-cols-6">
        <Metric label="Pages" value={doc.page_count} />
        <Metric label="Chars" value={doc.char_count} />
        <Metric label="Chunks" value={doc.chunk_count} />
        <Metric label="Type" value={doc.file_type} />
        <Metric label="OCR" value={doc.ocr_used ? "yes" : "no"} />
        <Metric label="Vectors" value={doc.chunk_count} />
      </div>

      {doc.error_message && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{doc.error_message}</div>
      )}

      {/* Extracted text */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="label mb-0">Extracted text {doc.ocr_used && <span className="normal-case text-indigo-500">(OCR)</span>}</p>
          {pages.length > 1 && (
            <div className="flex gap-1">
              {pages.map((p) => (
                <button key={p.page_number} onClick={() => setPage(p.page_number - 1)}
                  className={`rounded px-2 py-0.5 text-xs font-medium ${page === p.page_number - 1 ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
                  p.{p.page_number}
                </button>
              ))}
            </div>
          )}
        </div>
        <pre className="codeblock max-h-80 overflow-auto whitespace-pre-wrap text-slate-200">
          {pages[page]?.text || doc.extracted_text || "No text extracted yet."}
        </pre>
        {doc.ocr_used && (
          <p className="mt-1 flex items-center gap-1 text-xs text-slate-400">
            <ScanText className="h-3.5 w-3.5" /> Text was recovered with Tesseract OCR.
          </p>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-2 py-2">
      <p className="text-lg font-bold text-slate-800">{value}</p>
      <p className="text-[11px] uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  );
}