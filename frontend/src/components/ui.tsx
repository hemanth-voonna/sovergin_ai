import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from "lucide-react";

/* ---------------------------------- Spinner -------------------------------- */
export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

/* ---------------------------------- Badges --------------------------------- */
const STATUS_STYLES: Record<string, string> = {
  uploaded: "bg-sky-100 text-sky-700",
  validating: "bg-indigo-100 text-indigo-700",
  processing: "bg-indigo-100 text-indigo-700",
  indexing: "bg-indigo-100 text-indigo-700",
  processed: "bg-emerald-100 text-emerald-700",
  indexed: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600";
  const dot =
    status === "failed" ? "bg-rose-500" :
    status === "indexed" || status === "processed" ? "bg-emerald-500" :
    status === "uploaded" ? "bg-sky-500" : "bg-indigo-500 animate-pulse";
  return (
    <span className={`badge ${style}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}

export function ValidationBadge({ status }: { status: string }) {
  if (status === "pending") return <span className="badge bg-slate-100 text-slate-500">pending</span>;
  if (status === "valid") return <span className="badge bg-emerald-100 text-emerald-700">valid</span>;
  if (status === "warning") return <span className="badge bg-amber-100 text-amber-700">warning</span>;
  if (status === "invalid") return <span className="badge bg-rose-100 text-rose-700">invalid</span>;
  return <span className="badge bg-slate-100 text-slate-500">{status}</span>;
}

/* ---------------------------------- Empty ---------------------------------- */
export function EmptyState({ icon, title, hint }: { icon?: React.ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center">
      {icon}
      <p className="font-medium text-slate-600">{title}</p>
      {hint && <p className="max-w-md text-sm text-slate-400">{hint}</p>}
    </div>
  );
}

/* ---------------------------------- Modal ---------------------------------- */
export function Modal({ open, onClose, title, children, wide }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 backdrop-blur-sm">
      <div className={`mt-10 w-full ${wide ? "max-w-4xl" : "max-w-2xl"} rounded-2xl bg-white shadow-2xl`}>
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h3 className="font-semibold text-slate-800">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="max-h-[80vh] overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

/* ---------------------------------- Toasts ---------------------------------- */
type ToastKind = "success" | "error" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}
const ToastCtx = createContext<{ push: (kind: ToastKind, message: string) => void }>({ push: () => {} });

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: ToastKind, message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  const icons = {
    success: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
    error: <XCircle className="h-4 w-4 text-rose-500" />,
    info: <Info className="h-4 w-4 text-sky-500" />,
  };
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className="flex items-start gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-lg">
            {icons[t.kind]}
            <span className="text-sm text-slate-700">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------------------------- Alert ---------------------------------- */
export function Alert({ kind, title, children }: { kind: "error" | "warning" | "info" | "success"; title: string; children?: React.ReactNode }) {
  const styles = {
    error: "border-rose-200 bg-rose-50 text-rose-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  }[kind];
  const Icon = kind === "error" ? XCircle : kind === "warning" ? AlertTriangle : kind === "success" ? CheckCircle2 : Info;
  return (
    <div className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm ${styles}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="font-medium">{title}</p>
        {children && <div className="mt-1 text-[13px] opacity-90">{children}</div>}
      </div>
    </div>
  );
}

/* ---------------------------------- Stat card ---------------------------------- */
export function StatCard({ icon, label, value, sub, tone = "brand" }: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: "brand" | "emerald" | "amber" | "rose" | "sky";
}) {
  const tones = {
    brand: "bg-brand-50 text-brand-600",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
    rose: "bg-rose-50 text-rose-600",
    sky: "bg-sky-50 text-sky-600",
  }[tone];
  return (
    <div className="card flex items-center gap-4 p-4">
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${tones}`}>{icon}</div>
      <div className="min-w-0">
        <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <p className="text-2xl font-bold text-slate-800">{value}</p>
        {sub && <p className="truncate text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}

/* ---------------------------------- Misc ---------------------------------- */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function formatDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}