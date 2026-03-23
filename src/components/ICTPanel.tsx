"use client";

import { TermTooltip } from "@/components/TermTooltip";

export function ICTPanel({ data, isRunning, ticker }: { data: any, isRunning: boolean, ticker: string }) {
  if (isRunning) {
    return (
      <div className="h-[350px] flex items-center justify-center text-emerald-400">
        <div className="text-center">
          <div className="text-3xl mb-2 animate-pulse">🏦</div>
          <div className="text-sm">Detecting Smart Money on <span className="text-white font-bold">{ticker}</span>...</div>
          <div className="text-[10px] mt-2 text-slate-600">CHoCH • BOS • Order Blocks • Fair Value Gaps</div>
        </div>
      </div>
    );
  }

  if (!data?.ict || data.error) {
    return (
      <div className="h-[350px] flex items-center justify-center text-slate-600">
        <div className="text-center">
          <div className="text-3xl mb-2">🏦</div>
          <div className="text-sm">Click ICT to run Smart Money analysis</div>
          <div className="text-[10px] mt-1 text-slate-700">Market Structure • Order Blocks • FVG Detection</div>
        </div>
      </div>
    );
  }

  const ict = data.ict;
  const structColor = ict.market_structure?.includes("BULLISH") ? "text-green-400" : ict.market_structure?.includes("BEARISH") ? "text-red-400" : "text-yellow-400";

  return (
    <div>
      {/* Structure Header */}
      <div className="flex items-center justify-between mb-4 p-3 rounded bg-black/40 border border-white/10">
        <div>
          <div className="text-xs text-slate-500">MARKET STRUCTURE</div>
          <div className={`text-xl font-black tracking-widest ${structColor}`}>{ict.market_structure || "UNKNOWN"}</div>
        </div>
        <div className="text-right text-xs text-slate-500">
          {data.ticker} • {data.timeframe}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Structure Events */}
        <div className="p-3 rounded border border-emerald-500/20 bg-emerald-500/5">
          <div className="text-[10px] text-emerald-400 font-bold mb-2">
            📐 <TermTooltip term="Market Structure" description="BOS (Break of Structure) means trend continuation. CHoCH (Change of Character) signals a potential trend reversal.">STRUCTURE (BOS/CHoCH)</TermTooltip>
          </div>
          {ict.structure_events?.length ? ict.structure_events.map((e: any, i: number) => (
            <div key={i} className="mb-1.5">
              <span className={`text-xs font-bold ${e.direction === "BULLISH" ? "text-green-400" : "text-red-400"}`}>
                {e.type}: {e.direction}
              </span>
              <div className="text-[10px] text-slate-500">{e.detail}</div>
            </div>
          )) : <div className="text-[10px] text-slate-600">No structure breaks detected</div>}
        </div>

        {/* Order Blocks */}
        <div className="p-3 rounded border border-blue-500/20 bg-blue-500/5">
          <div className="text-[10px] text-blue-400 font-bold mb-2">
            🧱 <TermTooltip term="Order Block (OB)" description="An area of intense institutional buying or selling where large unexecuted orders often linger. Acts as significant support/resistance.">ORDER BLOCKS</TermTooltip>
          </div>
          {ict.order_blocks?.length ? ict.order_blocks.map((ob: any, i: number) => (
            <div key={i} className="mb-1.5">
              <span className={`text-xs font-bold ${ob.type.includes("BULLISH") ? "text-green-400" : "text-red-400"}`}>
                {ob.type}
              </span>
              <div className="text-[10px] text-slate-400">Zone: {ob.bottom} — {ob.top}</div>
            </div>
          )) : <div className="text-[10px] text-slate-600">No order blocks detected</div>}
        </div>

        {/* Fair Value Gaps */}
        <div className="p-3 rounded border border-violet-500/20 bg-violet-500/5">
          <div className="text-[10px] text-violet-400 font-bold mb-2">
            📏 <TermTooltip term="Fair Value Gap (FVG)" description="A 3-candle pattern showing price inefficiency. Price naturally pulls back to fill these gaps over time.">FAIR VALUE GAPS</TermTooltip>
          </div>
          {ict.fair_value_gaps?.length ? ict.fair_value_gaps.map((fvg: any, i: number) => (
            <div key={i} className="mb-1.5">
              <span className={`text-xs font-bold ${fvg.type.includes("BULLISH") ? "text-green-400" : "text-red-400"}`}>
                {fvg.type}
              </span>
              <div className="text-[10px] text-slate-400">Gap: {fvg.bottom} — {fvg.top} (size: {fvg.size})</div>
            </div>
          )) : <div className="text-[10px] text-slate-600">No FVGs detected</div>}
        </div>
      </div>

      {/* Key Levels */}
      <div className="mt-3 flex gap-4">
        {ict.recent_swing_highs?.length > 0 && (
          <div className="text-[10px] text-slate-500">
            🔺 Resistance: <span className="text-red-400 font-bold">{ict.recent_swing_highs.map((s: any) => s.price).join(", ")}</span>
          </div>
        )}
        {ict.recent_swing_lows?.length > 0 && (
          <div className="text-[10px] text-slate-500">
            🔻 Support: <span className="text-green-400 font-bold">{ict.recent_swing_lows.map((s: any) => s.price).join(", ")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
