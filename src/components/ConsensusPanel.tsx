"use client";

export function ConsensusPanel({ data, isRunning, ticker }: { data: any, isRunning: boolean, ticker: string }) {
  if (isRunning) {
    return (
      <div className="h-[350px] flex items-center justify-center text-amber-400">
        <div className="text-center">
          <div className="text-3xl mb-2 animate-pulse">🗳️</div>
          <div className="text-sm">Querying 3 AI models on <span className="text-white font-bold">{ticker}</span>...</div>
          <div className="text-[10px] mt-2 text-slate-600">GPT-4o-mini • Claude 3.5 Haiku • Gemini 2.0 Flash</div>
        </div>
      </div>
    );
  }

  if (!data?.verdicts?.length) {
    return (
      <div className="h-[350px] flex items-center justify-center text-slate-600">
        <div className="text-center">
          <div className="text-3xl mb-2">🗳️</div>
          <div className="text-sm">Click CONSENSUS to run multi-model voting</div>
          <div className="text-[10px] mt-1 text-slate-700">3 AI models vote independently on the same signal</div>
        </div>
      </div>
    );
  }

  const consensusColor = data.consensus === "LONG" ? "text-green-400" : data.consensus === "SHORT" ? "text-red-400" : "text-yellow-400";

  return (
    <div>
      {/* Consensus Header */}
      <div className="flex items-center justify-between mb-4 p-3 rounded bg-black/40 border border-white/10">
        <div>
          <div className="text-xs text-slate-500">MULTI-MODEL CONSENSUS</div>
          <div className={`text-2xl font-black tracking-widest ${consensusColor}`}>{data.consensus}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">Agreement</div>
          <div className="text-xl font-bold text-white">{data.agreement} <span className="text-sm text-slate-500">({data.agreement_pct}%)</span></div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">Avg. Confidence</div>
          <div className="text-xl font-bold text-white">{data.avg_confidence}%</div>
        </div>
      </div>

      {/* Individual Model Verdicts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.verdicts.map((v: any, i: number) => {
          const sigColor = v.signal === "LONG" ? "border-green-500/30 bg-green-500/5" : v.signal === "SHORT" ? "border-red-500/30 bg-red-500/5" : "border-slate-500/30 bg-slate-500/5";
          const sigText = v.signal === "LONG" ? "text-green-400" : v.signal === "SHORT" ? "text-red-400" : "text-yellow-400";

          return (
            <div key={i} className={`p-3 rounded border ${sigColor}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-slate-500 font-bold">
                  {v.model === "gpt-4o-mini" ? "🤖 GPT-4o" :
                   v.model?.includes("claude") ? "🟣 Claude" :
                   v.model?.includes("gemini") ? "💎 Gemini" : v.model}
                </span>
                <span className={`text-xs font-black ${sigText}`}>{v.signal || "?"}</span>
              </div>
              <div className="text-xs text-slate-400 space-y-1">
                {v.confidence !== undefined && <div>Confidence: <span className="text-white">{v.confidence}%</span></div>}
                {v.entry && <div>Entry: <span className="text-white">{v.entry}</span></div>}
                {v.stop_loss && <div>SL: <span className="text-red-400">{v.stop_loss}</span></div>}
                {v.take_profit && <div>TP: <span className="text-green-400">{v.take_profit}</span></div>}
                {v.reason && <div className="mt-2 text-[10px] text-slate-500 italic">{v.reason}</div>}
                {v.error && <div className="mt-2 text-[10px] text-red-400">{v.error}</div>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 text-[10px] text-slate-600 text-center">
        Scanned: {data.scanned_at ? new Date(data.scanned_at).toLocaleTimeString() : "—"} • {data.ticker} on {data.timeframe}
      </div>
    </div>
  );
}
