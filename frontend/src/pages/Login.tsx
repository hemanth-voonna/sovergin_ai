import React, { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Landmark, Lock, ShieldCheck, User } from "lucide-react";
import { api, ApiError, getToken, getUser } from "../api";
import { Alert, Spinner } from "../components/ui";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // If already authenticated, redirect to Dashboard
  if (getToken() && getUser()) {
    const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || "/dashboard";
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Please enter both username and password.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await api.login(username.trim(), password);
      const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || "/dashboard";
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || "Invalid username or password.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during login.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-900 px-4 py-12 text-slate-100 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        {/* Header Branding */}
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 shadow-lg shadow-brand-600/30">
            <Landmark className="h-8 w-8 text-white" />
          </div>
          <h2 className="mt-5 text-2xl font-bold tracking-tight text-white sm:text-3xl">
            SovereignAI Workbench
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Sign in to access your secure on-premise document intelligence workspace
          </p>
        </div>

        {/* Login Card */}
        <div className="rounded-2xl border border-slate-800 bg-slate-800/80 p-8 shadow-2xl backdrop-blur-sm">
          {error && (
            <div className="mb-6">
              <Alert kind="error" title="Authentication Failed">
                {error}
              </Alert>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Username
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. admin"
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/90 py-2.5 pl-10 pr-3 text-sm text-white placeholder-slate-500 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/90 py-2.5 pl-10 pr-3 text-sm text-white placeholder-slate-500 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-brand-600/20 transition-all hover:bg-brand-500 hover:shadow-brand-500/30 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50"
            >
              {loading ? (
                <Spinner label="Authenticating…" />
              ) : (
                <>
                  <span>Sign in</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Sovereign security footer */}
          <div className="mt-6 border-t border-slate-700/60 pt-4 text-center">
            <div className="inline-flex items-center gap-1.5 text-xs text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              <span>Isolated on-premise authentication &middot; No cloud leakage</span>
            </div>
            <p className="mt-2 text-[11px] text-slate-500">
              Default system account: <span className="font-mono text-slate-400">admin</span> / <span className="font-mono text-slate-400">admin123</span>
            </p>
          </div>
        </div>

        {/* Footer info */}
        <p className="text-center text-xs text-slate-500">
          SovereignAI Workbench &middot; Smart India Hackathon 2026 (SIH117)
        </p>
      </div>
    </div>
  );
}
