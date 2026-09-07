import { useEffect, useRef, useState } from "react";
import { FileUp, Loader2, ScanText } from "lucide-react";
import { api } from "../api";
import type { DocumentItem, OCRResult } from "../types";
import { Alert, EmptyState, formatDuration, useToast } from "../components/ui";

export default function OCRPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [docId, setDocId] = useState("");
  const [lang, setLang] = useState("eng");
  const [result, setResult] = useState<OCRResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { push } = useToast();

  useEffect(() => {
    api.listDocuments().then((r) => setDocs(r.items)).catch(() => {});
  }, []);

  const run = async () => {
    if (!file && !docId) return;
    setBusy(true);
    setResult(null);
    try {
      const res = file
        ? await api.ocrFile(file, lang)
        : await api.ocrDocument(docId, lang);
      setResult(res);
      push("success", `OCR completed in ${formatDuration(res.took_ms)}`);
    } catch (e) {
      push("error", e instanceof Error ? e.message : "OCR failed");
    } finally {
      setBusy(false);
    }
  };

  const ingest = async () => {
    if (!file || !result) return;
    setIngesting(true);
    try {
      const doc = await api.uploadDocument(file);
      await api.pipelineDocument(doc.id);
      push("success", `OCR text ingested & indexed as "${doc.original_name}" — try RAG Chat!`);
      setDocs(await (await api.listDocuments()).items);
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
      <div className="card h-fit space-y-4 p-5">
        <div>
          <p className="label">Source</p>
          <div className="space-y-2">
            <button
              className={`w-full rounded-lg border-2 border-dashed p-4 text-center text-sm transition-colors ${file ? "border-brand-400 bg-brand-50 text-brand-700" : "border-slate-300 text-slate-400 hover:border-brand-300"}`}
              onClick={() => fileRef.current?.click()}
            >
              <FileUp className="mx-auto mb-1 h-5 w-5" />
              {file ? file.name : "Choose image or scanned PDF"}
            </button>
            <input ref={fileRef} type="file" hidden accept=".pdf,.png,.jpg,.jpeg"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setDocId(""); }} />
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="h-px flex-1 bg-slate-200" /> or from corpus <span className="h-px flex-1 bg-slate-200" />
            </div>
            <select className="input" value={docId} onChange={(e) => { setDocId(e.target.value); setFile(null); }}>
              <option value="">— processed document in corpus —</option>
              {docs.filter((d) => ["pdf", "png", "jpg", "jpeg"].includes(d.file_type)).map((d) => (
                <option key={d.id} value={d.id}>{d.original_name}</option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="label">Language</label>
          <select className="input" value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="eng">English</option>
            <option value="hin">Hindi</option>
            <option value="mar">Marathi</option>
            <option value="eng+hin">English + Hindi</option>
          </select>
        </div>
        <button className="btn-primary w-full" disabled={busy || (!file && !docId)} onClick={run}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanText className="h-4 w-4" />}
          {busy ? "OCR running…" : "Run OCR"}
        </button>
        <Alert kind="info" title="How it works">
          Text-layer PDFs skip OCR automatically. Scanned PDFs and images are rendered and read by
          Tesseract with per-page confidence.
        </Alert>
      </div>

      <div className="space-y-4">
        {result ? (
          <>
            <div className="card p-5">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="flex items-center gap-2 font-semibold text-slate-800">
                  <ScanText className="h-4 w-4 text-brand-600" /> Extracted text
                </h3>
                <div className="flex items-center gap-2">
                  <span className="badge bg-slate-100 text-slate-500">{result.language}</span>
                  <span className="badge bg-slate-100 text-slate-500">{formatDuration(result.took_ms)}</span>
                  {file && (
                    <button className="btn-secondary px-2.5 py-1.5" disabled={ingesting} onClick={ingest}>
                      {ingesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanText className="h-4 w-4" />}
                      Ingest as document
                    </button>
                  )}
                </div>
              </div>
              <pre className="codeblock max-h-96 overflow-auto whitespace-pre-wrap text-slate-200">{result.text || "(no text detected)"}</pre>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {result.pages.map((p) => (
                <div key={p.page_number} className="card p-4">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-700">Page {p.page_number}</span>
                    <span className={`badge ${p.confidence >= 70 ? "bg-emerald-100 text-emerald-700" : p.confidence >= 40 ? "bg-amber-100 text-amber-700" : "bg-rose-100 text-rose-700"}`}>
                      {p.confidence.toFixed(0)}% conf
                    </span>
                  </div>
                  <div className="mb-2 h-1.5 rounded-full bg-slate-100">
                    <div className={`h-1.5 rounded-full ${p.confidence >= 70 ? "bg-emerald-500" : p.confidence >= 40 ? "bg-amber-500" : "bg-rose-500"}`}
                      style={{ width: `${p.confidence}%` }} />
                  </div>
                  <p className="line-clamp-6 text-xs leading-relaxed text-slate-500">{p.text}</p>
                </div>
              ))}
            </div>
          </>
        ) : (
          <EmptyState
            icon={<ScanText className="h-8 w-8 text-slate-300" />}
            title="No OCR run yet"
            hint="Upload a scanned document or pick one from the corpus, then run OCR to see extracted text with confidence scores."
          />
        )}
      </div>
    </div>
  );
}