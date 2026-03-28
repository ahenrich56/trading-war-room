"use client";

import { useState, useEffect, useRef } from "react";
import { Radar, Check, X } from "lucide-react";

const AGENTS = [
  { key: "FUNDAMENTAL_ANALYST", label: "FUNDAMENTAL", short: "Fundamentals" },
  { key: "SENTIMENT_ANALYST", label: "SENTIMENT", short: "Sentiment" },
  { key: "NEWS_ANALYST", label: "NEWS", short: "News signals" },
  { key: "TECHNICAL_ANALYST", label: "TECHNICAL", short: "Technicals" },
  { key: "BEAR_RESEARCHER", label: "BEAR", short: "Bear case" },
  { key: "BULL_RESEARCHER", label: "BULL", short: "Bull case" },
  { key: "TRADER_DECISION", label: "TRADER", short: "Decision" },
  { key: "RISK_MANAGER", label: "RISK MGR", short: "Risk check" },
];

interface AnalysisHUDProps {
  isRunning: boolean;
  currentStage: string | null;
  agentData: Record<string, any>;
  ticker: string;
  progress: number;
  onCancel: () => void;
}

type Phase = "running" | "completing" | "exiting" | "done";

export function AnalysisHUD({
  isRunning,
  currentStage,
  agentData,
  ticker,
  progress,
  onCancel,
}: AnalysisHUDProps) {
  const [phase, setPhase] = useState<Phase>("done");
  const [elapsed, setElapsed] = useState(0);
  const [justCompleted, setJustCompleted] = useState<string | null>(null);
  const prevKeysRef = useRef<string[]>([]);
  const startTimeRef = useRef<number>(Date.now());

  // Phase state machine
  useEffect(() => {
    if (isRunning) {
      if (phase === "done" || phase === "exiting") {
        setPhase("running");
        setElapsed(0);
        startTimeRef.current = Date.now();
        prevKeysRef.current = [];
      }
    } else if (phase === "running") {
      // Analysis just finished
      setPhase("completing");
      const t1 = setTimeout(() => setPhase("exiting"), 2200);
      const t2 = setTimeout(() => setPhase("done"), 2700);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
  }, [isRunning, phase]);

  // Elapsed timer
  useEffect(() => {
    if (phase !== "running") return;
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [phase]);

  // Track "just completed" agent for flash animation
  useEffect(() => {
    const currentKeys = Object.keys(agentData);
    const newKey = currentKeys.find(k => !prevKeysRef.current.includes(k));
    if (newKey) {
      setJustCompleted(newKey);
      const t = setTimeout(() => setJustCompleted(null), 700);
      prevKeysRef.current = [...currentKeys];
      return () => clearTimeout(t);
    }
    prevKeysRef.current = [...currentKeys];
  }, [agentData]);

  // Don't render when not active
  if (phase === "done") return null;

  const completedCount = AGENTS.filter(a => agentData[a.key]).length;
  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  // Calculate progress line height (percentage of track filled)
  const progressPct = AGENTS.length > 0
    ? (completedCount / AGENTS.length) * 100
    : 0;

  const getStatus = (key: string): "pending" | "active" | "complete" => {
    if (agentData[key]) return "complete";
    if (currentStage === key) return "active";
    return "pending";
  };

  return (
    <div
      className="fixed z-50 pointer-events-auto right-0 top-[52px] bottom-0 w-[300px] max-md:inset-0 max-md:top-0 max-md:w-full max-md:h-full"
      style={{
        animation: phase === "exiting"
          ? "hud-slide-out 0.5s ease-in forwards"
          : "hud-slide-in 0.4s ease-out",
      }}
    >
      <div className="h-full flex flex-col bg-[#06080F]/98 backdrop-blur-xl border-l max-md:border-l-0 border-cyan-500/15 shadow-[-8px_0_30px_rgba(6,182,212,0.08)]">

        {/* ═══ HEADER ═══ */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/5">
          <div className="relative">
            <Radar
              className="h-5 w-5 text-cyan-400"
              style={{ animation: "scan-sweep 3s linear infinite" }}
            />
            <div className="absolute inset-0 rounded-full bg-cyan-400/20 blur-sm" />
          </div>
          <div className="flex-1">
            <div className="text-[9px] text-slate-500 tracking-[0.3em] font-medium">ANALYZING</div>
            <div className="text-sm font-black text-white tracking-widest">{ticker}</div>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-slate-500 tracking-[0.2em]">ELAPSED</div>
            <div className="text-sm font-bold text-cyan-400 tabular-nums font-mono">
              {formatTime(elapsed)}
            </div>
          </div>
        </div>

        {/* ═══ TIMELINE ═══ */}
        <div className="flex-1 overflow-y-auto px-5 py-5 relative">
          {/* Background track line */}
          <div className="absolute left-[33px] top-5 bottom-5 w-[2px] bg-slate-800/80" />
          {/* Progress fill line */}
          <div
            className="absolute left-[33px] top-5 w-[2px] bg-gradient-to-b from-cyan-400 to-cyan-500 transition-all duration-700 ease-out"
            style={{ height: `${Math.min(progressPct, 100) * 0.9}%` }}
          />

          {AGENTS.map((agent, i) => {
            const status = getStatus(agent.key);
            const isFlashing = justCompleted === agent.key;

            return (
              <div key={agent.key} className="flex items-start gap-4 mb-5 relative">
                {/* Node circle */}
                <div className="relative z-10 flex-shrink-0">
                  {/* Sonar ping (active only) */}
                  {status === "active" && (
                    <div
                      className="absolute inset-[-4px] rounded-full border border-cyan-400/50"
                      style={{ animation: "sonar-ping 2s ease-out infinite" }}
                    />
                  )}
                  {/* Main circle */}
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all duration-400 ${
                      status === "complete"
                        ? "bg-cyan-500 border-cyan-400"
                        : status === "active"
                        ? "bg-transparent border-cyan-400"
                        : "bg-slate-900 border-slate-700"
                    }`}
                    style={
                      isFlashing
                        ? { animation: "node-flash 0.7s ease-out" }
                        : status === "active"
                        ? { animation: "glow-pulse 2s ease-in-out infinite" }
                        : {}
                    }
                  >
                    {status === "complete" && <Check className="h-3 w-3 text-black" strokeWidth={3} />}
                    {status === "active" && (
                      <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                    )}
                  </div>
                </div>

                {/* Text */}
                <div className="flex-1 pt-0.5 min-w-0">
                  <div
                    className={`text-[11px] font-bold tracking-[0.15em] transition-colors duration-300 ${
                      status === "complete"
                        ? "text-slate-300"
                        : status === "active"
                        ? "text-cyan-400"
                        : "text-slate-600"
                    }`}
                    style={
                      status === "active"
                        ? {
                            background: "linear-gradient(90deg, #06b6d4 0%, #67e8f9 50%, #06b6d4 100%)",
                            backgroundSize: "200% auto",
                            WebkitBackgroundClip: "text",
                            WebkitTextFillColor: "transparent",
                            animation: "shimmer-text 2s linear infinite",
                          }
                        : {}
                    }
                  >
                    {agent.label}
                  </div>

                  {/* Active: bouncing dots + "Processing..." */}
                  {status === "active" && (
                    <div className="text-[10px] text-cyan-600 mt-1 flex items-center gap-1.5">
                      <div className="flex gap-0.5">
                        <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                        <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                        <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" />
                      </div>
                      <span>Processing...</span>
                    </div>
                  )}

                  {/* Complete: short summary */}
                  {status === "complete" && (
                    <div className="text-[10px] text-slate-500 mt-0.5 truncate animate-in fade-in duration-300">
                      {agent.short} complete
                    </div>
                  )}
                </div>

                {/* Time indicator for completed */}
                {status === "complete" && (
                  <div className="text-[9px] text-slate-600 pt-1 flex-shrink-0 animate-in fade-in duration-300">
                    OK
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* ═══ FOOTER ═══ */}
        <div className="px-5 py-4 border-t border-white/5">
          {/* Segmented progress bar */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] text-slate-500 tracking-[0.2em] font-medium">PROGRESS</span>
            <span className="text-sm font-black text-white tabular-nums">{Math.round(progress)}%</span>
          </div>
          <div className="flex gap-1 mb-4">
            {AGENTS.map((a) => (
              <div
                key={a.key}
                className={`h-1.5 flex-1 rounded-full transition-all duration-500 ${
                  agentData[a.key]
                    ? "bg-cyan-500 shadow-[0_0_6px_rgba(6,182,212,0.5)]"
                    : currentStage === a.key
                    ? "bg-cyan-500/40"
                    : "bg-slate-800"
                }`}
                style={
                  currentStage === a.key
                    ? { animation: "segment-glow 1.5s ease-in-out infinite" }
                    : {}
                }
              />
            ))}
          </div>
          <button
            onClick={onCancel}
            className="w-full py-2 text-[10px] font-bold text-red-400 border border-red-500/20 rounded hover:bg-red-500/10 transition-colors tracking-[0.2em] flex items-center justify-center gap-2"
          >
            <X className="h-3 w-3" />
            CANCEL ANALYSIS
          </button>
        </div>

        {/* Completion: all nodes flash then HUD slides out */}
      </div>
    </div>
  );
}
