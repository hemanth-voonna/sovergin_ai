import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity as ActivityIcon,
  Bot,
  Boxes,
  Cpu,
  Database,
  FileText,
  HardDrive,
  MemoryStick,
  MessageSquareText,
  PlusCircle,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError, getUser } from "../api";
import type { Activity, Dashboard } from "../types";
import { Alert, EmptyState, Spinner, StatCard, formatDuration, timeAgo, useToast } from "../components/ui";

const ACTION_ICONS: Record<string, React.ReactNode> = {
  upload: <Upload className="h-4 w-4" />,
  process: <FileText className="h-4 w-4" />,
  index: <Database className="h-4 w-4" />,
  rag_query: <MessageSquareText className="h-4 w-4" />,
  agent_run: <Bot className="h-4 w-4" />,
  validation: <ShieldCheck className="h-4 w-4" />,
  ocr: <Cpu className="h-4 w-4" />,
  sandbox: <Boxes className="h-4 w-4" />,
  delete: <ActivityIcon className="h-4 w-4" />,
};

function ActivityRow({ item }: { item: Activity }) {
  const icon = ACTION_ICONS[item.action] ?? <ActivityIcon className="h-4 w-4" />;
  return (
    <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-2.5 last:border-0">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-slate-700">{item.message}</p>
        <p className="text-xs text-slate-400">
          {item.action} · {timeAgo(item.created_at)}
        </p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const user = getUser();
  const username = user?.username || "User";
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [loadingSample, setLoadingSample] = useState(false);
  const { push } = useToast();

  const load = useCallback(() => {
    api
      .dashboard()
      .then(setData)
      .catch((e: ApiError) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const loadSample = async () => {
    setLoadingSample(true);
    try {
      const doc = await api.loadSample();
      await api.pipelineDocument(doc.id);
      push("success", `Sample document "${doc.original_name}" ingested & indexed. Try the RAG Chat!`);
      load();
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Failed to load sample");
    } finally {
      setLoadingSample(false);
    }
  };

  if (error && !data) {
    return <Alert kind="error" title="Could not reach the backend">{(error as string)}</Alert>;
  }
  if (!data) return <Spinner label="Loading dashboard…" />;

  const h = data.health;
  const services = Object.entries(h.services ?? {});
  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="card flex flex-col justify-between gap-4 bg-gradient-to-r from-ink-900 to-ink-800 p-6 text-white md:flex-row md:items-center">
        <div>
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-brand-500/20 px-3 py-1 text-xs font-semibold text-brand-300 border border-brand-500/30">
            <span>Welcome,</span>
            <span className="text-white font-bold">{username}</span>
          </div>
          <h2 className="text-xl font-bold">SovereignAI Workbench</h2>
          <p className="mt-1 max-w-xl text-sm text-slate-300">
            Secure, on-premise document processing — upload, OCR, ground AI answers in your
            documents, validate records and run tasks in an isolated sandbox. No data leaves your
            infrastructure.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn bg-white/10 text-white hover:bg-white/20" disabled={loadingSample} onClick={loadSample}>
            <PlusCircle className="h-4 w-4" />
            {loadingSample ? "Ingesting…" : "Load sample document"}
          </button>
          <Link to="/chat" className="btn bg-brand-600 text-white hover:bg-brand-500">
            <MessageSquareText className="h-4 w-4" /> Ask the RAG Chat
          </Link>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard icon={<FileText className="h-5 w-5" />} label="Documents" value={data.documents.total} tone="brand" />
        <StatCard icon={<Cpu className="h-5 w-5" />} label="Processed" value={data.documents.processed} tone="sky" />
        <StatCard icon={<Database className="h-5 w-5" />} label="Indexed" value={data.documents.indexed} sub={`${data.vectors_indexed} vectors`} tone="emerald" />
        <StatCard icon={<MessageSquareText className="h-5 w-5" />} label="RAG queries" value={data.rag_queries} tone="sky" />
        <StatCard icon={<Bot className="h-5 w-5" />} label="Agent runs" value={data.agent_runs} sub="5 agents registered" tone="amber" />
        <StatCard icon={<Boxes className="h-5 w-5" />} label="Sandbox runs" value={data.sandbox_runs} tone="rose" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Activity chart */}
        <div className="card p-5 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-slate-800">System activity — last 7 days</h3>
            <span className="text-xs text-slate-400">uploads · queries · agents · sandbox</span>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.activity_series}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#4f46e5" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} width={28} />
                <Tooltip />
                <Area type="monotone" dataKey="count" stroke="#4f46e5" strokeWidth={2} fill="url(#grad)" name="actions" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* System health */}
        <div className="card p-5">
          <h3 className="mb-3 font-semibold text-slate-800">System health</h3>
          <div className="space-y-2.5 text-sm">
            <HealthRow icon={<Cpu className="h-4 w-4" />} label="CPU" value={`${h.cpu_percent}%`} pct={h.cpu_percent} />
            <HealthRow icon={<MemoryStick className="h-4 w-4" />} label="Memory" value={`${h.memory.used_gb} / ${h.memory.total_gb} GB`} pct={h.memory.percent} />
            <HealthRow icon={<HardDrive className="h-4 w-4" />} label="Disk" value={`${h.disk.used_gb} / ${h.disk.total_gb} GB`} pct={h.disk.percent} />
            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-slate-400">Uptime</span>
              <span className="font-medium text-slate-600">{formatDuration(h.uptime_s * 1000)}</span>
            </div>
          </div>
          <div className="mt-4 border-t border-slate-100 pt-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Services</p>
            <div className="flex flex-wrap gap-1.5">
              {services.map(([name, state]) => (
                <span
                  key={name}
                  className={`badge ${
                    String(state).startsWith("ok") || String(state).startsWith("chroma")
                      ? "bg-emerald-100 text-emerald-700"
                      : String(state).startsWith("unavailable")
                        ? "bg-amber-100 text-amber-700"
                        : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {name}: {String(state).slice(0, 28)}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recent activity */}
      <div className="card">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h3 className="font-semibold text-slate-800">Recent activity</h3>
          <Link to="/documents" className="text-sm text-brand-600 hover:underline">Open documents →</Link>
        </div>
        {data.recent_activity.length === 0 ? (
          <EmptyState
            icon={<ActivityIcon className="h-8 w-8 text-slate-300" />}
            title="No activity yet"
            hint="Upload and process a document to see the audit trail here."
          />
        ) : (
          <div className="max-h-72 divide-y divide-slate-100 overflow-y-auto">
            {data.recent_activity.map((a) => <ActivityRow key={a.id} item={a} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function HealthRow({ icon, label, value, pct }: { icon: React.ReactNode; label: string; value: string; pct: number }) {
  const color = pct > 85 ? "bg-rose-500" : pct > 65 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-slate-500">{icon}{label}</span>
        <span className="font-medium text-slate-700">{value}</span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-slate-100">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}