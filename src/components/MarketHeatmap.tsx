"use client";

import { useState, useEffect, useCallback } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface TickerData {
  ticker: string;
  price: number;
  change_pct: number;
}

interface MarketHeatmapProps {
  onTickerSelect: (ticker: string) => void;
}

function heatColor(pct: number): string {
  const clamped = Math.max(-3, Math.min(3, pct));
  if (clamped > 0) {
    const intensity = Math.min(1, clamped / 2);
    return `rgba(34, 197, 94, ${0.05 + intensity * 0.12})`;
  }
  if (clamped < 0) {
    const intensity = Math.min(1, Math.abs(clamped) / 2);
    return `rgba(239, 68, 68, ${0.05 + intensity * 0.12})`;
  }
  return "rgba(255, 255, 255, 0.03)";
}

function pctColor(pct: number): string {
  if (pct > 0) return "text-green-400";
  if (pct < 0) return "text-red-400";
  return "text-slate-500";
}

const GROUP_LABELS: Record<string, string> = {
  Indices: "INDICES",
  Energy: "ENERGY",
  Metals: "METALS",
  Bonds: "BONDS",
  Crypto: "CRYPTO",
};

export function MarketHeatmap({ onTickerSelect }: MarketHeatmapProps) {
  const [data, setData] = useState<Record<string, TickerData[]> | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/market-overview");
      const json = await res.json();
      if (!json.error) setData(json);
    } catch (_) {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="p-4 text-center text-slate-600 text-sm">
        Loading market data...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4 text-center text-slate-600 text-sm">
        Failed to load market data
      </div>
    );
  }

  return (
    <div className="p-3 space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-bold text-white tracking-wider">MARKETS</h2>
        <span className="text-[9px] text-slate-600">Auto-refresh 30s</span>
      </div>

      {Object.entries(data).map(([group, tickers]) => (
        <div key={group}>
          <div className="text-[10px] text-slate-500 font-bold tracking-widest mb-1.5">
            {GROUP_LABELS[group] || group.toUpperCase()}
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {tickers.map((t) => (
              <button
                key={t.ticker}
                onClick={() => onTickerSelect(t.ticker)}
                className="relative rounded-xl border border-white/8 p-2.5 text-left transition-all hover:border-white/15 hover:scale-[1.02] active:scale-[0.98]"
                style={{ backgroundColor: heatColor(t.change_pct), backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)" }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-white">{t.ticker}</span>
                  {t.change_pct !== 0 && (
                    t.change_pct > 0
                      ? <TrendingUp className="w-3 h-3 text-green-400" />
                      : <TrendingDown className="w-3 h-3 text-red-400" />
                  )}
                </div>
                <div className="text-sm font-bold text-white/90">
                  ${t.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div className={`text-[11px] font-bold ${pctColor(t.change_pct)}`}>
                  {t.change_pct > 0 ? "+" : ""}{t.change_pct.toFixed(2)}%
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
