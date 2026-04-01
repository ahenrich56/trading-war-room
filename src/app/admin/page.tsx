"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Brain, Database, TrendingUp, RefreshCw, Shield, BarChart3,
  AlertTriangle, CheckCircle, XCircle, Zap, Lock, Eye, EyeOff
} from "lucide-react";

const ADMIN_KEY_STORAGE = "warroom_admin_key";

interface DashboardData {
  db: {
    total_signals: number;
    resolved_signals: number;
    total_outcomes: number;
    wins: number;
    losses: number;
    win_rate: number;
  };
  grade_distribution: Record<string, number>;
  ml: {
    status: string;
    n_samples?: number;
    n_wins?: number;
    n_losses?: number;
    win_rate?: number;
    threshold?: number;
    top_features?: [string, number][];
  };
  ml_threshold: number;
  recent_signals: {
    ticker: string;
    signal: string;
    grade: string;
    score: number;
    confidence: number;
    timestamp: string;
  }[];
}

export default function AdminDashboard() {
  const [adminKey, setAdminKey] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retraining, setRetraining] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(ADMIN_KEY_STORAGE);
    if (saved) {
      setAdminKey(saved);
      setAuthenticated(true);
    }
  }, []);

  const showToast = (msg: string, type: "success" | "error") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchDashboard = useCallback(async (key?: string) => {
    const k = key || adminKey;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin?action=dashboard&key=${k}`);
      if (res.status === 403) {
        setError("Invalid admin key");
        setAuthenticated(false);
        localStorage.removeItem(ADMIN_KEY_STORAGE);
        return;
      }
      const d = await res.json();
      if (d.error) {
        setError(d.error);
        return;
      }
      setData(d);
      setAuthenticated(true);
      localStorage.setItem(ADMIN_KEY_STORAGE, k);
    } catch (e: any) {
      setError(e.message || "Failed to connect");
    } finally {
      setLoading(false);
    }
  }, [adminKey]);

  useEffect(() => {
    if (authenticated && adminKey) {
      fetchDashboard();
      const interval = setInterval(() => fetchDashboard(), 30000);
      return () => clearInterval(interval);
    }
  }, [authenticated, adminKey, fetchDashboard]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    fetchDashboard();
  };

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      const res = await fetch("/api/admin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "retrain", key: adminKey }),
      });
      const d = await res.json();
      if (d.error) {
        showToast(d.error, "error");
      } else {
        showToast(`Model retrained: ${d.result?.n_samples?.toLocaleString()} samples, ${d.result?.win_rate}% WR`, "success");
        fetchDashboard();
      }
    } catch {
      showToast("Retrain failed", "error");
    } finally {
      setRetraining(false);
    }
  };

  const handleLogout = () => {
    setAuthenticated(false);
    setData(null);
    setAdminKey("");
    localStorage.removeItem(ADMIN_KEY_STORAGE);
  };

  // Login screen
  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center font-mono" style={{ background: "linear-gradient(135deg, #05050A 0%, #0a0f1a 30%, #080510 60%, #05050A 100%)" }}>
        <form onSubmit={handleLogin} className="w-80 space-y-4">
          <div className="flex items-center justify-center gap-2 mb-6">
            <Shield className="h-8 w-8 text-red-500" />
            <h1 className="text-xl font-extrabold text-white tracking-widest">ADMIN</h1>
          </div>
          <div className="relative">
            <input
              type={showKey ? "text" : "password"}
              value={adminKey}
              onChange={e => setAdminKey(e.target.value)}
              placeholder="Admin key"
              className="w-full px-4 py-3 bg-black/50 border border-white/20 rounded-lg text-white text-sm focus:outline-none focus:border-red-500/50"
            />
            <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-3 top-3.5 text-slate-500 hover:text-white">
              {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <button type="submit" disabled={loading} className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-bold text-sm rounded-lg transition-colors disabled:opacity-50">
            {loading ? "Authenticating..." : "ACCESS DASHBOARD"}
          </button>
        </form>
      </div>
    );
  }

  // Admin dashboard
  const db = data?.db;
  const ml = data?.ml;
  const grades = data?.grade_distribution;
  const topFeatures = (ml?.top_features || []).slice(0, 5);
  const maxImportance = topFeatures.length > 0 ? topFeatures[0][1] : 1;

  return (
    <div className="min-h-screen text-slate-300 font-mono" style={{ background: "linear-gradient(135deg, #05050A 0%, #0a0f1a 30%, #080510 60%, #05050A 100%)" }}>
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-white/8 px-6 py-3 flex items-center justify-between" style={{ background: "rgba(5, 5, 10, 0.8)", backdropFilter: "blur(16px)" }}>
        <div className="flex items-center gap-3">
          <Shield className="h-5 w-5 text-red-500" />
          <h1 className="text-lg font-extrabold text-white tracking-widest">WAR ROOM ADMIN</h1>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 font-semibold border border-red-500/20">OWNER ONLY</span>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => fetchDashboard()} className="text-slate-500 hover:text-white transition-colors" title="Refresh">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button onClick={handleLogout} className="text-xs text-slate-500 hover:text-red-400 transition-colors">Logout</button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {loading && !data ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="h-6 w-6 text-slate-500 animate-spin" />
          </div>
        ) : data ? (
          <>
            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              <StatCard icon={Database} label="TOTAL SIGNALS" value={db?.total_signals?.toLocaleString() || "0"} color="cyan" />
              <StatCard icon={CheckCircle} label="RESOLVED" value={db?.resolved_signals?.toLocaleString() || "0"} color="green" />
              <StatCard icon={BarChart3} label="OUTCOMES" value={db?.total_outcomes?.toLocaleString() || "0"} color="purple" />
              <StatCard icon={TrendingUp} label="WINS" value={`${db?.wins?.toLocaleString() || 0}`} color="green" />
              <StatCard icon={XCircle} label="LOSSES" value={`${db?.losses?.toLocaleString() || 0}`} color="red" />
              <StatCard icon={Zap} label="WIN RATE" value={`${db?.win_rate || 0}%`} color={db?.win_rate && db.win_rate >= 33.3 ? "green" : "red"} />
            </div>

            {/* ML Model + Grade Distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* ML Model Panel */}
              <div className="rounded-xl border border-white/8 p-5 space-y-4" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-purple-400" />
                    <span className="text-sm font-bold text-white tracking-wide">ML MODEL</span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                    ml?.status === "active"
                      ? "bg-green-500/15 text-green-400 border-green-500/20"
                      : "bg-amber-500/15 text-amber-400 border-amber-500/20"
                  }`}>
                    {ml?.status?.toUpperCase() || "UNKNOWN"}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <MiniStat label="SAMPLES" value={ml?.n_samples?.toLocaleString() || "0"} />
                  <MiniStat label="ML WIN RATE" value={`${ml?.win_rate || 0}%`} />
                  <MiniStat label="THRESHOLD" value={`${((data.ml_threshold || 0) * 100).toFixed(0)}%`} />
                </div>

                {/* Win/Loss bar */}
                {ml?.n_wins !== undefined && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-slate-500">
                      <span>{ml.n_wins?.toLocaleString()} W</span>
                      <span>{ml.n_losses?.toLocaleString()} L</span>
                    </div>
                    <div className="h-2 rounded-full overflow-hidden bg-red-500/30">
                      <div className="h-full rounded-full bg-green-500" style={{ width: `${ml.win_rate || 0}%` }} />
                    </div>
                  </div>
                )}

                {/* Top Features */}
                {topFeatures.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[10px] text-slate-500 font-medium tracking-wider">TOP FEATURES</div>
                    {topFeatures.map(([name, importance]) => (
                      <div key={name} className="flex items-center gap-2">
                        <span className="text-[11px] text-slate-400 w-32 truncate" title={name}>{name.replace(/_/g, " ")}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-white/5">
                          <div className="h-full rounded-full bg-purple-500/60" style={{ width: `${(importance / maxImportance) * 100}%` }} />
                        </div>
                        <span className="text-[10px] text-slate-500 w-12 text-right">{(importance * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Retrain Button */}
                <button
                  onClick={handleRetrain}
                  disabled={retraining}
                  className="w-full py-2.5 rounded-lg border border-purple-500/30 bg-purple-500/10 text-purple-400 font-bold text-xs tracking-wide hover:bg-purple-500/20 transition-colors disabled:opacity-50"
                >
                  {retraining ? (
                    <span className="flex items-center justify-center gap-2">
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" /> RETRAINING...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      <Zap className="h-3.5 w-3.5" /> FORCE RETRAIN MODEL
                    </span>
                  )}
                </button>
              </div>

              {/* Grade Distribution */}
              <div className="rounded-xl border border-white/8 p-5 space-y-4" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-cyan-400" />
                  <span className="text-sm font-bold text-white tracking-wide">GRADE DISTRIBUTION</span>
                </div>

                {grades && (
                  <div className="space-y-3">
                    {(["A+", "A", "B", "C"] as const).map(grade => {
                      const count = grades[grade] || 0;
                      const total = Object.values(grades).reduce((a, b) => a + b, 0);
                      const pct = total > 0 ? (count / total) * 100 : 0;
                      const colors: Record<string, string> = {
                        "A+": "bg-emerald-500", "A": "bg-green-500", "B": "bg-amber-500", "C": "bg-red-500"
                      };
                      return (
                        <div key={grade} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-slate-400 font-bold">{grade}</span>
                            <span className="text-slate-500">{count.toLocaleString()} ({pct.toFixed(1)}%)</span>
                          </div>
                          <div className="h-2 rounded-full bg-white/5">
                            <div className={`h-full rounded-full ${colors[grade]}`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Quick Info */}
                <div className="mt-4 p-3 rounded-lg border border-white/5 text-[11px] text-slate-500 space-y-1" style={{ background: "rgba(0,0,0,0.3)" }}>
                  <p>Break-even WR for 2:1 R:R: <span className="text-white font-bold">33.3%</span></p>
                  <p>ML gate passes signals with P(WIN) &ge; <span className="text-cyan-400 font-bold">{((data.ml_threshold || 0) * 100).toFixed(0)}%</span></p>
                  <p>Model auto-retrains every 50 new outcomes</p>
                </div>
              </div>
            </div>

            {/* Recent Signals Table */}
            <div className="rounded-xl border border-white/8 p-5" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="h-5 w-5 text-amber-400" />
                <span className="text-sm font-bold text-white tracking-wide">RECENT SIGNALS</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 text-left border-b border-white/5">
                      <th className="pb-2 pr-4">Ticker</th>
                      <th className="pb-2 pr-4">Signal</th>
                      <th className="pb-2 pr-4">Grade</th>
                      <th className="pb-2 pr-4">Score</th>
                      <th className="pb-2 pr-4">Confidence</th>
                      <th className="pb-2">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_signals.map((s, i) => (
                      <tr key={i} className="border-b border-white/3 hover:bg-white/3">
                        <td className="py-2 pr-4 text-white font-bold">{s.ticker}</td>
                        <td className="py-2 pr-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            s.signal === "LONG" ? "bg-green-500/15 text-green-400" :
                            s.signal === "SHORT" ? "bg-red-500/15 text-red-400" :
                            "bg-slate-500/15 text-slate-400"
                          }`}>{s.signal}</span>
                        </td>
                        <td className="py-2 pr-4">
                          <span className={`font-bold ${
                            s.grade === "A+" ? "text-emerald-400" :
                            s.grade === "A" ? "text-green-400" :
                            s.grade === "B" ? "text-amber-400" :
                            "text-red-400"
                          }`}>{s.grade || "-"}</span>
                        </td>
                        <td className="py-2 pr-4 text-slate-400">{s.score}</td>
                        <td className="py-2 pr-4 text-slate-400">{typeof s.confidence === "number" ? `${(s.confidence * 100).toFixed(0)}%` : "-"}</td>
                        <td className="py-2 text-slate-500">{s.timestamp ? new Date(s.timestamp).toLocaleString() : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : null}
      </main>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 z-[100] px-4 py-3 rounded-lg border backdrop-blur-md shadow-2xl text-xs font-bold animate-in slide-in-from-right duration-300 ${
          toast.type === "success" ? "bg-green-500/20 border-green-500/40 text-green-400" : "bg-red-500/20 border-red-500/40 text-red-400"
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: string; color: string }) {
  const colorMap: Record<string, string> = {
    cyan: "text-cyan-400",
    green: "text-green-400",
    purple: "text-purple-400",
    red: "text-red-400",
    amber: "text-amber-400",
  };
  return (
    <div className="rounded-xl border border-white/8 p-3" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className={`h-3.5 w-3.5 ${colorMap[color] || "text-slate-400"}`} />
        <span className="text-[10px] text-slate-500 tracking-wider">{label}</span>
      </div>
      <div className={`text-lg font-bold ${colorMap[color] || "text-white"}`}>{value}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 p-2.5 text-center" style={{ background: "rgba(0,0,0,0.3)" }}>
      <div className="text-[10px] text-slate-500 mb-1">{label}</div>
      <div className="text-sm font-bold text-white">{value}</div>
    </div>
  );
}
