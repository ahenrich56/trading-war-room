"use client";

import { useState, useEffect, useCallback } from "react";
import { MiniChart } from "./MiniChart";
import { SignalPayload } from "./types";

const TIMEFRAMES = ["1m", "5m", "15m", "1h"] as const;

interface MultiChartGridProps {
  ticker: string;
  signal: SignalPayload | null;
  showSessions: boolean;
  showBubbles: boolean;
  showDelta: boolean;
  showCVD: boolean;
  showVwapBands: boolean;
  showVP: boolean;
  showFootprint: boolean;
  showHeatmap: boolean;
}

export function MultiChartGrid({
  ticker, signal,
  showSessions, showBubbles, showDelta, showCVD, showVwapBands, showVP,
  showFootprint, showHeatmap,
}: MultiChartGridProps) {
  const [chartDataMap, setChartDataMap] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);

  const fetchAll = useCallback(async (t: string) => {
    if (t.length < 1) return;
    setLoading(true);
    try {
      const results = await Promise.all(
        TIMEFRAMES.map(async (tf) => {
          const res = await fetch("/api/chart-data", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker: t, timeframe: tf }),
          });
          const data = await res.json();
          return { tf, data };
        })
      );
      const map: Record<string, any> = {};
      for (const r of results) {
        map[r.tf] = r.data;
      }
      setChartDataMap(map);
    } catch (e) {
      // silently fail — individual charts show placeholder
    }
    setLoading(false);
  }, []);

  // Initial load + polling
  useEffect(() => {
    fetchAll(ticker);
    const interval = setInterval(() => fetchAll(ticker), 45000); // 45s — WS handles real-time candle ticks
    return () => clearInterval(interval);
  }, [ticker, fetchAll]);

  return (
    <div>
      {loading && Object.keys(chartDataMap).length === 0 && (
        <div className="h-[350px] flex items-center justify-center text-slate-600 text-sm">
          Loading 4 timeframes...
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {TIMEFRAMES.map((tf) => (
          <div key={tf} className="border border-white/5 rounded-lg p-2 bg-black/20">
            <div className="text-[10px] text-slate-500 font-bold mb-1 tracking-wider">{tf.toUpperCase()}</div>
            <MiniChart
              chartData={chartDataMap[tf] || null}
              signal={signal}
              ticker={ticker}
              compact
              showSessions={showSessions}
              showBubbles={showBubbles}
              showDelta={showDelta}
              showCVD={showCVD}
              showVwapBands={showVwapBands}
              showVP={showVP}
              showFootprint={showFootprint}
              showHeatmap={showHeatmap}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
