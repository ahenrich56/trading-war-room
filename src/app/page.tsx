"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SignalPayload } from "@/components/types";
import { MiniChart } from "@/components/MiniChart";
import { TradingViewChart } from "@/components/TradingViewChart";
import { AgentCard } from "@/components/AgentCard";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { ConsensusPanel } from "@/components/ConsensusPanel";
import { ICTPanel } from "@/components/ICTPanel";
import { BacktestPanel } from "@/components/BacktestPanel";
import { TermTooltip } from "@/components/TermTooltip";
import { OutcomesPanel } from "@/components/OutcomesPanel";
import { WhaleAlertsPanel } from "@/components/WhaleAlertsPanel";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Activity, LayoutDashboard, Users, Bird, LineChart, Target, Settings, X, Menu } from "lucide-react";



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
  const [ticker, setTicker] = useState("NVDA");
  const [timeframe, setTimeframe] = useState("5m");
  const [riskProfile, setRiskProfile] = useState("standard");
  
  const [isRunning, setIsRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [backendStatus, setBackendStatus] = useState<"ok" | "error" | "checking">("checking");
  const [demoMode, setDemoMode] = useState(false);

  const [agentData, setAgentData] = useState<Record<string, any>>({});
  const [signal, setSignal] = useState<SignalPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Chart + History state
  const [chartData, setChartData] = useState<any>(null);
  const [signalHistory, setSignalHistory] = useState<SignalPayload[]>([]);
  const [activeTab, setActiveTab] = useState<"chart" | "history" | "watchlist" | "consensus" | "ict" | "backtest" | "outcomes">("chart");

  // Watchlist + Consensus state
  const [watchlistData, setWatchlistData] = useState<any>(null);
  const [consensusData, setConsensusData] = useState<any>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isConsensusRunning, setIsConsensusRunning] = useState(false);

  // ICT + Backtest state
  const [ictData, setIctData] = useState<any>(null);
  const [backtestData, setBacktestData] = useState<any>(null);
  const [isIctRunning, setIsIctRunning] = useState(false);
  const [isBacktesting, setIsBacktesting] = useState(false);

  // Mobile menu state
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Poll backend health
  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/health");
        if (isMounted) {
          setBackendStatus(res.ok ? "ok" : "error");
        }
      } catch (e) {
        if (isMounted) setBackendStatus("error");
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Outcome tracking state
  const [outcomesData, setOutcomesData] = useState<any>(null);

  // Toast notifications
  const [toasts, setToasts] = useState<{id: number; message: string; type: "success" | "error" | "info"}[]>([]);
  const toastIdRef = useRef(0);

  // Customizable watchlist
  const [watchlistTickers, setWatchlistTickers] = useState<string[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("warroom_watchlist");
      return saved ? JSON.parse(saved) : ["NQ1", "ES1", "AAPL", "NVDA", "TSLA", "BTCUSD", "GOLD", "AMZN"];
    }
    return ["NQ1", "ES1", "AAPL", "NVDA", "TSLA", "BTCUSD", "GOLD", "AMZN"];
  });
  const [newWatchlistTicker, setNewWatchlistTicker] = useState("");

  // Abort controller for cancellation
  const abortControllerRef = useRef<AbortController | null>(null);

  const addToast = useCallback((message: string, type: "success" | "error" | "info" = "info") => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
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

  // Auto-refresh chart when ticker changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (ticker.length >= 1) loadChartData(ticker, timeframe);
    }, 600);
    return () => clearTimeout(timer);
  }, [ticker, timeframe, loadChartData]);

  // Load outcomes data
  const loadOutcomes = useCallback(async () => {
    try {
      const res = await fetch("/api/outcomes");
      const data = await res.json();
      setOutcomesData(data);
    } catch (e) {
      console.error("Failed to load outcomes:", e);
    }
  }, []);

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

  // Watchlist scan (uses customizable tickers)
  const scanWatchlist = useCallback(async () => {
    setIsScanning(true);
    setActiveTab("watchlist");
    try {
      const res = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: watchlistTickers, timeframe }),
      });
      const data = await res.json();
      setWatchlistData(data);
      addToast(`Scanned ${watchlistTickers.length} tickers`, "success");
    } catch (e) {
      addToast("Watchlist scan failed", "error");
    } finally {
      setIsScanning(false);
    }
  }, [timeframe, watchlistTickers, addToast]);

  // ═══ DEMO MODE MOCK PIPELINE ═══
  const runDemoPipeline = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    setAgentData({});
    setSignal(null);
    setActiveTab("chart");
    
    try {
      // Fake chart data
      const mockChartUrl = "https://raw.githubusercontent.com/tradingview/lightweight-charts/master/plugin-examples/data.json";
      const res = await fetch(mockChartUrl);
      const rawData = await res.json();
      // Adjust timestamps and format slightly for our display
      const cData = {
        ohlcv: rawData.slice(-100).map((d: any) => ({
          time: new Date(d.time).getTime() / 1000,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
          volume: Math.random() * 1000 + 500
        }))
      };
      setChartData(cData);
      
      const stages = [...ALL_STAGES];
      setProgress(0);
      
      let mockAgents = {} as Record<string, string>;
      for (let i = 0; i < stages.length; i++) {
        const stage = stages[i];
        setCurrentStage(stage);
        await new Promise(r => setTimeout(r, 600)); // Sim delay
        
        mockAgents[stage] = `[DEMO MODE] The ${stage} indicates favorable conditions for a long entry in the current market regime based on simulated metrics.`;
        setAgentData({ ...mockAgents });
        setProgress(Math.round(((i + 1) / stages.length) * 100));
      }
      
      const lastClose = cData.ohlcv[cData.ohlcv.length - 1].close;
      setSignal({
        ticker,
        timeframe,
        signal: "LONG",
        entry_zone: { min: lastClose - 2, max: lastClose + 1 },
        stop_loss: lastClose - 5,
        take_profit: [{ level: 1, price: lastClose + 10 }],
        confidence: 85,
        risk_reward: 2.0,
        position_size_pct: 2,
        reasons: ["Strong demo momentum", "Simulated breakout"],
        tv_alert: "DEMO_ALERT",
        timestamp_utc: new Date().toISOString()
      });
      
      addToast("Demo analysis complete", "success");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsRunning(false);
      setProgress(100);
      setCurrentStage("COMPLETE");
    }
  }, [ticker, timeframe, addToast]);

  // Multi-model consensus (runs independently due to multiple LLM latencies)
  const runConsensus = useCallback(async () => {
    setIsConsensusRunning(true);
    setActiveTab("consensus");
    try {
      const res = await fetch("/api/consensus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, timeframe }),
      });
      const data = await res.json();
      setConsensusData(data);
      addToast("Consensus analysis complete", "success");
    } catch (e) {
      addToast("Consensus analysis failed", "error");
    } finally {
      setIsConsensusRunning(false);
    }
  }, [ticker, timeframe, addToast]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Report outcome (WIN/LOSS)
  const reportOutcome = useCallback(async (sig: SignalPayload, result: "WIN" | "LOSS", pnl: number) => {
    try {
      await fetch("/api/outcomes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: sig.ticker,
          signal: sig.signal,
          entry: sig.entry_zone?.min || 0,
          result,
          pnl_pct: pnl,
        }),
      });
      addToast(`Outcome reported: ${result}`, "success");
      loadOutcomes();
    } catch (e) {
      addToast("Failed to report outcome", "error");
    }
  }, [addToast, loadOutcomes]);

  // Cancel running analysis
  const cancelAnalysis = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsRunning(false);
      setCurrentStage("CANCELLED");
      addToast("Analysis cancelled", "info");
    }
  }, [addToast]);

  const runAnalysis = async () => {
    setIsRunning(true);
    setAgentData({});
    setSignal(null);
    setError(null);
    setCurrentStage(ALL_STAGES[0]);
    setProgress(0);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Also fetch chart data in parallel
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
                  } else if (marker === "BACKTEST") {
                    setBacktestData(content);
                  } else if (marker === "ICT") {
                    setIctData(content);
                  } else if (marker === "WHALE_ALERTS") {
                    // Whale alerts stream early
                  } else if (marker === "ERROR") {
                    setError(content.text);
                  } else {
                    setAgentData((prev) => ({ ...prev, [marker]: content.text }));
                  }
                  
                  setCurrentStage(marker);
                  const stageIndex = ALL_STAGES.indexOf(marker);
                  if (stageIndex !== -1) {
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
      // Reload history after analysis
      loadHistory();
      addToast(`Analysis complete for ${ticker}`, "success");
    } catch (err: any) {
      if (err.name === "AbortError") return; // User cancelled
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
      <aside className="w-20 bg-[#0A0A15] border-r border-white/5 flex flex-col items-center py-6 gap-8 z-50 flex-shrink-0 relative">
        <Activity className="h-8 w-8 text-[#4A4A6A] mb-4 hover:text-cyan-400 transition-colors" />
        <div className="flex flex-col gap-6 w-full items-center">
          <button onClick={() => setActiveTab("chart")} className={`p-3 rounded-xl transition-all ${activeTab === "chart" ? "bg-cyan-500/10 text-cyan-400" : "text-[#4A4A6A] hover:text-white"}`}>
            <LayoutDashboard className="h-6 w-6" />
          </button>
          <button onClick={() => { setActiveTab("consensus"); if (!consensusData) runConsensus(); }} className={`p-3 rounded-xl transition-all ${activeTab === "consensus" ? "bg-amber-500/10 text-amber-400" : "text-[#4A4A6A] hover:text-white"}`}>
            <Users className="h-6 w-6" />
          </button>
          <button onClick={() => { setActiveTab("ict"); }} className={`p-3 rounded-xl transition-all ${activeTab === "ict" ? "bg-emerald-500/10 text-emerald-400" : "text-[#4A4A6A] hover:text-white"}`}>
            <Bird className="h-6 w-6" />
          </button>
          <button onClick={() => { setActiveTab("backtest"); }} className={`p-3 rounded-xl transition-all ${activeTab === "backtest" ? "bg-orange-500/10 text-orange-400" : "text-[#4A4A6A] hover:text-white"}`}>
            <LineChart className="h-6 w-6" />
          </button>
          <button onClick={() => { setActiveTab("outcomes"); }} className={`p-3 rounded-xl transition-all ${activeTab === "outcomes" ? "bg-pink-500/10 text-pink-400" : "text-[#4A4A6A] hover:text-white"}`}>
            <Target className="h-6 w-6" />
          </button>
        </div>
        <div className="mt-auto">
          <Settings className="h-6 w-6 text-[#4A4A6A] hover:text-white cursor-pointer transition-colors" />
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        <div className="absolute inset-0 bg-[url('/dots.svg')] bg-repeat opacity-[0.03] pointer-events-none" />

        {/* Header */}
        <header className="shrink-0 sticky top-0 z-50 border-b border-white/5 bg-[#05050A]/90 backdrop-blur-md px-6 py-4">
          <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-extrabold text-white tracking-widest uppercase flex items-center gap-2">
                  {activeTab === "chart" ? "AI TRADING WAR ROOM" :
                   activeTab === "backtest" ? "BACKTEST STUDIO" :
                   activeTab === "ict" ? "SMART MONEY CONCEPTS" :
                   activeTab === "consensus" ? "CONSENSUS ENGINE" :
                   "OUTCOMES & PERFORMANCE"}
                   {backendStatus === "error" && (
                    <span className="text-xs text-red-500 font-normal uppercase tracking-normal hidden sm:inline">(Offline)</span>
                  )}
                </h1>
                <div 
                  className={`h-2 w-2 rounded-full ${
                    backendStatus === "ok" ? "bg-cyan-500 animate-pulse" : 
                    backendStatus === "checking" ? "bg-amber-500 animate-pulse" : 
                    "bg-red-500"
                  }`} 
                  title={backendStatus === "ok" ? "Backend connected" : backendStatus === "checking" ? "Checking connection..." : "Backend offline"}
                />
              </div>
              <span className="text-sm text-[#8A8AAA]">
                 {activeTab === "chart" ? "Real-Time Multi-Agent Analysis" :
                  activeTab === "backtest" ? "Historical Strategy Optimization & Win-Rates" :
                  activeTab === "ict" ? "Real-Time Liquidity, FVG & Order Block Detection" :
                  "Institutional Grade Market Tracking"}
              </span>
            </div>

            <button 
              className="xl:hidden absolute top-4 right-4 text-[#4A4A6A] hover:text-white p-2"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          
            <div className={`${isMobileMenuOpen ? "flex" : "hidden"} xl:flex flex-col sm:flex-row flex-wrap gap-3 items-stretch sm:items-center mt-3 xl:mt-0`}>
              <div className="flex items-center justify-between sm:justify-start space-x-2 bg-slate-900 border border-white/10 px-3 py-1.5 rounded-md">
                <Switch id="demo-mode" checked={demoMode} onCheckedChange={setDemoMode} />
                <Label htmlFor="demo-mode" className="text-xs text-slate-300 font-bold cursor-pointer hover:text-cyan-400 transition-colors">
                  <TermTooltip term="Demo Mode" description="Uses simulated offline data for testing UI without backend API keys.">
                    DEMO DATA
                  </TermTooltip>
                </Label>
              </div>
              <Input 
                value={ticker} 
                onChange={e => setTicker(e.target.value.toUpperCase())}
                placeholder="TICKER" 
                className="w-20 sm:w-24 bg-black/50 border-white/20 uppercase text-cyan-400 font-bold text-xs sm:text-sm"
              />
              <Select value={timeframe} onValueChange={(v) => v && setTimeframe(v)}>
                <SelectTrigger className="w-20 sm:w-24 bg-black/50 border-white/20 text-xs sm:text-sm">
                  <SelectValue placeholder="TF" />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-white/20 text-white">
                  <SelectItem value="1m">1m</SelectItem>
                  <SelectItem value="5m">5m</SelectItem>
                  <SelectItem value="15m">15m</SelectItem>
                  <SelectItem value="1h">1h</SelectItem>
                </SelectContent>
              </Select>
              <Select value={riskProfile} onValueChange={(v) => v && setRiskProfile(v)}>
                <SelectTrigger className="w-28 sm:w-32 bg-black/50 border-white/20 text-xs sm:text-sm">
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
                className="bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-extrabold text-xs sm:text-sm shadow-[0_0_15px_rgba(6,182,212,0.4)] hover:shadow-[0_0_25px_rgba(6,182,212,0.6)] hover:scale-105 transition-all duration-300 border border-cyan-400/30"
              >
                {isRunning ? "ANALYZING..." : "RUN ANALYSIS"}
              </Button>
              {isRunning && (
                <Button 
                  onClick={cancelAnalysis}
                  variant="outline"
                  className="bg-black/50 border-red-500/50 text-red-500 hover:bg-red-500/20 hover:text-red-400 font-bold text-xs shadow-[0_0_10px_rgba(239,68,68,0.2)] transition-all duration-300 flex items-center gap-1"
                >
                  <X className="h-3 w-3" /> CANCEL
                </Button>
              )}
            </div>
          </div>
        </header>

        {/* Progress Bar */}
        {isRunning && (
          <div className="shrink-0 px-6 py-2 bg-black/40 border-b border-white/5 flex items-center gap-4">
            <span className="text-xs text-cyan-500 w-48 truncate flex-shrink-0">
              {currentStage ? `[${currentStage}]` : "INITIALIZING..."}
            </span>
            <Progress value={progress} className="h-1 bg-white/10 [&>div]:bg-cyan-500 flex-1" />
          </div>
        )}

        {error && (
          <div className="shrink-0 m-6 p-4 border border-red-500/50 bg-red-500/10 text-red-400 rounded-md">
            [SYSTEM ERROR]: {error}
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-6 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        {/* ═══ CHART + SIGNAL HISTORY TABS ═══ */}
        <div className="border border-white/10 rounded-lg bg-black/30 backdrop-blur-sm overflow-hidden">
          <div className="flex overflow-x-auto scrollbar-hide border-b border-white/10">
            <button
              onClick={() => setActiveTab("chart")}
              className={`px-6 py-3 text-xs font-bold tracking-widest transition-all ${
                activeTab === "chart"
                  ? "text-cyan-400 border-b-2 border-cyan-500 bg-cyan-500/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              📊 LIVE CHART
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`px-6 py-3 text-xs font-bold tracking-widest transition-all ${
                activeTab === "history"
                  ? "text-cyan-400 border-b-2 border-cyan-500 bg-cyan-500/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              📜 HISTORY {signalHistory.length > 0 && <span className="ml-2 px-1.5 py-0.5 bg-cyan-500/20 rounded text-[10px]">{signalHistory.length}</span>}
            </button>
            <button
              onClick={() => { setActiveTab("watchlist"); if (!watchlistData) scanWatchlist(); }}
              className={`px-6 py-3 text-xs font-bold tracking-widest transition-all ${
                activeTab === "watchlist"
                  ? "text-purple-400 border-b-2 border-purple-500 bg-purple-500/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              📡 WATCHLIST
            </button>
            <button
              onClick={() => setActiveTab("consensus")}
              className={`px-6 py-3 text-xs font-bold tracking-widest transition-all ${
                activeTab === "consensus"
                  ? "text-amber-400 border-b-2 border-amber-500 bg-amber-500/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              ðŸ—³ï¸ CONSENSUS
            </button>
            <button
              onClick={() => { setActiveTab("ict"); }}
              className={`px-6 py-3 text-xs font-bold tracking-widest transition-all ${
                activeTab === "ict"
                  ? "text-emerald-400 border-b-2 border-emerald-500 bg-emerald-500/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              ðŸ¦ ICT
            </button>
            <button
              onClick={() => { setActiveTab("backtest"); }}
              className={`px-6 py-3 text-xs font-bold tracking-widest transition-all ${
                activeTab === "backtest"
                  ? "text-orange-400 border-b-2 border-orange-500 bg-orange-500/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              ðŸ“ˆ BACKTEST
            </button>
            <button
              onClick={() => { setActiveTab("outcomes"); if (!outcomesData) loadOutcomes(); }}
              className={`px-6 py-3 text-xs font-bold tracking-widest transition-all whitespace-nowrap ${
                activeTab === "outcomes"
                  ? "text-pink-400 border-b-2 border-pink-500 bg-pink-500/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              ðŸŽ¯ PERFORMANCE
            </button>
          </div>

          {activeTab === "chart" && (
            <div className="p-0">
              <TradingViewChart ticker={ticker} timeframe={timeframe} />
            </div>
          )}

          {activeTab === "watchlist" && (
            <div className="p-4">
              <div className="mb-3 flex flex-wrap gap-2 items-center">
                <div className="flex gap-1 items-center">
                  <Input
                    value={newWatchlistTicker}
                    onChange={e => setNewWatchlistTicker(e.target.value.toUpperCase())}
                    placeholder="Add ticker..."
                    className="w-28 bg-black/50 border-white/20 uppercase text-cyan-400 font-bold text-xs h-8"
                    onKeyDown={e => {
                      if (e.key === "Enter" && newWatchlistTicker && !watchlistTickers.includes(newWatchlistTicker)) {
                        setWatchlistTickers(prev => [...prev, newWatchlistTicker]);
                        setNewWatchlistTicker("");
                        addToast(`Added ${newWatchlistTicker} to watchlist`, "success");
                      }
                    }}
                  />
                  <Button
                    size="sm"
                    className="bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs h-8 px-2"
                    onClick={() => {
                      if (newWatchlistTicker && !watchlistTickers.includes(newWatchlistTicker)) {
                        setWatchlistTickers(prev => [...prev, newWatchlistTicker]);
                        setNewWatchlistTicker("");
                        addToast(`Added ${newWatchlistTicker} to watchlist`, "success");
                      }
                    }}
                  >+</Button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {watchlistTickers.map(t => (
                    <Badge key={t} variant="outline" className="text-purple-400 border-purple-500/30 bg-purple-500/5 text-[10px] cursor-pointer hover:bg-red-500/20 hover:border-red-500/30 hover:text-red-400 transition-colors"
                      onClick={() => {
                        setWatchlistTickers(prev => prev.filter(x => x !== t));
                        addToast(`Removed ${t} from watchlist`, "info");
                      }}
                    >
                      {t} Ã—
                    </Badge>
                  ))}
                </div>
              </div>
              <WatchlistPanel data={watchlistData} isScanning={isScanning} onSelect={(t: string) => { setTicker(t); setActiveTab("chart"); loadChartData(t, timeframe); }} />
            </div>
          )}

          {activeTab === "consensus" && (
            <div className="p-4">
              <ConsensusPanel data={consensusData} isRunning={isConsensusRunning} ticker={ticker} />
            </div>
          )}

          {activeTab === "ict" && (
            <div className="p-4">
              <ICTPanel data={ictData} isRunning={isIctRunning} ticker={ticker} />
            </div>
          )}

          {activeTab === "backtest" && (
            <div className="p-4">
              <BacktestPanel data={backtestData} isRunning={isBacktesting} ticker={ticker} />
            </div>
          )}

          {activeTab === "outcomes" && (
            <div className="p-4">
              {!outcomesData ? (
                <div className="text-center text-slate-600 py-8">Loading performance data...</div>
              ) : (
                <div className="space-y-4">
                  {/* Stats Row */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded bg-black/40 border border-pink-500/20 text-center">
                      <div className="text-[10px] text-slate-500 font-bold">TOTAL TRACKED</div>
                      <div className="text-2xl font-black text-white">{outcomesData.total || 0}</div>
                    </div>
                    <div className="p-3 rounded bg-black/40 border border-green-500/20 text-center">
                      <div className="text-[10px] text-slate-500 font-bold">WINS</div>
                      <div className="text-2xl font-black text-green-400">{outcomesData.wins || 0}</div>
                    </div>
                    <div className="p-3 rounded bg-black/40 border border-red-500/20 text-center">
                      <div className="text-[10px] text-slate-500 font-bold">LOSSES</div>
                      <div className="text-2xl font-black text-red-400">{outcomesData.losses || 0}</div>
                    </div>
                    <div className="p-3 rounded bg-black/40 border border-cyan-500/20 text-center">
                      <div className="text-[10px] text-slate-500 font-bold">WIN RATE</div>
                      <div className={`text-2xl font-black ${(outcomesData.win_rate || 0) >= 50 ? "text-green-400" : "text-red-400"}`}>
                        {outcomesData.win_rate || 0}%
                      </div>
                    </div>
                  </div>

                  {/* AI Learning Context */}
                  {outcomesData.learning_context && (
                    <div className="p-3 rounded bg-pink-500/5 border border-pink-500/20">
                      <div className="text-[10px] text-pink-400 font-bold mb-1">ðŸ§  AI SELF-LEARNING CONTEXT</div>
                      <pre className="text-[11px] text-slate-400 whitespace-pre-wrap font-mono">{outcomesData.learning_context}</pre>
                    </div>
                  )}

                  {/* Report Outcome for current signal */}
                  {signal && (
                    <div className="p-3 rounded bg-black/40 border border-white/10">
                      <div className="text-[10px] text-slate-400 font-bold mb-2">REPORT OUTCOME FOR: {signal.ticker} {signal.signal}</div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-green-600 hover:bg-green-500 text-white font-bold text-xs" onClick={() => reportOutcome(signal, "WIN", 2.0)}>
                          âœ… WIN (+2%)
                        </Button>
                        <Button size="sm" className="bg-green-700 hover:bg-green-600 text-white font-bold text-xs" onClick={() => reportOutcome(signal, "WIN", 5.0)}>
                          âœ… WIN (+5%)
                        </Button>
                        <Button size="sm" className="bg-red-600 hover:bg-red-500 text-white font-bold text-xs" onClick={() => reportOutcome(signal, "LOSS", -1.0)}>
                          âŒ LOSS (-1%)
                        </Button>
                        <Button size="sm" className="bg-red-700 hover:bg-red-600 text-white font-bold text-xs" onClick={() => reportOutcome(signal, "LOSS", -2.0)}>
                          âŒ LOSS (-2%)
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Recent Outcomes */}
                  {outcomesData.outcomes?.length > 0 && (
                    <div>
                      <div className="text-[10px] text-slate-500 font-bold mb-2">RECENT OUTCOMES</div>
                      <div className="space-y-1 max-h-[250px] overflow-y-auto">
                        {outcomesData.outcomes.map((o: any, i: number) => (
                          <div key={i} className="flex items-center gap-3 p-2 bg-black/30 rounded text-xs">
                            <span className={`font-bold min-w-[50px] ${o.result === "WIN" ? "text-green-400" : "text-red-400"}`}>{o.result}</span>
                            <span className="text-white font-bold">{o.ticker}</span>
                            <span className="text-slate-500">{o.signal}</span>
                            <span className={`ml-auto font-black ${o.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                              {o.pnl_pct > 0 ? "+" : ""}{o.pnl_pct}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "history" && (
            <div className="p-4 max-h-[400px] overflow-y-auto">
              {signalHistory.length === 0 ? (
                <div className="text-center text-slate-600 py-8">
                  No signals yet. Run an analysis to populate history.
                </div>
              ) : (
                <div className="space-y-2">
                  {signalHistory.map((sig, i) => (
                    <div key={i} className="flex items-center gap-4 p-3 bg-black/40 rounded border border-white/5 hover:border-white/15 transition-all">
                      <div className={`px-2 py-1 rounded text-xs font-black ${
                        sig.signal === "LONG" ? "bg-green-500/20 text-green-400" :
                        sig.signal === "SHORT" ? "bg-red-500/20 text-red-400" :
                        "bg-yellow-500/20 text-yellow-400"
                      }`}>
                        {sig.signal}
                      </div>
                      <div className="text-white font-bold text-sm">{sig.ticker}</div>
                      <div className="text-slate-500 text-xs">{sig.timeframe}</div>
                      <div className="text-slate-400 text-xs">
                        Entry: {sig.entry_zone?.min?.toFixed(2)} - {sig.entry_zone?.max?.toFixed(2)}
                      </div>
                      <div className="text-slate-400 text-xs ml-auto">
                        Conf: {sig.confidence}% | R:R {sig.risk_reward}
                      </div>
                      {sig.timestamp_utc && (
                        <div className="text-slate-600 text-[10px]">
                          {new Date(sig.timestamp_utc).toLocaleTimeString()}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Analyst Layer */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <AgentCard title="FUNDAMENTAL" data={agentData["FUNDAMENTAL_ANALYST"]} />
          <AgentCard title="SENTIMENT" data={agentData["SENTIMENT_ANALYST"]} />
          <AgentCard title="NEWS" data={agentData["NEWS_ANALYST"]} />
          <AgentCard title="TECHNICAL" data={agentData["TECHNICAL_ANALYST"]} />
        </div>

        {/* Debate Layer */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="bg-black/40 border-red-500/30 shadow-[0_0_15px_rgba(239,68,68,0.1)] backdrop-blur-sm transition-all duration-500">
            <CardHeader className="border-b border-red-500/20 pb-2">
              <CardTitle className="text-red-400 flex justify-between items-center text-sm">
                <span>[BEAR_RESEARCHER]</span>
                {agentData["BEAR_RESEARCHER"] && <Badge variant="outline" className="text-red-400 border-red-500/50 bg-red-500/10 animate-in fade-in">DONE</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 text-sm leading-relaxed text-slate-300 min-h-[100px]">
              {agentData["BEAR_RESEARCHER"] || <span className="text-slate-600 animate-pulse">Awaiting arguments...</span>}
            </CardContent>
          </Card>

          <Card className="bg-black/40 border-green-500/30 shadow-[0_0_15px_rgba(34,197,94,0.1)] backdrop-blur-sm transition-all duration-500">
            <CardHeader className="border-b border-green-500/20 pb-2">
              <CardTitle className="text-green-400 flex justify-between items-center text-sm">
                <span>[BULL_RESEARCHER]</span>
                {agentData["BULL_RESEARCHER"] && <Badge variant="outline" className="text-green-400 border-green-500/50 bg-green-500/10 animate-in fade-in">DONE</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 text-sm leading-relaxed text-slate-300 min-h-[100px]">
              {agentData["BULL_RESEARCHER"] || <span className="text-slate-600 animate-pulse">Awaiting arguments...</span>}
            </CardContent>
          </Card>
        </div>

        {/* Execution Layer */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AgentCard title="TRADER_DECISION" data={agentData["TRADER_DECISION"]} accent="cyan" />
          <AgentCard title="RISK_MANAGER" data={agentData["RISK_MANAGER"]} accent="cyan" />
        </div>

        {/* Signal Engine Verdict */}
        {signal && (
          <div className="mt-8 animate-in slide-in-from-bottom-4 fade-in duration-700">
            <Card className="bg-slate-900 border-white/20 shadow-2xl relative overflow-hidden">
              <div className={`absolute top-0 left-0 w-2 h-full ${
                  signal.signal === "LONG" ? "bg-green-500" : 
                  signal.signal === "SHORT" ? "bg-red-500" : "bg-yellow-500"
                }`} 
              />
              <CardHeader className="border-b border-white/10 ml-2">
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle className="text-xl text-white">SIGNAL ENGINE VERDICT</CardTitle>
                    {signal.market_regime && (
                      <span className="text-xs text-slate-500 mt-1">Regime: {signal.market_regime}</span>
                    )}
                  </div>
                  <div className={`px-6 py-2 rounded font-black text-2xl tracking-widest ${
                    signal.signal === "LONG" ? "bg-green-500 text-black shadow-[0_0_20px_rgba(34,197,94,0.4)]" : 
                    signal.signal === "SHORT" ? "bg-red-500 text-white shadow-[0_0_20px_rgba(239,68,68,0.4)]" : 
                    "bg-yellow-500 text-black"
                  }`}>
                    {signal.signal}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-6 ml-2 grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* Execution Metrics */}
                <div className="space-y-4">
                  <h3 className="text-xs text-slate-500 font-bold tracking-widest uppercase">Execution Parameters</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="text-slate-400">Entry Zone:</div>
                    <div className="text-white font-bold">{signal.entry_zone.min.toFixed(2)} - {signal.entry_zone.max.toFixed(2)}</div>
                    
                    <div className="text-slate-400">Stop Loss:</div>
                    <div className="text-red-400 font-bold">{signal.stop_loss.toFixed(2)}</div>
                    
                    {signal.take_profit.map((tp, idx) => (
                      <div key={idx} className="col-span-2 grid grid-cols-2 gap-2">
                        <div className="text-slate-400">Take Profit {tp.level}:</div>
                        <div className="text-green-400 font-bold">{tp.price.toFixed(2)}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Risk Metrics */}
                <div className="space-y-4">
                  <h3 className="text-xs text-slate-500 font-bold tracking-widest uppercase">Risk & Confidence</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="text-slate-400">Confidence:</div>
                    <div className="text-white font-bold">{signal.confidence}%</div>
                    
                    <div className="text-slate-400">Risk:Reward:</div>
                    <div className="text-white font-bold">{signal.risk_reward}</div>

                    <div className="text-slate-400">Pos Size:</div>
                    <div className="text-white font-bold">{signal.position_size_pct}%</div>
                  </div>

                  {/* Indicators Used */}
                  {signal.indicators_used && (
                    <div className="mt-4 pt-3 border-t border-white/5">
                      <h4 className="text-[10px] text-slate-600 font-bold tracking-widest uppercase mb-2">Indicators Used</h4>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(signal.indicators_used).map(([key, val]) => (
                          val !== null && (
                            <span key={key} className="text-[10px] px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/20 rounded text-cyan-400">
                              {key}: {val}
                            </span>
                          )
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Webhook payload */}
                <div className="space-y-4">
                  <h3 className="text-xs text-slate-500 font-bold tracking-widest uppercase">TradingView Webhook Payload</h3>
                  <div className="bg-black/60 border border-white/10 p-3 rounded text-xs text-cyan-400 break-all select-all focus:ring-1 focus:ring-cyan-500 cursor-copy">
                    {signal.tv_alert}
                  </div>
                  <div className="text-xs text-slate-500 mt-2">
                    * Click to select string for Pine Script alerts
                  </div>
                </div>
                
                {/* Reasons */}
                <div className="col-span-full mt-4 pt-4 border-t border-white/10 text-sm">
                  <h3 className="text-xs text-slate-500 font-bold tracking-widest uppercase mb-2">Rationale</h3>
                  <ul className="list-disc list-inside space-y-1 text-slate-300">
                    {signal.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
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
              {toast.type === "success" ? "âœ… " : toast.type === "error" ? "âŒ " : "â„¹ï¸ "}
              {toast.message}
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
