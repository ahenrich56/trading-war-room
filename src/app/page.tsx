"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SignalPayload } from "@/components/types";
import { MiniChart } from "@/components/MiniChart";
import { ConsensusPanel } from "@/components/ConsensusPanel";
import { SignalStrip } from "@/components/SignalStrip";
import { AgentAccordion } from "@/components/AgentAccordion";
import { TradeJournal } from "@/components/TradeJournal";
import { WatchlistPage } from "@/components/WatchlistPage";
import { ChartOverlayToggles } from "@/components/ChartOverlayToggles";
import { MultiChartGrid } from "@/components/MultiChartGrid";
import { AlertBell } from "@/components/AlertBell";
import { MarketHeatmap } from "@/components/MarketHeatmap";
import { AnalysisHUD } from "@/components/AnalysisHUD";
import { MLStatsPanel } from "@/components/MLStatsPanel";
import { GlassFilter } from "@/components/ui/liquid-glass";
import { Activity, LayoutDashboard, Users, BookOpen, List, Settings, X, Menu, LayoutGrid, BarChart3, Radar, Crosshair, ChevronLeft, ChevronRight } from "lucide-react";

const ALL_STAGES = [
  "ICT_TRADER",
  "ORDERFLOW_TRADER",
  "SCALPER",
  "MACRO_TRADER",
  "STRUCTURE_TRADER",
  "WHALE_TRACKER",
  "HEAD_TRADER",
  "BULL_ADVOCATE",
  "BEAR_ADVOCATE",
  "HEAD_TRADER_FINAL",
  "RISK_MANAGER",
  "SIGNAL_ENGINE"
];

export default function WarRoomDashboard() {
  const [ticker, setTicker] = useState("NQ1");
  const [timeframe, setTimeframe] = useState("5m");
  const [riskProfile, setRiskProfile] = useState("standard");
  const [selectedModel, setSelectedModel] = useState("qwen-3-235b-a22b-instruct-2507");

  const [isRunning, setIsRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [backendStatus, setBackendStatus] = useState<"ok" | "error" | "checking">("checking");

  const [agentData, setAgentData] = useState<Record<string, any>>({});
  const [signal, setSignal] = useState<SignalPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [chartData, setChartData] = useState<any>(null);
  const [signalHistory, setSignalHistory] = useState<SignalPayload[]>([]);

  // Sidebar navigation
  const [activeView, setActiveView] = useState<"main" | "watchlist" | "journal" | "consensus" | "markets">("main");

  const [watchlistData, setWatchlistData] = useState<any>(null);
  const [isScanning, setIsScanning] = useState(false);

  // Consensus
  const [consensusData, setConsensusData] = useState<any>(null);
  const [isConsensusRunning, setIsConsensusRunning] = useState(false);

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  const [watchlistTickers, setWatchlistTickers] = useState<string[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("warroom_watchlist");
      return saved ? JSON.parse(saved) : ["NQ1", "ES1", "YM1", "RTY1", "GC1", "CL1", "SI1", "ZB1"];
    }
    return ["NQ1", "ES1", "YM1", "RTY1", "GC1", "CL1", "SI1", "ZB1"];
  });
  const [newWatchlistTicker, setNewWatchlistTicker] = useState("");

  // Chart overlay toggles
  const [showSessions, setShowSessions] = useState(false);
  const [showBubbles, setShowBubbles] = useState(false);
  const [showDelta, setShowDelta] = useState(false);
  const [showCVD, setShowCVD] = useState(false);
  const [showVwapBands, setShowVwapBands] = useState(false);
  const [showVP, setShowVP] = useState(false);
  const showFootprint = false;
  const showHeatmap = false;
  const [showLiquidityMap, setShowLiquidityMap] = useState(false);
  const [multiChart, setMultiChart] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const [toasts, setToasts] = useState<{id: number; message: string; type: "success" | "error" | "info"}[]>([]);
  const toastIdRef = useRef(0);

  const addToast = useCallback((message: string, type: "success" | "error" | "info" = "info") => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  // Poll backend health
  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/health");
        if (isMounted) setBackendStatus(res.ok ? "ok" : "error");
      } catch {
        if (isMounted) setBackendStatus("error");
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => { isMounted = false; clearInterval(interval); };
  }, []);

  // Save watchlist to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("warroom_watchlist", JSON.stringify(watchlistTickers));
    }
  }, [watchlistTickers]);

  // Load chart data
  const loadChartData = useCallback(async (t: string, tf: string) => {
    try {
      const res = await fetch("/api/chart-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: t, timeframe: tf }),
      });
      const data = await res.json();
      setChartData(data);
    } catch (e) {
      console.error("Failed to load chart data:", e);
    }
  }, []);

  // Auto-refresh chart data (indicators/order flow) — WS handles real-time candles
  useEffect(() => {
    const timer = setTimeout(() => {
      if (ticker.length >= 1) loadChartData(ticker, timeframe);
    }, 600);
    const intervalId = setInterval(() => {
      if (ticker.length >= 1) loadChartData(ticker, timeframe);
    }, 30000); // 30s — WS streams candle ticks between refreshes
    return () => { clearTimeout(timer); clearInterval(intervalId); };
  }, [ticker, timeframe, loadChartData]);

  // Load signal history
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch("/api/signals?limit=10");
      const data = await res.json();
      setSignalHistory(data.signals || []);
    } catch (e) {
      console.error("Failed to load signal history:", e);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Watchlist scan
  const scanWatchlist = useCallback(async () => {
    setIsScanning(true);
    try {
      const res = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: watchlistTickers, timeframe }),
      });
      const data = await res.json();
      setWatchlistData(data);
      addToast(`Scanned ${watchlistTickers.length} tickers`, "success");
    } catch {
      addToast("Watchlist scan failed", "error");
    } finally {
      setIsScanning(false);
    }
  }, [timeframe, watchlistTickers, addToast]);

  // Multi-model consensus
  const runConsensus = useCallback(async () => {
    setIsConsensusRunning(true);
    setActiveView("consensus");
    try {
      const res = await fetch("/api/consensus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, timeframe }),
      });
      const data = await res.json();
      setConsensusData(data);
      addToast("Consensus analysis complete", "success");
    } catch {
      addToast("Consensus analysis failed", "error");
    } finally {
      setIsConsensusRunning(false);
    }
  }, [ticker, timeframe, addToast]);

  // Cancel analysis
  const cancelAnalysis = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsRunning(false);
      setCurrentStage("CANCELLED");
      addToast("Analysis cancelled", "info");
    }
  }, [addToast]);

  // Main analysis SSE stream
  const runAnalysis = async () => {
    setIsRunning(true);
    setAgentData({});
    setSignal(null);
    setError(null);
    setCurrentStage(ALL_STAGES[0]);
    setProgress(0);
    setActiveView("main");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    loadChartData(ticker, timeframe);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, timeframe, riskProfile, model: selectedModel }),
        signal: controller.signal,
      });

      if (!response.body) throw new Error("No readable stream");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      let done = false;
      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.replace("data: ", "").trim();
              if (!dataStr) continue;

              const match = dataStr.match(/^\[(.*?)\] (.*)$/);
              if (match) {
                const marker = match[1];
                const contentStr = match[2];
                try {
                  const content = JSON.parse(contentStr);

                  if (marker === "SIGNAL_ENGINE") {
                    setSignal(content);
                  } else if (marker === "ERROR") {
                    setError(content.text);
                  } else if (marker === "ICT" || marker === "ORDER_FLOW" || marker === "MTF_ORDER_FLOW") {
                    // Silently consumed — data feeds into signal scoring backend-side
                  } else {
                    setAgentData((prev) => ({ ...prev, [marker]: content.text }));
                  }

                  // Only update currentStage for HUD-visible agents (not ICT/ORDER_FLOW/MTF)
                  if (ALL_STAGES.includes(marker)) {
                    setCurrentStage(marker);
                    const stageIndex = ALL_STAGES.indexOf(marker);
                    setProgress(((stageIndex + 1) / ALL_STAGES.length) * 100);
                  }
                } catch (e) {
                  console.error("Failed to parse JSON for marker", marker, contentStr);
                }
              }
            }
          }
        }
      }
      loadHistory();
      addToast(`Analysis complete for ${ticker}`, "success");
    } catch (err: any) {
      if (err.name === "AbortError") return;
      setError(err.message || "Failed to run analysis");
      addToast(err.message || "Analysis failed", "error");
    } finally {
      setIsRunning(false);
      setProgress(100);
      setCurrentStage("COMPLETE");
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="flex h-screen text-slate-300 font-mono font-[family-name:var(--font-jetbrains-mono)] selection:bg-cyan-900 overflow-hidden" style={{ background: "linear-gradient(135deg, #05050A 0%, #0a0f1a 30%, #080510 60%, #05050A 100%)" }}>
      <GlassFilter />
      {/* Sidebar */}
      <aside
        className={`${sidebarExpanded ? "w-48" : "w-16"} border-r border-white/[0.06] hidden sm:flex flex-col py-4 z-50 flex-shrink-0 transition-all duration-300 ease-in-out`}
        style={{ background: "rgba(8, 8, 18, 0.7)", backdropFilter: "blur(20px)" }}
      >
        {/* Logo / Brand */}
        <div className={`flex items-center ${sidebarExpanded ? "px-4 gap-3" : "justify-center"} mb-6`}>
          <div className="relative">
            <Crosshair className="h-7 w-7 text-cyan-500" />
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          {sidebarExpanded && (
            <div className="overflow-hidden">
              <div className="text-xs font-extrabold text-white tracking-[0.2em] whitespace-nowrap">WAR ROOM</div>
              <div className="text-[9px] text-slate-600 tracking-wider">TRADING SYSTEM</div>
            </div>
          )}
        </div>

        {/* Nav Items */}
        <nav className={`flex flex-col gap-1 flex-1 ${sidebarExpanded ? "px-3" : "px-2"}`}>
          {([
            { view: "main" as const, icon: LayoutDashboard, label: "Dashboard", activeBg: "bg-cyan-500/10", activeText: "text-cyan-400", activeBar: "bg-cyan-400", onClick: () => setActiveView("main") },
            { view: "watchlist" as const, icon: List, label: "Watchlist", activeBg: "bg-purple-500/10", activeText: "text-purple-400", activeBar: "bg-purple-400", onClick: () => setActiveView("watchlist") },
            { view: "journal" as const, icon: BookOpen, label: "Journal", activeBg: "bg-pink-500/10", activeText: "text-pink-400", activeBar: "bg-pink-400", onClick: () => setActiveView("journal") },
            { view: "consensus" as const, icon: Users, label: "Consensus", activeBg: "bg-amber-500/10", activeText: "text-amber-400", activeBar: "bg-amber-400", onClick: () => { setActiveView("consensus"); if (!consensusData) runConsensus(); } },
            { view: "markets" as const, icon: BarChart3, label: "Markets", activeBg: "bg-emerald-500/10", activeText: "text-emerald-400", activeBar: "bg-emerald-400", onClick: () => setActiveView("markets") },
          ]).map(({ view, icon: Icon, label, activeBg, activeText, activeBar, onClick }) => {
            const isActive = activeView === view;
            return (
              <button
                key={view}
                onClick={onClick}
                title={!sidebarExpanded ? label : undefined}
                className={`relative flex items-center gap-3 rounded-xl transition-all duration-200 group ${
                  sidebarExpanded ? "px-3 py-2.5" : "p-2.5 justify-center"
                } ${
                  isActive
                    ? `${activeBg} ${activeText} shadow-[inset_0_0_20px_rgba(0,0,0,0.3)]`
                    : "text-slate-500 hover:text-slate-200 hover:bg-white/[0.04]"
                }`}
              >
                {isActive && (
                  <div className={`absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full ${activeBar}`} />
                )}
                <Icon className={`h-[18px] w-[18px] flex-shrink-0 transition-transform duration-200 ${isActive ? "" : "group-hover:scale-110"}`} />
                {sidebarExpanded && (
                  <span className={`text-xs font-semibold tracking-wide whitespace-nowrap ${isActive ? "" : "text-slate-400 group-hover:text-slate-200"}`}>
                    {label}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom actions */}
        <div className={`flex flex-col gap-2 ${sidebarExpanded ? "px-3" : "px-2"} mt-4`}>
          <div className="h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent mb-1" />
          <button
            title="Settings"
            className={`flex items-center gap-3 rounded-xl transition-all text-slate-500 hover:text-slate-200 hover:bg-white/[0.04] ${sidebarExpanded ? "px-3 py-2.5" : "p-2.5 justify-center"}`}
          >
            <Settings className="h-[18px] w-[18px]" />
            {sidebarExpanded && <span className="text-xs font-semibold tracking-wide text-slate-400">Settings</span>}
          </button>
          <button
            onClick={() => setSidebarExpanded(e => !e)}
            className={`flex items-center gap-3 rounded-xl transition-all text-slate-600 hover:text-slate-300 hover:bg-white/[0.04] ${sidebarExpanded ? "px-3 py-2" : "p-2.5 justify-center"}`}
            title={sidebarExpanded ? "Collapse" : "Expand"}
          >
            {sidebarExpanded ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            {sidebarExpanded && <span className="text-[10px] text-slate-500">Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        <div className="absolute inset-0 bg-[url('/dots.svg')] bg-repeat opacity-[0.03] pointer-events-none" />

        {/* Header */}
        <header className="shrink-0 sticky top-0 z-40 border-b border-white/[0.06] px-4 py-2" style={{ background: "rgba(5, 5, 10, 0.75)", backdropFilter: "blur(20px)" }}>
          <div className="flex items-center justify-between gap-3">
            {/* Left: Status */}
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <div
                    className={`h-2 w-2 rounded-full flex-shrink-0 ${
                      backendStatus === "ok" ? "bg-cyan-500" :
                      backendStatus === "checking" ? "bg-amber-500" :
                      "bg-red-500"
                    }`}
                  />
                  {backendStatus === "ok" && (
                    <div className="absolute inset-0 h-2 w-2 rounded-full bg-cyan-500 animate-ping opacity-30" />
                  )}
                </div>
                <span className={`text-[10px] font-semibold tracking-wider hidden sm:inline ${
                  backendStatus === "ok" ? "text-cyan-500/70" :
                  backendStatus === "checking" ? "text-amber-500/70" :
                  "text-red-500"
                }`}>
                  {backendStatus === "ok" ? "LIVE" : backendStatus === "checking" ? "..." : "OFFLINE"}
                </span>
              </div>
            </div>

            {/* Mobile menu toggle */}
            <button
              className="sm:hidden text-slate-500 hover:text-white p-1.5 rounded-lg hover:bg-white/5"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            {/* Controls */}
            <div className={`${isMobileMenuOpen ? "flex" : "hidden"} sm:flex flex-col sm:flex-row gap-2 items-stretch sm:items-center absolute sm:relative top-full left-0 right-0 sm:top-auto p-3 sm:p-0 z-50 ${isMobileMenuOpen ? "bg-[#08081280] backdrop-blur-xl border-b border-white/[0.06]" : ""}`}>
              {/* Instrument group */}
              <div className="flex items-center gap-1.5 sm:border-r sm:border-white/[0.06] sm:pr-3">
                <Input
                  value={ticker}
                  onChange={e => setTicker(e.target.value.toUpperCase())}
                  placeholder="TICKER"
                  className="w-20 bg-white/[0.04] border-white/[0.08] uppercase text-cyan-400 font-bold text-xs h-8 focus:border-cyan-500/40 focus:ring-cyan-500/20 placeholder:text-slate-600"
                />
                <Select value={timeframe} onValueChange={(v) => v && setTimeframe(v)}>
                  <SelectTrigger className="w-16 bg-white/[0.04] border-white/[0.08] text-xs h-8 text-slate-300">
                    <SelectValue placeholder="TF" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0c0c1a] border-white/[0.1] text-white">
                    <SelectItem value="1m">1m</SelectItem>
                    <SelectItem value="5m">5m</SelectItem>
                    <SelectItem value="15m">15m</SelectItem>
                    <SelectItem value="1h">1h</SelectItem>
                  </SelectContent>
                </Select>
                <button
                  onClick={() => setMultiChart(m => !m)}
                  className={`h-8 w-8 flex items-center justify-center rounded-lg border transition-all ${multiChart ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-400" : "border-white/[0.08] bg-white/[0.04] text-slate-500 hover:text-slate-300 hover:border-white/[0.15]"}`}
                  title="Toggle multi-timeframe view"
                >
                  <LayoutGrid className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Config group */}
              <div className="flex items-center gap-1.5 sm:border-r sm:border-white/[0.06] sm:pr-3">
                <Select value={riskProfile} onValueChange={(v) => v && setRiskProfile(v)}>
                  <SelectTrigger className="w-24 bg-white/[0.04] border-white/[0.08] text-xs h-8 text-slate-300">
                    <SelectValue placeholder="Risk" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0c0c1a] border-white/[0.1] text-white">
                    <SelectItem value="conservative">Conservative</SelectItem>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="aggressive">Aggressive</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={selectedModel} onValueChange={(v) => v && setSelectedModel(v)}>
                  <SelectTrigger className="w-36 bg-white/[0.04] border-white/[0.08] text-xs h-8 text-slate-300">
                    <SelectValue placeholder="Model" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0c0c1a] border-white/[0.1] text-white">
                    <SelectItem value="qwen-3-235b-a22b-instruct-2507">QWen 3 235B</SelectItem>
                    <SelectItem value="llama-3.3-70b-versatile">Llama 3.3 70B</SelectItem>
                    <SelectItem value="openai/gpt-oss-120b">GPT-OSS 120B</SelectItem>
                    <SelectItem value="openclaude">OpenClaude (Agent)</SelectItem>
                    <SelectItem value="nvidia/nemotron-3-super-120b-a12b:free">Nemotron 120B</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Action group */}
              <div className="flex items-center gap-2">
                <Button
                  onClick={runAnalysis}
                  disabled={isRunning}
                  className={`relative overflow-hidden text-white font-extrabold text-xs h-8 px-5 transition-all border rounded-lg ${
                    isRunning
                      ? "bg-cyan-900/30 border-cyan-400/40 shadow-[0_0_20px_rgba(6,182,212,0.4)] cursor-wait"
                      : "bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 shadow-[0_0_12px_rgba(6,182,212,0.3)] hover:shadow-[0_0_24px_rgba(6,182,212,0.5)] border-cyan-500/30"
                  }`}
                >
                  {isRunning && (
                    <span
                      className="absolute inset-[-2px] rounded-lg opacity-75"
                      style={{
                        background: "conic-gradient(from 0deg, transparent 60%, #06b6d4 100%)",
                        animation: "scan-sweep 1.5s linear infinite",
                      }}
                    />
                  )}
                  {isRunning && <span className="absolute inset-[2px] rounded-md bg-[#05050A]/90" />}
                  <span className="relative z-10 flex items-center gap-2">
                    {isRunning && <Radar className="h-3.5 w-3.5 animate-spin [animation-duration:2s]" />}
                    {isRunning ? "ANALYZING..." : "RUN ANALYSIS"}
                  </span>
                </Button>
                <AlertBell onTickerSelect={(t) => { setTicker(t); setActiveView("main"); }} />
              </div>
            </div>
          </div>
        </header>

        {/* Analysis HUD — slides in from right during analysis */}
        <AnalysisHUD
          isRunning={isRunning}
          currentStage={currentStage}
          agentData={agentData}
          ticker={ticker}
          progress={progress}
          onCancel={cancelAnalysis}
        />

        {error && (
          <div className="shrink-0 mx-4 mt-2 p-3 border border-red-500/50 bg-red-500/10 text-red-400 rounded text-xs">
            [ERROR]: {error}
          </div>
        )}

        {/* Main scrollable content */}
        <main className="flex-1 overflow-y-auto p-4 pb-20 sm:pb-4 space-y-4 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">

          {/* ═══ MAIN VIEW: Chart + Signal ═══ */}
          {activeView === "main" && (
            <>
              {/* Chart header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-bold text-white tracking-wide">{ticker}</span>
                    <span className="text-slate-600">/</span>
                    <span className="text-xs text-slate-500 font-medium">{timeframe}</span>
                  </div>
                  {isRunning && (
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                      <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                      <span className="text-[10px] text-cyan-400 font-semibold">LIVE</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between mb-2">
                <ChartOverlayToggles toggles={[
                  { id: "sessions", label: "Sessions", color: "#a78bfa", active: showSessions, onToggle: () => setShowSessions(s => !s) },
                  { id: "bubbles", label: "Big Trades", color: "#22d3ee", active: showBubbles, onToggle: () => setShowBubbles(s => !s) },
                  { id: "delta", label: "Delta", color: "#c026d3", active: showDelta, onToggle: () => setShowDelta(s => !s) },
                  { id: "cvd", label: "CVD", color: "#f59e0b", active: showCVD, onToggle: () => setShowCVD(s => !s) },
                  { id: "vwapBands", label: "VWAP\u00b1", color: "#a78bfa", active: showVwapBands, onToggle: () => setShowVwapBands(s => !s) },
                  { id: "vp", label: "VP", color: "#f59e0b", active: showVP, onToggle: () => setShowVP(s => !s) },
                  { id: "liquidityMap", label: "Liquidity", color: "#f97316", active: showLiquidityMap, onToggle: () => setShowLiquidityMap(s => !s) },
                ]} />
              </div>
              {multiChart ? (
                <MultiChartGrid
                  ticker={ticker} signal={signal}
                  showSessions={showSessions} showBubbles={showBubbles}
                  showDelta={showDelta} showCVD={showCVD}
                  showVwapBands={showVwapBands} showVP={showVP}
                  showFootprint={showFootprint} showHeatmap={showHeatmap} showLiquidityMap={showLiquidityMap}
                />
              ) : (
                <MiniChart
                  chartData={chartData} signal={signal} ticker={ticker}
                  showSessions={showSessions} showBubbles={showBubbles}
                  showDelta={showDelta} showCVD={showCVD}
                  showVwapBands={showVwapBands} showVP={showVP}
                  showFootprint={showFootprint} showHeatmap={showHeatmap} showLiquidityMap={showLiquidityMap}
                />
              )}

              {/* Section divider */}
              {signal && (
                <div className="flex items-center gap-3 py-2">
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
                  <span className="text-[9px] text-slate-600 font-semibold tracking-[0.2em]">SIGNAL</span>
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
                </div>
              )}

              {signal && <SignalStrip signal={signal} currentPrice={chartData?.candles?.length ? chartData.candles[chartData.candles.length - 1].close : undefined} />}

              {/* ML Stats */}
              <MLStatsPanel />

              {/* Section divider */}
              {Object.keys(agentData).length > 0 && (
                <div className="flex items-center gap-3 py-2">
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
                  <span className="text-[9px] text-slate-600 font-semibold tracking-[0.2em]">AGENTS</span>
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
                </div>
              )}
            </>
          )}

          {/* ═══ WATCHLIST ═══ */}
          {activeView === "watchlist" && (
            <WatchlistPage
              watchlistTickers={watchlistTickers}
              setWatchlistTickers={setWatchlistTickers}
              watchlistData={watchlistData}
              isScanning={isScanning}
              onScan={scanWatchlist}
              onSelect={(t: string) => { setTicker(t); setActiveView("main"); loadChartData(t, timeframe); }}
              newTicker={newWatchlistTicker}
              setNewTicker={setNewWatchlistTicker}
            />
          )}

          {/* ═══ TRADE JOURNAL ═══ */}
          {activeView === "journal" && (
            <TradeJournal signal={signal} signalHistory={signalHistory} />
          )}

          {/* ═══ CONSENSUS ═══ */}
          {activeView === "consensus" && (
            <ConsensusPanel data={consensusData} isRunning={isConsensusRunning} ticker={ticker} />
          )}

          {/* ═══ MARKETS HEATMAP ═══ */}
          {activeView === "markets" && (
            <MarketHeatmap onTickerSelect={(t) => { setTicker(t); setActiveView("main"); }} />
          )}

          {/* ═══ AGENTS — main view only ═══ */}
          {activeView === "main" && (
            <AgentAccordion agentData={agentData} currentStage={isRunning ? currentStage : null} />
          )}
        </main>

        {/* Toast Notifications */}
        {toasts.length > 0 && (
          <div className="fixed bottom-4 right-4 z-[100] space-y-2 max-w-sm">
            {toasts.map(toast => (
              <div
                key={toast.id}
                className={`relative overflow-hidden px-4 py-3 rounded-xl border shadow-2xl text-xs font-semibold animate-in slide-in-from-right duration-300 ${
                  toast.type === "success" ? "bg-green-500/10 border-green-500/20 text-green-400" :
                  toast.type === "error" ? "bg-red-500/10 border-red-500/20 text-red-400" :
                  "bg-cyan-500/10 border-cyan-500/20 text-cyan-400"
                }`}
                style={{ backdropFilter: "blur(16px)" }}
              >
                <div className={`absolute inset-x-0 top-0 h-px ${
                  toast.type === "success" ? "bg-gradient-to-r from-transparent via-green-500/40 to-transparent" :
                  toast.type === "error" ? "bg-gradient-to-r from-transparent via-red-500/40 to-transparent" :
                  "bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent"
                }`} />
                {toast.message}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mobile Bottom Tab Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 sm:hidden border-t border-white/[0.06] flex items-center justify-around px-2 py-1.5 safe-area-inset-bottom" style={{ background: "rgba(8, 8, 18, 0.85)", backdropFilter: "blur(24px)" }}>
        {([
          { view: "main" as const, icon: LayoutDashboard, label: "Dashboard", activeText: "text-cyan-400" },
          { view: "watchlist" as const, icon: List, label: "Watch", activeText: "text-purple-400" },
          { view: "journal" as const, icon: BookOpen, label: "Journal", activeText: "text-pink-400" },
          { view: "consensus" as const, icon: Users, label: "Vote", activeText: "text-amber-400" },
          { view: "markets" as const, icon: BarChart3, label: "Markets", activeText: "text-emerald-400" },
        ]).map(({ view, icon: Icon, label, activeText }) => (
          <button
            key={view}
            onClick={() => { setActiveView(view); if (view === "consensus" && !consensusData) runConsensus(); }}
            className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all ${
              activeView === view ? activeText : "text-slate-600"
            }`}
          >
            <Icon className="h-5 w-5" />
            <span className="text-[9px] font-medium">{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
