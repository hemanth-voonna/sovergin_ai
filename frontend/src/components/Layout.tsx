import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Bot,
  FileText,
  Gauge,
  Landmark,
  LayoutDashboard,
  MessageSquareText,
  ScanText,
  Settings as SettingsIcon,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { api } from "../api";
import { ToastProvider } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/chat", label: "RAG Chat", icon: MessageSquareText },
  { to: "/agents", label: "AI Agents", icon: Bot },
  { to: "/ocr", label: "OCR", icon: ScanText },
  { to: "/validation", label: "Validation", icon: ShieldCheck },
  { to: "/sandbox", label: "Sandbox", icon: Terminal },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/documents": "Document Management",
  "/chat": "RAG Chat",
  "/agents": "AI Agents",
  "/ocr": "OCR Studio",
  "/validation": "Document Validation",
  "/sandbox": "Secure Sandbox",
  "/settings": "Settings",
};

function HealthPill() {
  const [status, setStatus] = useState<string | null>(null);
  const [version, setVersion] = useState("");
  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .health()
        .then((h) => {
          if (!alive) return;
          setStatus(h.status as string);
          setVersion((h.version as string) ?? "");
        })
        .catch(() => alive && setStatus(null));
    load();
    const t = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  return (
    <div className="flex items-center gap-3">
      <span className="hidden text-xs text-slate-400 sm:inline">v{version || "—"}</span>
      <span
        className={`badge ${
          status === "ok" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
        }`}
        title="Backend health"
      >
        <span className={`h-1.5 w-1.5 rounded-full ${status === "ok" ? "bg-emerald-500" : "bg-rose-500 animate-pulse"}`} />
        {status === "ok" ? "API online" : status === null ? "connecting…" : "degraded"}
      </span>
    </div>
  );
}

export default function Layout() {
  const location = useLocation();
  const title = TITLES[location.pathname] ?? "SovereignAI Workbench";

  return (
    <ToastProvider>
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside className="fixed inset-y-0 left-0 z-40 flex w-60 flex-col bg-ink-900 text-slate-300">
          <div className="flex items-center gap-2.5 border-b border-white/10 px-5 py-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Landmark className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-bold text-white">SovereignAI</p>
              <p className="text-[11px] text-slate-400">Workbench · SIH 2026 (117)</p>
            </div>
          </div>
          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-brand-600 text-white shadow-sm"
                      : "text-slate-400 hover:bg-white/5 hover:text-white"
                  }`
                }
              >
                <Icon className="h-[18px] w-[18px]" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="border-t border-white/10 px-5 py-4">
            <p className="text-[11px] leading-relaxed text-slate-500">
              Sovereign, private &amp; on-premise document intelligence for government and enterprise.
            </p>
          </div>
        </aside>

        {/* Main */}
        <div className="ml-60 flex min-h-screen flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-6 backdrop-blur">
            <div className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-brand-600" />
              <h1 className="text-lg font-semibold text-slate-800">{title}</h1>
            </div>
            <HealthPill />
          </header>
          <main className="flex-1 px-6 py-6">
            <Outlet />
          </main>
          <footer className="border-t border-slate-200 px-6 py-3 text-center text-xs text-slate-400">
            SovereignAI Workbench — Smart India Hackathon 2026 · Problem Statement SIH117
          </footer>
        </div>
      </div>
    </ToastProvider>
  );
}