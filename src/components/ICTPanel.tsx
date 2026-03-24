"use client";

import { TermTooltip } from "@/components/TermTooltip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Landmark, Layers, BarChart2, ArrowUpDown } from "lucide-react";

export function ICTPanel({ data, isRunning, ticker }: { data: any, isRunning: boolean, ticker: string }) {
  if (isRunning) {
    return (
      <div className="h-[450px] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="relative">
            <div className="h-16 w-16 mx-auto rounded-full border-2 border-emerald-500/30 border-t-emerald-400 animate-spin" />
            <Landmark className="h-6 w-6 text-emerald-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          </div>
          <div className="text-sm text-emerald-400 font-bold tracking-wider">DETECTING SMART MONEY ON <span className="text-white">{ticker}</span></div>
          <div className="text-[10px] text-slate-600">CHoCH • BOS • Order Blocks • Fair Value Gaps</div>
        </div>
      </div>
    );
  }

  if (!data?.ict || data.error) {
    return (
      <div className="h-[450px] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="h-16 w-16 mx-auto rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <Landmark className="h-8 w-8 text-emerald-500/40" />
          </div>
          <div className="text-sm text-slate-500">Click ICT to run Smart Money analysis</div>
          <div className="text-[10px] text-slate-700">Market Structure • Order Blocks • FVG Detection</div>
        </div>
      </div>
    );
  }

  const ict = data.ict;
  const isB = ict.market_structure?.includes("BULLISH");
  const isBear = ict.market_structure?.includes("BEARISH");
  const structColor = isB ? "text-green-400" : isBear ? "text-red-400" : "text-yellow-400";
  const structBg = isB ? "from-green-500/10 border-green-500/20" : isBear ? "from-red-500/10 border-red-500/20" : "from-yellow-500/10 border-yellow-500/20";

  return (
    <div className="space-y-4">
      {/* Structure Header */}
      <Card className={`bg-gradient-to-r ${structBg} to-transparent backdrop-blur-sm`}>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-500 font-bold tracking-wider mb-1">MARKET STRUCTURE</div>
            <div className={`text-2xl font-black tracking-widest ${structColor}`}>{ict.market_structure || "UNKNOWN"}</div>
          </div>
          <div className="text-right">
            <Badge variant="outline" className="border-white/10 text-slate-400 font-mono text-[10px]">
              {data.ticker} • {data.timeframe}
            </Badge>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Structure Events */}
        <Card className="border-emerald-500/15 bg-gradient-to-b from-emerald-500/5 to-transparent backdrop-blur-sm">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-[10px] text-emerald-400 font-bold tracking-wider flex items-center gap-2">
              <ArrowUpDown className="h-3 w-3" />
              <TermTooltip term="Market Structure" description="BOS (Break of Structure) means trend continuation. CHoCH (Change of Character) signals a potential trend reversal.">
                STRUCTURE (BOS/CHoCH)
              </TermTooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 space-y-2">
            {ict.structure_events?.length ? ict.structure_events.map((e: any, i: number) => (
              <div key={i} className="p-2 rounded-lg bg-black/20 border border-white/5">
                <span className={`text-xs font-bold ${e.direction === "BULLISH" ? "text-green-400" : "text-red-400"}`}>
                  {e.type}: {e.direction}
                </span>
                <div className="text-[10px] text-slate-500 mt-0.5">{e.detail}</div>
              </div>
            )) : <div className="text-[10px] text-slate-600 p-2">No structure breaks detected</div>}
          </CardContent>
        </Card>

        {/* Order Blocks */}
        <Card className="border-blue-500/15 bg-gradient-to-b from-blue-500/5 to-transparent backdrop-blur-sm">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-[10px] text-blue-400 font-bold tracking-wider flex items-center gap-2">
              <Layers className="h-3 w-3" />
              <TermTooltip term="Order Block (OB)" description="An area of intense institutional buying or selling where large unexecuted orders often linger. Acts as significant support/resistance.">
                ORDER BLOCKS
              </TermTooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 space-y-2">
            {ict.order_blocks?.length ? ict.order_blocks.map((ob: any, i: number) => (
              <div key={i} className="p-2 rounded-lg bg-black/20 border border-white/5">
                <span className={`text-xs font-bold ${ob.type.includes("BULLISH") ? "text-green-400" : "text-red-400"}`}>
                  {ob.type}
                </span>
                <div className="text-[10px] text-slate-400 mt-0.5">Zone: {ob.bottom} — {ob.top}</div>
              </div>
            )) : <div className="text-[10px] text-slate-600 p-2">No order blocks detected</div>}
          </CardContent>
        </Card>

        {/* Fair Value Gaps */}
        <Card className="border-violet-500/15 bg-gradient-to-b from-violet-500/5 to-transparent backdrop-blur-sm">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-[10px] text-violet-400 font-bold tracking-wider flex items-center gap-2">
              <BarChart2 className="h-3 w-3" />
              <TermTooltip term="Fair Value Gap (FVG)" description="A 3-candle pattern showing price inefficiency. Price naturally pulls back to fill these gaps over time.">
                FAIR VALUE GAPS
              </TermTooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 space-y-2">
            {ict.fair_value_gaps?.length ? ict.fair_value_gaps.map((fvg: any, i: number) => (
              <div key={i} className="p-2 rounded-lg bg-black/20 border border-white/5">
                <span className={`text-xs font-bold ${fvg.type.includes("BULLISH") ? "text-green-400" : "text-red-400"}`}>
                  {fvg.type}
                </span>
                <div className="text-[10px] text-slate-400 mt-0.5">Gap: {fvg.bottom} — {fvg.top} (size: {fvg.size})</div>
              </div>
            )) : <div className="text-[10px] text-slate-600 p-2">No FVGs detected</div>}
          </CardContent>
        </Card>
      </div>

      {/* Key Levels */}
      <div className="flex gap-4 px-1">
        {ict.recent_swing_highs?.length > 0 && (
          <div className="text-[10px] text-slate-500 flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-red-400" />
            Resistance: <span className="text-red-400 font-bold">{ict.recent_swing_highs.map((s: any) => s.price).join(", ")}</span>
          </div>
        )}
        {ict.recent_swing_lows?.length > 0 && (
          <div className="text-[10px] text-slate-500 flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-green-400" />
            Support: <span className="text-green-400 font-bold">{ict.recent_swing_lows.map((s: any) => s.price).join(", ")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
