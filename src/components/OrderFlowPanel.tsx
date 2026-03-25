"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { OrderFlowData, MtfOrderFlowData } from "@/components/types";

interface OrderFlowPanelProps {
  data: OrderFlowData | null;
  ticker: string;
  mtfData?: MtfOrderFlowData | null;
}

export function OrderFlowPanel({ data, ticker, mtfData }: OrderFlowPanelProps) {
  if (!data || !data.summary) {
    return (
      <div className="text-center text-slate-600 py-8">
        Run analysis to see order flow data for {ticker}.
      </div>
    );
  }

  const s = data.summary;
  const biasColor = s.overall_delta_bias === "BULLISH" ? "text-green-400" : s.overall_delta_bias === "BEARISH" ? "text-red-400" : "text-yellow-400";
  const cvdColor = s.cvd_trend === "RISING" ? "text-green-400" : s.cvd_trend === "FALLING" ? "text-red-400" : "text-slate-400";

  return (
    <div className="space-y-4">
      {/* Summary Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500 font-bold">DELTA BIAS</div>
          <div className={`text-lg font-black ${biasColor}`}>{s.overall_delta_bias}</div>
        </div>
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500 font-bold">CVD TREND</div>
          <div className={`text-lg font-black ${cvdColor}`}>{s.cvd_trend}</div>
        </div>
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500 font-bold">NET DELTA</div>
          <div className={`text-lg font-black ${s.total_recent_delta > 0 ? "text-green-400" : s.total_recent_delta < 0 ? "text-red-400" : "text-slate-400"}`}>
            {s.total_recent_delta > 0 ? "+" : ""}{s.total_recent_delta.toLocaleString()}
          </div>
        </div>
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500 font-bold">VWAP DEV</div>
          <div className={`text-lg font-black ${Math.abs(s.vwap_deviation) > 2 ? "text-amber-400" : "text-slate-300"}`}>
            {s.vwap_deviation > 0 ? "+" : ""}{s.vwap_deviation}σ
          </div>
        </div>
      </div>

      {/* Bar Balance */}
      <div className="p-3 rounded bg-black/40 border border-white/10">
        <div className="text-[10px] text-slate-500 font-bold mb-2">RECENT BAR DELTA (last 10)</div>
        <div className="flex gap-1 items-end h-8">
          <div className="flex-1 bg-green-500/20 rounded-sm relative" style={{ height: `${(s.recent_positive_bars / 10) * 100}%`, minHeight: "4px" }}>
            <span className="absolute inset-0 flex items-center justify-center text-[10px] text-green-400 font-bold">{s.recent_positive_bars}</span>
          </div>
          <div className="flex-1 bg-red-500/20 rounded-sm relative" style={{ height: `${(s.recent_negative_bars / 10) * 100}%`, minHeight: "4px" }}>
            <span className="absolute inset-0 flex items-center justify-center text-[10px] text-red-400 font-bold">{s.recent_negative_bars}</span>
          </div>
        </div>
        <div className="flex justify-between text-[10px] text-slate-600 mt-1">
          <span>Buying bars</span>
          <span>Selling bars</span>
        </div>
      </div>

      {/* Volume Profile */}
      {data.volume_profile && data.volume_profile.poc > 0 && (
        <Card className="bg-black/40 border-cyan-500/20">
          <CardHeader className="pb-2 border-b border-cyan-500/10">
            <CardTitle className="text-xs text-cyan-400 font-bold tracking-widest">VOLUME PROFILE</CardTitle>
          </CardHeader>
          <CardContent className="pt-3 space-y-2">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-[10px] text-slate-500">VAL</div>
                <div className="text-sm text-red-400 font-bold">{data.volume_profile.val.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">POC</div>
                <div className="text-sm text-yellow-400 font-bold">{data.volume_profile.poc.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">VAH</div>
                <div className="text-sm text-green-400 font-bold">{data.volume_profile.vah.toFixed(2)}</div>
              </div>
            </div>

            {/* Mini volume profile bars */}
            {data.volume_profile.levels && data.volume_profile.levels.length > 0 && (
              <div className="space-y-px mt-2">
                {data.volume_profile.levels
                  .filter(l => l.volume > 0)
                  .slice(-12)
                  .reverse()
                  .map((level, i) => {
                    const maxVol = Math.max(...data.volume_profile.levels.map(l => l.volume));
                    const pct = maxVol > 0 ? (level.volume / maxVol) * 100 : 0;
                    const isPoc = level.price === data.volume_profile.poc;
                    return (
                      <div key={i} className="flex items-center gap-2 h-3">
                        <span className="text-[9px] text-slate-600 w-16 text-right">{level.price.toFixed(1)}</span>
                        <div className="flex-1 h-full relative">
                          <div
                            className={`h-full rounded-r ${isPoc ? "bg-yellow-500/60" : "bg-cyan-500/30"}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Divergences */}
      {data.divergences && data.divergences.length > 0 && (
        <Card className="bg-black/40 border-amber-500/20">
          <CardHeader className="pb-2 border-b border-amber-500/10">
            <CardTitle className="text-xs text-amber-400 font-bold tracking-widest flex items-center gap-2">
              DIVERGENCES
              <Badge variant="outline" className="text-amber-400 border-amber-500/30 bg-amber-500/10 text-[10px]">
                {data.divergences.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-3 space-y-2">
            {data.divergences.map((div, i) => (
              <div key={i} className={`p-2 rounded text-xs border ${
                div.type === "BEARISH_DIVERGENCE"
                  ? "bg-red-500/5 border-red-500/20 text-red-300"
                  : "bg-green-500/5 border-green-500/20 text-green-300"
              }`}>
                <div className="font-bold text-[10px] mb-0.5">
                  {div.type === "BEARISH_DIVERGENCE" ? "BEARISH" : "BULLISH"} DIVERGENCE
                </div>
                <div className="text-slate-400">{div.description}</div>
                <div className="text-[10px] text-slate-600 mt-0.5">{div.bars_ago} bars ago</div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Absorptions */}
      {data.absorptions && data.absorptions.length > 0 && (
        <Card className="bg-black/40 border-purple-500/20">
          <CardHeader className="pb-2 border-b border-purple-500/10">
            <CardTitle className="text-xs text-purple-400 font-bold tracking-widest flex items-center gap-2">
              ABSORPTION ZONES
              <Badge variant="outline" className="text-purple-400 border-purple-500/30 bg-purple-500/10 text-[10px]">
                {data.absorptions.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-3 space-y-2">
            {data.absorptions.map((abs, i) => (
              <div key={i} className={`p-2 rounded text-xs border ${
                abs.type === "BULLISH_ABSORPTION"
                  ? "bg-green-500/5 border-green-500/20"
                  : "bg-red-500/5 border-red-500/20"
              }`}>
                <div className="flex justify-between items-center">
                  <span className={`font-bold text-[10px] ${abs.type === "BULLISH_ABSORPTION" ? "text-green-400" : "text-red-400"}`}>
                    {abs.type === "BULLISH_ABSORPTION" ? "BULLISH" : "BEARISH"}
                  </span>
                  <span className="text-slate-500 text-[10px]">{abs.volume_ratio}x vol</span>
                </div>
                <div className="text-slate-400 mt-0.5">{abs.description}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Stacked Imbalances */}
      {data.stacked_imbalances && data.stacked_imbalances.length > 0 && (
        <Card className="bg-black/40 border-emerald-500/20">
          <CardHeader className="pb-2 border-b border-emerald-500/10">
            <CardTitle className="text-xs text-emerald-400 font-bold tracking-widest">STACKED IMBALANCES</CardTitle>
          </CardHeader>
          <CardContent className="pt-3 space-y-2">
            {data.stacked_imbalances.map((imb, i) => (
              <div key={i} className={`p-2 rounded text-xs border ${
                imb.direction === "BUY"
                  ? "bg-green-500/5 border-green-500/20"
                  : "bg-red-500/5 border-red-500/20"
              }`}>
                <span className={`font-bold ${imb.direction === "BUY" ? "text-green-400" : "text-red-400"}`}>
                  {imb.bars_count}x {imb.direction}
                </span>
                <span className="text-slate-400 ml-2">{imb.description}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* MTF Order Flow Confluence */}
      {mtfData && mtfData.total_count > 0 && (
        <Card className={`bg-black/40 ${
          mtfData.confluence_label === "STRONG" ? "border-cyan-500/30" :
          mtfData.confluence_label === "MODERATE" ? "border-blue-500/20" :
          mtfData.confluence_label === "CONFLICTING" ? "border-orange-500/20" :
          "border-white/10"
        }`}>
          <CardHeader className="pb-2 border-b border-white/5">
            <CardTitle className="text-xs font-bold tracking-widest flex items-center gap-2">
              <span className={
                mtfData.confluence_label === "STRONG" ? "text-cyan-400" :
                mtfData.confluence_label === "MODERATE" ? "text-blue-400" :
                mtfData.confluence_label === "CONFLICTING" ? "text-orange-400" :
                "text-slate-400"
              }>MTF ORDER FLOW CONFLUENCE</span>
              <Badge variant="outline" className={`text-[10px] ${
                mtfData.confluence_label === "STRONG" ? "text-cyan-400 border-cyan-500/30 bg-cyan-500/10" :
                mtfData.confluence_label === "MODERATE" ? "text-blue-400 border-blue-500/30 bg-blue-500/10" :
                mtfData.confluence_label === "CONFLICTING" ? "text-orange-400 border-orange-500/30 bg-orange-500/10" :
                "text-slate-400 border-slate-500/30 bg-slate-500/10"
              }`}>
                {mtfData.confluence_label} ({mtfData.confluence_multiplier}x)
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-3 space-y-2">
            <div className="text-[10px] text-slate-500 font-bold mb-1">
              {mtfData.agreement_count}/{mtfData.total_count} TIMEFRAMES ALIGNED
            </div>
            {Object.entries(mtfData.tf_biases).map(([tf, bias]) => {
              const cvd = mtfData.tf_cvd[tf] || "FLAT";
              return (
                <div key={tf} className="flex items-center justify-between p-2 rounded bg-black/30 border border-white/5">
                  <span className="text-xs text-slate-300 font-mono uppercase">{tf}</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className={`text-[10px] ${
                      bias === "BULLISH" ? "text-green-400 border-green-500/30 bg-green-500/10" :
                      bias === "BEARISH" ? "text-red-400 border-red-500/30 bg-red-500/10" :
                      "text-slate-400 border-slate-500/30"
                    }`}>
                      {bias}
                    </Badge>
                    <span className={`text-[10px] ${
                      cvd === "RISING" ? "text-green-400" :
                      cvd === "FALLING" ? "text-red-400" :
                      "text-slate-500"
                    }`}>
                      CVD {cvd}
                    </span>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
