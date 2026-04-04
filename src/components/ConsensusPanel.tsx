"use client";

import { Users, Bot, Sparkles, Diamond } from "lucide-react";

export function ConsensusPanel({ data, isRunning, ticker }: { data: any, isRunning: boolean, ticker: string }) {
  if (isRunning) {
    return (
      <div className="h-[350px] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="relative mx-auto w-16 h-16">
            <div className="absolute inset-0 rounded-full border-2 border-amber-500/20 animate-ping" />
            <div className="absolute inset-2 rounded-full border-2 border-amber-500/30 animate-pulse" />
            <div className="absolute inset-0 flex items-center justify-center">
              <Users className="h-7 w-7 text-amber-400" />
            </div>
          </div>
          <div>
            <div className="text-sm text-amber-400 font-semibold">Querying 3 AI models on <span className="text-white">{ticker}</span></div>
            <div className="text-[10px] mt-2 text-slate-600 flex items-center justify-center gap-3">
              <span className="flex items-center gap-1"><Bot className="h-3 w-3" /> GPT-4o-mini</span>
              <span className="flex items-center gap-1"><Sparkles className="h-3 w-3" /> Claude 3.5 Haiku</span>
              <span className="flex items-center gap-1"><Diamond className="h-3 w-3" /> Gemini 2.5 Flash</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!data?.verdicts?.length) {
    return (
      <div className="h-[350px] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
            <Users className="h-6 w-6 text-slate-600" />
          </div>
          <div>
            <div className="text-sm text-slate-500 font-medium">Multi-Model Consensus</div>
            <div className="text-[10px] mt-1 text-slate-700">3 AI models vote independently on the same signal</div>
          </div>
          <div className="text-[10px] text-slate-600 bg-white/[0.02] border border-white/[0.06] rounded-lg px-3 py-1.5 inline-block">
            Click the <span className="text-amber-400 font-bold">Consensus</span> tab to start
          </div>
        </div>
      </div>
    );
  }

  const consensusColor = data.consensus === "LONG" ? "text-green-400" : data.consensus === "SHORT" ? "text-red-400" : "text-yellow-400";
  const consensusBg = data.consensus === "LONG" ? "from-green-500/10" : data.consensus === "SHORT" ? "from-red-500/10" : "from-yellow-500/10";

  return (
    <div className="space-y-4">
      {/* Consensus Header */}
      <div className={`relative overflow-hidden flex items-center justify-between p-4 rounded-xl bg-gradient-to-r ${consensusBg} to-transparent border border-white/[0.06]`} style={{ backdropFilter: "blur(12px)" }}>
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        <div>
          <div className="text-[10px] text-slate-500 font-semibold tracking-wider">MULTI-MODEL CONSENSUS</div>
          <div className={`text-2xl font-black tracking-widest ${consensusColor}`}>{data.consensus}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-slate-500 font-semibold tracking-wider">AGREEMENT</div>
          <div className="text-xl font-bold text-white">{data.agreement} <span className="text-sm text-slate-500">({data.agreement_pct}%)</span></div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-slate-500 font-semibold tracking-wider">AVG. CONFIDENCE</div>
          <div className="text-xl font-bold text-white">{data.avg_confidence}%</div>
        </div>
      </div>

      {/* Scoring Context */}
      {data.regime && (
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.06] text-[10px]">
          <span className="text-slate-500 font-semibold">REGIME</span>
          <span className={`px-1.5 py-0.5 rounded font-bold ${
            data.regime === "LOW_LIQUIDITY" ? "bg-red-500/20 text-red-400" :
            data.regime?.includes("TRENDING") ? "bg-cyan-500/20 text-cyan-400" :
            data.regime === "HIGH_VOLATILITY" ? "bg-amber-500/20 text-amber-400" :
            "bg-slate-500/20 text-slate-400"
          }`}>{data.regime}</span>
          <span className="text-slate-500 font-semibold">GRADE</span>
          <span className={`px-1.5 py-0.5 rounded font-bold ${
            data.signal_grade?.startsWith("A") ? "bg-green-500/20 text-green-400" :
            data.signal_grade === "B" ? "bg-cyan-500/20 text-cyan-400" :
            "bg-red-500/20 text-red-400"
          }`}>{data.signal_grade}</span>
          <span className="text-slate-500 font-semibold">SCORE</span>
          <span className={`font-bold ${
            (data.strategy_score ?? 0) > 20 ? "text-green-400" :
            (data.strategy_score ?? 0) < -20 ? "text-red-400" :
            "text-yellow-400"
          }`}>{data.strategy_score}/100</span>
          <span className="text-slate-500 font-semibold">DIR</span>
          <span className={`font-bold ${
            data.strategy_direction === "LONG" ? "text-green-400" :
            data.strategy_direction === "SHORT" ? "text-red-400" :
            "text-yellow-400"
          }`}>{data.strategy_direction}</span>
        </div>
      )}

      {/* Individual Model Verdicts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.verdicts.map((v: any, i: number) => {
          const sigBorder = v.signal === "LONG" ? "border-green-500/20" : v.signal === "SHORT" ? "border-red-500/20" : "border-slate-500/20";
          const sigText = v.signal === "LONG" ? "text-green-400" : v.signal === "SHORT" ? "text-red-400" : "text-yellow-400";
          const ModelIcon = v.model?.includes("gpt") ? Bot : v.model?.includes("claude") ? Sparkles : Diamond;
          const modelLabel = v.model?.includes("gpt") ? "GPT-4o" : v.model?.includes("claude") ? "Claude" : v.model?.includes("gemini") ? "Gemini" : v.model;

          return (
            <div key={i} className={`relative overflow-hidden p-4 rounded-xl border ${sigBorder} bg-white/[0.02]`} style={{ backdropFilter: "blur(8px)" }}>
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] text-slate-400 font-bold flex items-center gap-1.5">
                  <ModelIcon className="h-3.5 w-3.5" /> {modelLabel}
                </span>
                <span className={`text-xs font-black px-2 py-0.5 rounded ${sigText} bg-white/[0.04]`}>{v.signal || "?"}</span>
              </div>
              <div className="text-xs text-slate-400 space-y-1.5">
                {v.confidence !== undefined && <div>Confidence: <span className="text-white font-semibold">{v.confidence}%</span></div>}
                {v.entry && <div>Entry: <span className="text-white font-semibold">{v.entry}</span></div>}
                {v.stop_loss && <div>SL: <span className="text-red-400 font-semibold">{v.stop_loss}</span></div>}
                {v.take_profit && <div>TP: <span className="text-green-400 font-semibold">{v.take_profit}</span></div>}
                {v.reason && <div className="mt-2 text-[10px] text-slate-500 leading-relaxed border-t border-white/[0.04] pt-2">{v.reason}</div>}
                {v.error && <div className="mt-2 text-[10px] text-red-400">{v.error}</div>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-2 text-[10px] text-slate-600 text-center">
        Scanned: {data.scanned_at ? new Date(data.scanned_at).toLocaleTimeString() : "—"} • {data.ticker} on {data.timeframe}
      </div>
    </div>
  );
}
