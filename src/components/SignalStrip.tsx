"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { SignalPayload } from "@/components/types";
import { ChevronDown, ChevronUp, Copy, Check } from "lucide-react";

interface SignalStripProps {
  signal: SignalPayload;
}

export function SignalStrip({ signal }: SignalStripProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const isLong = signal.signal === "LONG";
  const isShort = signal.signal === "SHORT";

  const dirColor = isLong ? "green" : isShort ? "red" : "yellow";
  const dirBg = isLong
    ? "bg-green-500 text-black shadow-[0_0_15px_rgba(34,197,94,0.4)]"
    : isShort
    ? "bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.4)]"
    : "bg-yellow-500 text-black";

  const gradeColor = (g?: string) => {
    if (g === "A+") return "text-green-400 bg-green-500/15 border-green-500/40";
    if (g === "A") return "text-emerald-400 bg-emerald-500/15 border-emerald-500/40";
    if (g === "B") return "text-yellow-400 bg-yellow-500/15 border-yellow-500/40";
    if (g === "C") return "text-orange-400 bg-orange-500/15 border-orange-500/40";
    return "text-red-400 bg-red-500/15 border-red-500/40";
  };

  const copyWebhook = () => {
    navigator.clipboard.writeText(signal.tv_alert);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="animate-in slide-in-from-bottom-2 fade-in duration-500">
      {/* Compact Strip */}
      <div
        className={`bg-slate-900 border border-${dirColor}-500/30 rounded-lg overflow-hidden cursor-pointer transition-all hover:border-${dirColor}-500/50`}
        onClick={() => setExpanded(prev => !prev)}
      >
        <div className={`h-1 w-full ${isLong ? "bg-green-500" : isShort ? "bg-red-500" : "bg-yellow-500"}`} />

        {/* Row 1: Direction + Execution Params */}
        <div className="flex items-center justify-between px-4 py-2.5 gap-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`px-4 py-1 rounded font-black text-lg tracking-widest ${dirBg}`}>
              {signal.signal}
            </span>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-slate-400">
                Entry: <span className="text-white font-bold">{signal.entry_zone.min.toFixed(2)} - {signal.entry_zone.max.toFixed(2)}</span>
              </span>
              <span className="text-slate-400">
                SL: <span className="text-red-400 font-bold">{signal.stop_loss.toFixed(2)}</span>
              </span>
              {signal.take_profit.slice(0, 2).map((tp) => (
                <span key={tp.level} className="text-slate-400">
                  TP{tp.level}: <span className="text-green-400 font-bold">{tp.price.toFixed(2)}</span>
                </span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {expanded ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
          </div>
        </div>

        {/* Row 2: Grade + Metrics */}
        <div className="flex items-center gap-2 px-4 pb-2.5 flex-wrap">
          {signal.signal_grade && (
            <span className={`px-2 py-0.5 rounded text-xs font-black border ${gradeColor(signal.signal_grade)}`}>
              {signal.signal_grade}
            </span>
          )}
          <span className="text-xs text-slate-500">
            Conf: <span className="text-white font-bold">{signal.confidence}%</span>
          </span>
          <span className="text-xs text-slate-500">
            R:R <span className="text-white font-bold">{signal.risk_reward}</span>
          </span>
          <span className="text-xs text-slate-500">
            Size: <span className="text-white font-bold">{signal.position_size_pct}%</span>
          </span>
          {signal.factors_aligned !== undefined && (
            <span className="text-xs text-slate-500">{signal.factors_aligned}/5 factors</span>
          )}
          {signal.market_regime && (
            <Badge variant="outline" className="text-[10px] text-slate-400 border-slate-500/30">
              {signal.market_regime}
            </Badge>
          )}
          {signal.order_flow_bias && signal.order_flow_bias !== "NEUTRAL" && (
            <Badge variant="outline" className={`text-[10px] ${
              signal.order_flow_bias === "BULLISH" ? "text-green-400 border-green-500/30 bg-green-500/10" :
              "text-red-400 border-red-500/30 bg-red-500/10"
            }`}>
              OF: {signal.order_flow_bias}
            </Badge>
          )}
          {signal.mtf_confluence_label && signal.mtf_confluence_label !== "NEUTRAL" && (
            <Badge variant="outline" className={`text-[10px] ${
              signal.mtf_confluence_label === "STRONG" ? "text-cyan-400 border-cyan-500/30 bg-cyan-500/10" :
              signal.mtf_confluence_label === "MODERATE" ? "text-blue-400 border-blue-500/30 bg-blue-500/10" :
              "text-orange-400 border-orange-500/30 bg-orange-500/10"
            }`}>
              MTF: {signal.mtf_confluence_label} ({signal.mtf_confluence_multiplier}x)
            </Badge>
          )}
        </div>
      </div>

      {/* Expanded Detail */}
      {expanded && (
        <div className="mt-1 bg-slate-900/80 border border-white/10 rounded-lg p-4 space-y-4 animate-in slide-in-from-top-2 fade-in duration-300">
          {/* Confluence Grid */}
          {signal.confluences && signal.confluences.length > 0 && (
            <div>
              <h3 className="text-[10px] text-slate-500 font-bold tracking-widest uppercase mb-2">5-FACTOR CONFLUENCE</h3>
              <div className="grid grid-cols-5 gap-2">
                {signal.confluences.map((c, i) => (
                  <div key={i} className={`p-2 rounded border text-center group relative ${
                    c.direction === "BULLISH" ? "bg-green-500/5 border-green-500/20" :
                    c.direction === "BEARISH" ? "bg-red-500/5 border-red-500/20" :
                    "bg-slate-500/5 border-slate-500/20"
                  }`}>
                    <div className="text-[10px] text-slate-500 font-bold">{c.name}</div>
                    <div className={`text-sm font-black ${
                      c.direction === "BULLISH" ? "text-green-400" :
                      c.direction === "BEARISH" ? "text-red-400" :
                      "text-slate-400"
                    }`}>
                      {c.score > 0 ? "+" : ""}{c.score}
                    </div>
                    <div className="text-[9px] text-slate-600">{c.weight}%</div>
                    {/* Tooltip with signals */}
                    {c.signals && c.signals.length > 0 && (
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50 w-48 p-2 bg-black border border-white/20 rounded text-left text-[10px] text-slate-300 shadow-xl">
                        {c.signals.map((s, j) => (
                          <div key={j} className="py-0.5">{s}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Indicators */}
            {signal.indicators_used && (
              <div>
                <h4 className="text-[10px] text-slate-500 font-bold tracking-widest uppercase mb-2">Indicators</h4>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(signal.indicators_used).map(([key, val]) => (
                    val !== null && (
                      <span key={key} className="text-[10px] px-1.5 py-0.5 bg-cyan-500/10 border border-cyan-500/20 rounded text-cyan-400">
                        {key}: {val}
                      </span>
                    )
                  ))}
                </div>
              </div>
            )}

            {/* Webhook */}
            <div>
              <h4 className="text-[10px] text-slate-500 font-bold tracking-widest uppercase mb-2">TV Webhook</h4>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-black/60 border border-white/10 px-2 py-1 rounded text-[10px] text-cyan-400 break-all truncate">
                  {signal.tv_alert}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); copyWebhook(); }}
                  className="p-1.5 rounded border border-white/10 hover:bg-white/5 transition-colors flex-shrink-0"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5 text-slate-400" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
