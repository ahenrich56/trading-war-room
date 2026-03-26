"use client";

import { useEffect, useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { SignalPayload } from "@/components/types";

interface TradeJournalProps {
  signal: SignalPayload | null;
  signalHistory: SignalPayload[];
}

export function TradeJournal({ signal, signalHistory }: TradeJournalProps) {
  const [outcomesData, setOutcomesData] = useState<any>(null);

  const loadOutcomes = useCallback(async () => {
    try {
      const res = await fetch("/api/outcomes");
      const data = await res.json();
      setOutcomesData(data);
    } catch (e) {
      console.error("Failed to load outcomes:", e);
    }
  }, []);

  useEffect(() => {
    loadOutcomes();
  }, [loadOutcomes]);

  const reportOutcome = async (sig: SignalPayload, result: "WIN" | "LOSS", pnl: number) => {
    try {
      await fetch("/api/outcomes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: sig.ticker,
          signal: sig.signal,
          entry: sig.entry_zone?.min || 0,
          result,
          pnl_pct: pnl,
        }),
      });
      loadOutcomes();
    } catch (e) {
      console.error("Failed to report outcome:", e);
    }
  };

  return (
    <div className="space-y-4">
      {/* Stats Row */}
      {outcomesData && (
        <div className="grid grid-cols-4 gap-2">
          <div className="p-2.5 rounded bg-black/40 border border-white/10 text-center">
            <div className="text-[9px] text-slate-500 font-bold">TOTAL</div>
            <div className="text-xl font-black text-white">{outcomesData.total || 0}</div>
          </div>
          <div className="p-2.5 rounded bg-black/40 border border-green-500/20 text-center">
            <div className="text-[9px] text-slate-500 font-bold">WINS</div>
            <div className="text-xl font-black text-green-400">{outcomesData.wins || 0}</div>
          </div>
          <div className="p-2.5 rounded bg-black/40 border border-red-500/20 text-center">
            <div className="text-[9px] text-slate-500 font-bold">LOSSES</div>
            <div className="text-xl font-black text-red-400">{outcomesData.losses || 0}</div>
          </div>
          <div className="p-2.5 rounded bg-black/40 border border-cyan-500/20 text-center">
            <div className="text-[9px] text-slate-500 font-bold">WIN RATE</div>
            <div className={`text-xl font-black ${(outcomesData.win_rate || 0) >= 50 ? "text-green-400" : "text-red-400"}`}>
              {outcomesData.win_rate || 0}%
            </div>
          </div>
        </div>
      )}

      {/* Report Outcome */}
      {signal && (
        <div className="p-3 rounded bg-black/40 border border-white/10">
          <div className="text-[10px] text-slate-400 font-bold mb-2">REPORT: {signal.ticker} {signal.signal}</div>
          <div className="flex gap-2 flex-wrap">
            <Button size="sm" className="bg-green-600 hover:bg-green-500 text-white font-bold text-xs h-7" onClick={() => reportOutcome(signal, "WIN", 2.0)}>
              WIN +2%
            </Button>
            <Button size="sm" className="bg-green-700 hover:bg-green-600 text-white font-bold text-xs h-7" onClick={() => reportOutcome(signal, "WIN", 5.0)}>
              WIN +5%
            </Button>
            <Button size="sm" className="bg-red-600 hover:bg-red-500 text-white font-bold text-xs h-7" onClick={() => reportOutcome(signal, "LOSS", -1.0)}>
              LOSS -1%
            </Button>
            <Button size="sm" className="bg-red-700 hover:bg-red-600 text-white font-bold text-xs h-7" onClick={() => reportOutcome(signal, "LOSS", -2.0)}>
              LOSS -2%
            </Button>
          </div>
        </div>
      )}

      {/* Combined Signal History + Outcomes */}
      <div className="space-y-1 max-h-[400px] overflow-y-auto">
        {/* Recent outcomes */}
        {outcomesData?.outcomes?.length > 0 && (
          <>
            <div className="text-[10px] text-slate-500 font-bold mt-2 mb-1">REPORTED OUTCOMES</div>
            {outcomesData.outcomes.map((o: any, i: number) => (
              <div key={`o-${i}`} className="flex items-center gap-3 p-2 bg-black/30 rounded border border-white/5 text-xs">
                <span className={`font-bold min-w-[40px] ${o.result === "WIN" ? "text-green-400" : "text-red-400"}`}>{o.result}</span>
                <span className="text-white font-bold">{o.ticker}</span>
                <span className="text-slate-500">{o.signal}</span>
                <span className={`ml-auto font-black ${o.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {o.pnl_pct > 0 ? "+" : ""}{o.pnl_pct}%
                </span>
              </div>
            ))}
          </>
        )}

        {/* Signal history */}
        {signalHistory.length > 0 && (
          <>
            <div className="text-[10px] text-slate-500 font-bold mt-3 mb-1">SIGNAL HISTORY</div>
            {signalHistory.map((sig, i) => (
              <div key={`h-${i}`} className="flex items-center gap-3 p-2 bg-black/30 rounded border border-white/5 text-xs">
                <span className={`px-1.5 py-0.5 rounded font-black text-[10px] ${
                  sig.signal === "LONG" ? "bg-green-500/20 text-green-400" :
                  sig.signal === "SHORT" ? "bg-red-500/20 text-red-400" :
                  "bg-yellow-500/20 text-yellow-400"
                }`}>
                  {sig.signal}
                </span>
                <span className="text-white font-bold">{sig.ticker}</span>
                <span className="text-slate-500">{sig.timeframe}</span>
                <span className="text-slate-400 ml-auto">
                  {sig.confidence}% | R:R {sig.risk_reward}
                </span>
                {sig.timestamp_utc && (
                  <span className="text-slate-600 text-[10px]">
                    {new Date(sig.timestamp_utc).toLocaleTimeString()}
                  </span>
                )}
              </div>
            ))}
          </>
        )}

        {!outcomesData?.outcomes?.length && !signalHistory.length && (
          <div className="text-center text-slate-600 py-8 text-sm">
            No trades yet. Run analysis to start tracking.
          </div>
        )}
      </div>

      {/* AI Learning Context */}
      {outcomesData?.learning_context && (
        <div className="p-3 rounded bg-cyan-500/5 border border-cyan-500/20">
          <div className="text-[10px] text-cyan-400 font-bold mb-1">AI SELF-LEARNING</div>
          <pre className="text-[10px] text-slate-400 whitespace-pre-wrap font-mono">{outcomesData.learning_context}</pre>
        </div>
      )}
    </div>
  );
}
