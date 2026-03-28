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
import { Activity, LayoutDashboard, Users, BookOpen, List, Settings, X, Menu, LayoutGrid, BarChart3, Radar } from "lucide-react";

const ALL_STAGES = [
  "FUNDAMENTAL_ANALYST",
  "SENTIMENT_ANALYST",
  "NEWS_ANALYST",
  "TECHNICAL_ANALYST",
  "BEAR_RESEARCHER",
  "BULL_RESEARCHER",
  "TRADER_DECISION",
  "RISK_MANAGER",
  "SIGNAL_ENGINE"
];

export default function WarRoomDashboard() {
  const [ticker, setTicker] = useState("NQ1");
  const [timeframe, setTimeframe] = useState("5m");
  const [riskProfile, setRiskProfile] = useState("standard");

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
  const [showFootprint, setShowFootprint] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
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
        body: JSON.stringify({ ticker, timeframe, riskProfile }),
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
    <div className="flex h-screen bg-[#05050A] text-slate-300 font-mono font-[family-name:var(--font-jetbrains-mono)] selection:bg-cyan-900 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-16 bg-[#0A0A15] border-r border-white/5 hidden sm:flex flex-col items-center py-4 gap-6 z-50 flex-shrink-0">
        <Activity className="h-7 w-7 text-[#4A4A6A] mb-2 hover:text-cyan-400 transition-colors" />
        <div className="flex flex-col gap-4 w-full items-center">
          <button
            onClick={() => setActiveView("main")}
            title="Dashboard"
            className={`p-2.5 rounded-xl transition-all ${activeView === "main" ? "bg-cyan-500/10 text-cyan-400" : "text-[#4A4A6A] hover:text-white"}`}
          >
            <LayoutDashboard className="h-5 w-5" />
          </button>
          <button
            onClick={() => setActiveView("watchlist")}
            title="Watchlist"
            className={`p-2.5 rounded-xl transition-all ${activeView === "watchlist" ? "bg-purple-500/10 text-purple-400" : "text-[#4A4A6A] hover:text-white"}`}
          >
            <List className="h-5 w-5" />
          </button>
          <button
            onClick={() => setActiveView("journal")}
            title="Trade Journal"
            className={`p-2.5 rounded-xl transition-all ${activeView === "journal" ? "bg-pink-500/10 text-pink-400" : "text-[#4A4A6A] hover:text-white"}`}
          >
            <BookOpen className="h-5 w-5" />
          </button>
          <button
            onClick={() => { setActiveView("consensus"); if (!consensusData) runConsensus(); }}
            title="Consensus"
            className={`p-2.5 rounded-xl transition-all ${activeView === "consensus" ? "bg-amber-500/10 text-amber-400" : "text-[#4A4A6A] hover:text-white"}`}
          >
            <Users className="h-5 w-5" />
          </button>
          <button
            onClick={() => setActiveView("markets")}
            title="Markets"
            className={`p-2.5 rounded-xl transition-all ${activeView === "markets" ? "bg-emerald-500/10 text-emerald-400" : "text-[#4A4A6A] hover:text-white"}`}
          >
            <BarChart3 className="h-5 w-5" />
          </button>
        </div>
        <div className="mt-auto">
          <Settings className="h-5 w-5 text-[#4A4A6A] hover:text-white cursor-pointer transition-colors" />
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        <div className="absolute inset-0 bg-[url('/dots.svg')] bg-repeat opacity-[0.03] pointer-events-none" />

        {/* Header */}
        <header className="shrink-0 sticky top-0 z-40 border-b border-white/5 bg-[#05050A]/90 backdrop-blur-md px-4 py-2.5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-extrabold text-white tracking-widest uppercase hidden sm:block">WAR ROOM</h1>
              <div
                className={`h-2 w-2 rounded-full flex-shrink-0 ${
                  backendStatus === "ok" ? "bg-cyan-500 animate-pulse" :
                  backendStatus === "checking" ? "bg-amber-500 animate-pulse" :
                  "bg-red-500"
                }`}
                title={backendStatus === "ok" ? "Backend connected" : backendStatus === "checking" ? "Checking..." : "Backend offline"}
              />
              {backendStatus === "error" && (
                <span className="text-[10px] text-red-500 font-bold hidden sm:inline">OFFLINE</span>
              )}
            </div>

            <button
              className="sm:hidden text-[#4A4A6A] hover:text-white p-1"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            <div className={`${isMobileMenuOpen ? "flex" : "hidden"} sm:flex flex-col sm:flex-row gap-2 items-stretch sm:items-center absolute sm:relative top-full left-0 right-0 sm:top-auto bg-[#05050A] sm:bg-transparent p-3 sm:p-0 border-b sm:border-0 border-white/5 z-50`}>
              <Input
                value={ticker}
                onChange={e => setTicker(e.target.value.toUpperCase())}
                placeholder="TICKER"
                className="w-20 bg-black/50 border-white/20 uppercase text-cyan-400 font-bold text-xs h-8"
              />
              <Select value={timeframe} onValueChange={(v) => v && setTimeframe(v)}>
                <SelectTrigger className="w-16 bg-black/50 border-white/20 text-xs h-8">
                  <SelectValue placeholder="TF" />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-white/20 text-white">
                  <SelectItem value="1m">1m</SelectItem>
                  <SelectItem value="5m">5m</SelectItem>
                  <SelectItem value="15m">15m</SelectItem>
                  <SelectItem value="1h">1h</SelectItem>
                </SelectContent>
              </Select>
              <button
                onClick={() => setMultiChart(m => !m)}
                className={`h-8 w-8 flex items-center justify-center rounded border transition-all ${multiChart ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-400" : "border-white/20 bg-black/50 text-slate-500 hover:text-slate-300"}`}
                title="Toggle multi-timeframe view"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
              <Select value={riskProfile} onValueChange={(v) => v && setRiskProfile(v)}>
                <SelectTrigger className="w-24 bg-black/50 border-white/20 text-xs h-8">
                  <SelectValue placeholder="Risk" />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-white/20 text-white">
                  <SelectItem value="conservative">Conservative</SelectItem>
                  <SelectItem value="standard">Standard</SelectItem>
                  <SelectItem value="aggressive">Aggressive</SelectItem>
                </SelectContent>
              </Select>
              <Button
                onClick={runAnalysis}
                disabled={isRunning}
                className={`relative overflow-hidden text-white font-extrabold text-xs h-8 transition-all border ${
                  isRunning
                    ? "bg-cyan-900/30 border-cyan-400/40 shadow-[0_0_20px_rgba(6,182,212,0.5)] cursor-wait"
                    : "bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 shadow-[0_0_15px_rgba(6,182,212,0.4)] hover:shadow-[0_0_25px_rgba(6,182,212,0.6)] border-cyan-400/30"
                }`}
              >
                {isRunning && (
                  <span
                    className="absolute inset-[-2px] rounded-md opacity-80"
                    style={{
                      background: "conic-gradient(from 0deg, transparent 60%, #06b6d4 100%)",
                      animation: "scan-sweep 1.5s linear infinite",
                    }}
                  />
                )}
                {isRunning && <span className="absolute inset-[2px] rounded bg-slate-950/90" />}
                <span className="relative z-10 flex items-center gap-2">
                  {isRunning && <Radar className="h-3 w-3 animate-spin [animation-duration:2s]" />}
                  {isRunning ? "ANALYZING..." : "RUN ANALYSIS"}
                </span>
              </Button>
              <AlertBell onTickerSelect={(t) => { setTicker(t); setActiveView("main"); }} />
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
              {/* Chart title */}
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold text-slate-400 tracking-wide">{ticker}</span>
                <span className="text-[10px] text-slate-600">/</span>
                <span className="text-xs text-slate-500">{timeframe}</span>
              </div>

              <div className="flex items-center justify-between mb-2">
                <ChartOverlayToggles toggles={[
                  { id: "sessions", label: "Sessions", color: "#a78bfa", active: showSessions, onToggle: () => setShowSessions(s => !s) },
                  { id: "bubbles", label: "Big Trades", color: "#22d3ee", active: showBubbles, onToggle: () => setShowBubbles(s => !s) },
                  { id: "delta", label: "Delta", color: "#c026d3", active: showDelta, onToggle: () => setShowDelta(s => !s) },
                  { id: "cvd", label: "CVD", color: "#f59e0b", active: showCVD, onToggle: () => setShowCVD(s => !s) },
                  { id: "vwapBands", label: "VWAP\u00b1", color: "#a78bfa", active: showVwapBands, onToggle: () => setShowVwapBands(s => !s) },
                  { id: "vp", label: "VP", color: "#f59e0b", active: showVP, onToggle: () => setShowVP(s => !s) },
                  { id: "footprint", label: "Footprint", color: "#10b981", active: showFootprint, onToggle: () => setShowFootprint(s => !s) },
                  { id: "heatmap", label: "Heatmap", color: "#ef4444", active: showHeatmap, onToggle: () => setShowHeatmap(s => !s) },
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
                <div className="flex items-center gap-3 py-1">
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
                  <span className="text-[9px] text-slate-600 font-medium tracking-wider">SIGNAL</span>
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
                </div>
              )}

              {signal && <SignalStrip signal={signal} currentPrice={chartData?.candles?.length ? chartData.candles[chartData.candles.length - 1].close : undefined} />}

              {/* Section divider */}
              {Object.keys(agentData).length > 0 && (
                <div className="flex items-center gap-3 py-1">
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
                  <span className="text-[9px] text-slate-600 font-medium tracking-wider">AGENTS</span>
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
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
                className={`px-4 py-3 rounded-lg border backdrop-blur-md shadow-2xl text-xs font-bold animate-in slide-in-from-right duration-300 ${
                  toast.type === "success" ? "bg-green-500/20 border-green-500/40 text-green-400" :
                  toast.type === "error" ? "bg-red-500/20 border-red-500/40 text-red-400" :
                  "bg-cyan-500/20 border-cyan-500/40 text-cyan-400"
                }`}
              >
                {toast.message}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mobile Bottom Tab Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 sm:hidden bg-[#0A0A15]/95 backdrop-blur-md border-t border-white/10 flex items-center justify-around px-2 py-2">
        {[
          { view: "main", icon: LayoutDashboard, color: "cyan" },
          { view: "watchlist", icon: List, color: "purple" },
          { view: "journal", icon: BookOpen, color: "pink" },
          { view: "consensus", icon: Users, color: "amber" },
          { view: "markets", icon: BarChart3, color: "emerald" },
        ].map(({ view, icon: Icon, color }) => (
          <button
            key={view}
            onClick={() => { setActiveView(view as any); if (view === "consensus" && !consensusData) runConsensus(); }}
            className={`p-2.5 rounded-xl transition-all ${
              activeView === view ? `bg-${color}-500/10 text-${color}-400` : "text-[#4A4A6A]"
            }`}
          >
            <Icon className="h-5 w-5" />
          </button>
        ))}
      </nav>
    </div>
  );
}
