"use client";

import { useState, useEffect } from "react";
import { SignalPayload } from "@/components/types";
import { ChevronDown, ChevronUp, Copy, Check, Flame, Clock } from "lucide-react";

interface SignalStripProps {
  signal: SignalPayload;
  currentPrice?: number;
}

export function SignalStrip({ signal, currentPrice }: SignalStripProps) {
  const [expanded, setExpanded] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [ageMinutes, setAgeMinutes] = useState(0);

  const isLong = signal.signal === "LONG";
  const isShort = signal.signal === "SHORT";
  const isNoTrade = !isLong && !isShort;

  // Signal age timer
  useEffect(() => {
    if (!signal.timestamp_utc) return;
    const update = () => {
      const signalTime = new Date(signal.timestamp_utc!).getTime();
      setAgeMinutes(Math.floor((Date.now() - signalTime) / 60000));
    };
    update();
    const interval = setInterval(update, 30000);
    return () => clearInterval(interval);
  }, [signal.timestamp_utc]);

  // Copy helper
  const copyPrice = (label: string, value: string) => {
    navigator.clipboard.writeText(value);
    setCopiedField(label);
    setTimeout(() => setCopiedField(null), 1500);
  };

  // Price proximity
  const entryMid = (signal.entry_zone.min + signal.entry_zone.max) / 2;
  const proximityPct = currentPrice ? Math.abs((currentPrice - entryMid) / entryMid) * 100 : null;

  // Urgency score (0-6)
  const gradeScore = signal.signal_grade === "A+" ? 3 : signal.signal_grade === "A" ? 2.5 : signal.signal_grade === "B" ? 1.5 : 0;
  const confScore = (signal.confidence || 0) > 60 ? 1.5 : (signal.confidence || 0) > 40 ? 0.75 : 0;
  const factorScore = (signal.factors_aligned || 0) >= 4 ? 1 : 0;
  const urgency = gradeScore + confScore + factorScore;
  const isHot = urgency >= 4.5;
  const isWarm = urgency >= 2.5;

  // Grade color
  const gradeColor = (g?: string) => {
    if (g === "A+") return "text-green-400 bg-green-500/15 border-green-500/40";
    if (g === "A") return "text-emerald-400 bg-emerald-500/15 border-emerald-500/40";
    if (g === "B") return "text-yellow-400 bg-yellow-500/15 border-yellow-500/40";
    if (g === "C") return "text-orange-400 bg-orange-500/15 border-orange-500/40";
    return "text-red-400 bg-red-500/15 border-red-500/40";
  };

  // Direction colors
  const dirBg = isLong
    ? "bg-green-500 text-black"
    : isShort
    ? "bg-red-500 text-white"
    : "bg-yellow-500/80 text-black";

  // Freshness dot
  const freshColor = ageMinutes < 5 ? "bg-green-400" : ageMinutes < 30 ? "bg-amber-400" : "bg-red-400";

  // Card border animation
  const cardAnimation = isHot
    ? "animate-[hot-pulse_2s_ease-in-out_infinite]"
    : isWarm
    ? "animate-[urgency-glow_3s_ease-in-out_infinite]"
    : "";

  const dirBorder = isLong ? "border-green-500/30 hover:border-green-500/50" : isShort ? "border-red-500/30 hover:border-red-500/50" : "border-yellow-500/30";

  // Price level row helper
  const PriceRow = ({ label, value, color }: { label: string; value: string; color: string }) => (
    <div className="flex items-center justify-between gap-2 py-1 px-2 rounded bg-white/[0.02] group">
      <span className="text-[10px] text-slate-500 font-medium w-8">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${color}`}>{value}</span>
      <button
        onClick={(e) => { e.stopPropagation(); copyPrice(label, value); }}
        className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-white/10 transition-all"
      >
        {copiedField === label
          ? <Check className="h-3 w-3 text-green-400" />
          : <Copy className="h-3 w-3 text-slate-500" />
        }
      </button>
    </div>
  );

  if (isNoTrade) {
    return (
      <div className="bg-white/[0.03] backdrop-blur-md border border-white/8 rounded-xl p-3 shadow-lg shadow-black/20">
        <div className="flex items-center gap-3">
          <span className="px-3 py-1 rounded font-black text-sm tracking-widest bg-slate-700 text-slate-300">NO TRADE</span>
          <span className="text-xs text-slate-500">Conditions don't support a trade right now</span>
          {signal.signal_grade && (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${gradeColor(signal.signal_grade)}`}>
              {signal.signal_grade}
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-in slide-in-from-bottom-2 fade-in duration-500">
      <div
        className={`bg-white/[0.03] backdrop-blur-xl border ${dirBorder} rounded-lg overflow-hidden cursor-pointer transition-all shadow-lg shadow-black/20 ${cardAnimation}`}
        onClick={() => setExpanded(prev => !prev)}
      >
        {/* Color accent bar */}
        <div className={`h-1 w-full ${isLong ? "bg-green-500" : "bg-red-500"}`} />

        {/* ═══ HERO: Direction + Grade + Levels ═══ */}
        <div className="flex flex-col sm:flex-row gap-4 px-4 py-3">

          {/* Left: Direction + Grade + Confidence + R:R */}
          <div className="flex items-center sm:items-start gap-3 sm:flex-col sm:gap-2 sm:min-w-[140px]">
            <div className="flex items-center gap-2">
              <span className={`px-4 py-1.5 rounded font-black text-xl tracking-widest ${dirBg}`}>
                {signal.signal}
              </span>
              {isHot && (
                <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-500/20 border border-red-500/40 text-red-400 text-[10px] font-bold">
                  <Flame className="h-3 w-3" /> HOT
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Grade */}
              {signal.signal_grade && (
                <span className={`px-2 py-0.5 rounded text-sm font-black border ${gradeColor(signal.signal_grade)}`}>
                  {signal.signal_grade}
                </span>
              )}

              {/* Confidence ring */}
              <div className="relative w-9 h-9 flex items-center justify-center">
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    background: `conic-gradient(${isLong ? '#22c55e' : '#ef4444'} ${(signal.confidence || 0) * 3.6}deg, rgba(255,255,255,0.06) 0deg)`,
                    mask: "radial-gradient(farthest-side, transparent calc(100% - 3px), black calc(100% - 2px))",
                    WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 3px), black calc(100% - 2px))",
                  }}
                />
                <span className="text-[10px] font-bold text-white">{signal.confidence}%</span>
              </div>

              {/* R:R */}
              <span className="text-xs text-slate-400">
                R:R <span className="text-white font-bold">{signal.risk_reward}</span>
              </span>
            </div>
          </div>

          {/* Right: Price Levels Table */}
          <div className="flex-1 space-y-1">
            <PriceRow
              label="Entry"
              value={`${signal.entry_zone.min.toFixed(2)} - ${signal.entry_zone.max.toFixed(2)}`}
              color="text-white"
            />
            <PriceRow label="SL" value={signal.stop_loss.toFixed(2)} color="text-red-400" />
            {signal.take_profit.slice(0, 2).map((tp) => (
              <PriceRow key={tp.level} label={`TP${tp.level}`} value={tp.price.toFixed(2)} color="text-green-400" />
            ))}
          </div>

          {/* Top-right badges: Freshness + Proximity */}
          <div className="flex sm:flex-col items-end gap-1.5 flex-shrink-0">
            {/* Freshness */}
            {signal.timestamp_utc && (
              <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
                <div className={`w-1.5 h-1.5 rounded-full ${freshColor}`} />
                <Clock className="h-3 w-3" />
                {ageMinutes < 1 ? "Just now" : `${ageMinutes}m ago`}
              </div>
            )}

            {/* Proximity */}
            {proximityPct !== null && (
              <div className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                proximityPct < 0.1 ? "bg-green-500/20 text-green-400 animate-pulse" :
                proximityPct < 0.3 ? "bg-amber-500/20 text-amber-400" :
                "bg-slate-800 text-slate-400"
              }`}>
                {proximityPct < 0.1 ? "AT ENTRY" : proximityPct < 0.3 ? "NEAR" : `${proximityPct.toFixed(1)}% away`}
              </div>
            )}

            {/* Expand chevron */}
            <div className="mt-auto">
              {expanded ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
            </div>
          </div>
        </div>

        {/* ═══ METRICS GRID ═══ */}
        <div className="grid grid-cols-4 gap-1.5 px-4 pb-3">
          {[
            { label: "Size", value: `${signal.position_size_pct}%` },
            { label: "Factors", value: `${signal.factors_aligned ?? "—"}/5` },
            { label: "Regime", value: signal.market_regime || "—" },
            { label: "OF Bias", value: signal.order_flow_bias || "—", color: signal.order_flow_bias === "BULLISH" ? "text-green-400" : signal.order_flow_bias === "BEARISH" ? "text-red-400" : undefined },
            { label: "MTF", value: signal.mtf_confluence_label || "—", color: signal.mtf_confluence_label === "STRONG" ? "text-cyan-400" : signal.mtf_confluence_label === "MODERATE" ? "text-blue-400" : undefined },
            { label: "MTF Mult", value: signal.mtf_confluence_multiplier ? `${signal.mtf_confluence_multiplier}x` : "—" },
            { label: "Max Hold", value: signal.max_hold_minutes ? `${signal.max_hold_minutes}m` : "—" },
            { label: "OF Agrees", value: signal.order_flow_agrees === true ? "Yes" : signal.order_flow_agrees === false ? "No" : "—", color: signal.order_flow_agrees === true ? "text-green-400" : signal.order_flow_agrees === false ? "text-red-400" : undefined },
          ].map((m) => (
            <div key={m.label} className="bg-white/[0.03] rounded px-2 py-1.5 text-center">
              <div className="text-[9px] text-slate-600 font-medium">{m.label}</div>
              <div className={`text-[11px] font-semibold ${m.color || "text-slate-300"}`}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ═══ EXPANDED DETAIL ═══ */}
      {expanded && (
        <div className="mt-1.5 bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-lg p-4 space-y-4 animate-in slide-in-from-top-2 fade-in duration-300 shadow-lg shadow-black/20">
          {/* Confluence Grid */}
          {signal.confluences && signal.confluences.length > 0 && (
            <div>
              <h3 className="text-[10px] text-slate-500 font-semibold tracking-wider mb-2">5-Factor Confluence</h3>
              <div className="grid grid-cols-5 gap-2">
                {signal.confluences.map((c, i) => (
                  <div key={i} className={`p-2 rounded border text-center group relative ${
                    c.direction === "BULLISH" ? "bg-green-500/5 border-green-500/20" :
                    c.direction === "BEARISH" ? "bg-red-500/5 border-red-500/20" :
                    "bg-slate-500/5 border-slate-500/20"
                  }`}>
                    <div className="text-[10px] text-slate-500 font-medium">{c.name}</div>
                    <div className={`text-sm font-black ${
                      c.direction === "BULLISH" ? "text-green-400" :
                      c.direction === "BEARISH" ? "text-red-400" :
                      "text-slate-400"
                    }`}>
                      {c.score > 0 ? "+" : ""}{c.score}
                    </div>
                    <div className="text-[9px] text-slate-600">{c.weight}%</div>
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
                <h4 className="text-[10px] text-slate-500 font-semibold tracking-wider mb-2">Indicators</h4>
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
              <h4 className="text-[10px] text-slate-500 font-semibold tracking-wider mb-2">TV Webhook</h4>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-white/[0.04] border border-white/10 px-2 py-1 rounded text-[10px] text-cyan-400 break-all truncate">
                  {signal.tv_alert}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); copyPrice("webhook", signal.tv_alert); }}
                  className="p-1.5 rounded border border-white/10 hover:bg-white/5 transition-colors flex-shrink-0"
                >
                  {copiedField === "webhook" ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5 text-slate-400" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
