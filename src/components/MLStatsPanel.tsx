"use client";

import { useState, useEffect, useCallback } from "react";
import { Brain, TrendingUp, Target, BarChart3, RefreshCw } from "lucide-react";

interface MLStats {
  status: string;
  message?: string;
  n_samples?: number;
  n_wins?: number;
  n_losses?: number;
  win_rate?: number;
  threshold?: number;
  top_features?: [string, number][];
  feature_names?: string[];
}

export function MLStatsPanel() {
  const [stats, setStats] = useState<MLStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/ml-stats");
      const data = await res.json();
      setStats(data);
    } catch {
      setStats({ status: "error", message: "Failed to reach backend" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 60000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  if (loading) {
    return (
      <div className="rounded-xl border border-white/[0.06] p-4" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
        <div className="flex items-center gap-2.5 text-slate-500 text-xs">
          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          <span className="font-medium">Loading ML model...</span>
        </div>
      </div>
    );
  }

  if (!stats || stats.status === "error") {
    return (
      <div className="rounded-xl border border-red-500/15 p-4" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
        <div className="flex items-center gap-2.5 text-red-400 text-xs">
          <div className="w-6 h-6 rounded-lg bg-red-500/10 flex items-center justify-center">
            <Brain className="h-3.5 w-3.5" />
          </div>
          <span className="font-medium">ML Model Error: {stats?.message || "Unknown"}</span>
        </div>
      </div>
    );
  }

  if (stats.status === "not_trained") {
    return (
      <div className="rounded-xl border border-amber-500/15 p-4" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
        <div className="flex items-center gap-2.5 text-amber-400 text-xs">
          <div className="w-6 h-6 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <Brain className="h-3.5 w-3.5" />
          </div>
          <span className="font-medium">{stats.message}</span>
        </div>
      </div>
    );
  }

  const topFeatures = (stats.top_features || []).slice(0, 5);
  const maxImportance = topFeatures.length > 0 ? topFeatures[0][1] : 1;

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/[0.06] p-4 space-y-3" style={{ background: "rgba(10, 10, 21, 0.5)", backdropFilter: "blur(12px)" }}>
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-purple-500/20 to-transparent" />
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-purple-500/10 flex items-center justify-center">
            <Brain className="h-4 w-4 text-purple-400" />
          </div>
          <span className="text-xs font-bold text-white tracking-wide">ML SIGNAL FILTER</span>
        </div>
        <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-green-500/10 text-green-400 font-semibold border border-green-500/15">
          ACTIVE
        </span>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-white/[0.04] p-2.5 text-center bg-white/[0.02]">
          <div className="text-[10px] text-slate-500 font-semibold mb-1">SAMPLES</div>
          <div className="text-sm font-bold text-white tabular-nums">{(stats.n_samples || 0).toLocaleString()}</div>
        </div>
        <div className="rounded-lg border border-white/[0.04] p-2.5 text-center bg-white/[0.02]">
          <div className="text-[10px] text-slate-500 font-semibold mb-1">WIN RATE</div>
          <div className={`text-sm font-bold tabular-nums ${(stats.win_rate || 0) >= 33.3 ? "text-green-400" : "text-red-400"}`}>
            {stats.win_rate}%
          </div>
        </div>
        <div className="rounded-lg border border-white/[0.04] p-2.5 text-center bg-white/[0.02]">
          <div className="text-[10px] text-slate-500 font-semibold mb-1">THRESHOLD</div>
          <div className="text-sm font-bold text-cyan-400 tabular-nums">{((stats.threshold || 0) * 100).toFixed(0)}%</div>
        </div>
      </div>

      {/* Win/Loss bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>{(stats.n_wins || 0).toLocaleString()} W</span>
          <span>{(stats.n_losses || 0).toLocaleString()} L</span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden bg-red-500/30">
          <div
            className="h-full rounded-full bg-green-500"
            style={{ width: `${stats.win_rate || 0}%` }}
          />
        </div>
      </div>

      {/* Top Features */}
      {topFeatures.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] text-slate-500 font-medium tracking-wider">TOP FEATURES</div>
          {topFeatures.map(([name, importance]) => (
            <div key={name} className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400 w-28 truncate" title={name}>
                {name.replace(/_/g, " ")}
              </span>
              <div className="flex-1 h-1 rounded-full bg-white/5">
                <div
                  className="h-full rounded-full bg-purple-500/60"
                  style={{ width: `${(importance / maxImportance) * 100}%` }}
                />
              </div>
              <span className="text-[10px] text-slate-500 w-10 text-right">
                {(importance * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
