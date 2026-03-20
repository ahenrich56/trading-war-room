"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Signal payload
interface SignalPayload {
  ticker: string;
  timeframe: string;
  signal: string;
  entry_zone: { min: number; max: number };
  stop_loss: number;
  take_profit: { level: number; price: number }[];
  confidence: number;
  risk_reward: number;
  position_size_pct: number;
  reasons: string[];
  tv_alert: string;
  market_regime?: string;
  timestamp_utc?: string;
  indicators_used?: Record<string, number | null>;
}

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

  const [agentData, setAgentData] = useState<Record<string, any>>({});
  const [signal, setSignal] = useState<SignalPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Chart + History state
  const [chartData, setChartData] = useState<any>(null);
  const [signalHistory, setSignalHistory] = useState<SignalPayload[]>([]);
  const [activeTab, setActiveTab] = useState<"chart" | "history" | "watchlist" | "consensus">("chart");

  // Watchlist + Consensus state
  const [watchlistData, setWatchlistData] = useState<any>(null);
  const [consensusData, setConsensusData] = useState<any>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isConsensusRunning, setIsConsensusRunning] = useState(false);

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

  // Load history on mount
  // Watchlist scan
  const scanWatchlist = useCallback(async () => {
    setIsScanning(true);
    setActiveTab("watchlist");
    try {
      const res = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: ["NQ1", "ES1", "AAPL", "NVDA", "TSLA", "BTCUSD", "GOLD", "AMZN"], timeframe }),
      });
      const data = await res.json();
      setWatchlistData(data);
    } catch (e) {
      console.error("Watchlist scan failed:", e);
    } finally {
      setIsScanning(false);
    }
  }, [timeframe]);

  // Multi-model consensus
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
    } catch (e) {
      console.error("Consensus failed:", e);
    } finally {
      setIsConsensusRunning(false);
    }
  }, [ticker, timeframe]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const runAnalysis = async () => {
    setIsRunning(true);
    setAgentData({});
    setSignal(null);
    setError(null);
    setCurrentStage(ALL_STAGES[0]);
    setProgress(0);

    // Also fetch chart data in parallel
    loadChartData(ticker, timeframe);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, timeframe, riskProfile }),
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
    } catch (err: any) {
      setError(err.message || "Failed to run analysis");
    } finally {
      setIsRunning(false);
      setProgress(100);
      setCurrentStage("COMPLETE");
    }
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-slate-300 font-mono font-[family-name:var(--font-jetbrains-mono)] selection:bg-cyan-900">
      <div className="absolute inset-0 bg-[url('/dots.svg')] bg-repeat opacity-[0.03] pointer-events-none" />

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-gradient-to-b from-slate-900 to-slate-950 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-3 w-3 rounded-full bg-cyan-500 animate-pulse" />
          <h1 className="text-xl font-bold text-white tracking-wider">AI TRADING WAR ROOM</h1>
          <Badge variant="outline" className="text-cyan-400 border-cyan-500/30 bg-cyan-500/5 text-[10px]">v3.0</Badge>
        </div>
        
        <div className="flex gap-4 items-center">
          <Input 
            value={ticker} 
            onChange={e => setTicker(e.target.value.toUpperCase())}
            placeholder="TICKER" 
            className="w-24 bg-black/50 border-white/20 uppercase text-cyan-400 font-bold"
          />
          <Select value={timeframe} onValueChange={(v) => v && setTimeframe(v)}>
            <SelectTrigger className="w-24 bg-black/50 border-white/20">
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
            <SelectTrigger className="w-32 bg-black/50 border-white/20">
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
            className="bg-cyan-600 hover:bg-cyan-500 text-white font-bold"
          >
            {isRunning ? "ANALYZING..." : "RUN ANALYSIS"}
          </Button>
          <Button 
            onClick={scanWatchlist} 
            disabled={isScanning}
            variant="outline"
            className="border-purple-500/50 text-purple-400 hover:bg-purple-500/10 font-bold text-xs"
          >
            {isScanning ? "SCANNING..." : "📡 SCAN"}
          </Button>
          <Button 
            onClick={runConsensus} 
            disabled={isConsensusRunning}
            variant="outline"
            className="border-amber-500/50 text-amber-400 hover:bg-amber-500/10 font-bold text-xs"
          >
            {isConsensusRunning ? "VOTING..." : "🗳️ CONSENSUS"}
          </Button>
        </div>
      </header>

      {/* Progress Bar */}
      {isRunning && (
        <div className="px-6 py-2 bg-black/40 border-b border-white/5 flex items-center gap-4">
          <span className="text-xs text-cyan-500 w-48 truncate">
            {currentStage ? `[${currentStage}]` : "INITIALIZING..."}
          </span>
          <Progress value={progress} className="h-1 bg-white/10 [&>div]:bg-cyan-500" />
        </div>
      )}

      {error && (
        <div className="m-6 p-4 border border-red-500/50 bg-red-500/10 text-red-400 rounded-md">
          [SYSTEM ERROR]: {error}
        </div>
      )}

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        {/* ═══ CHART + SIGNAL HISTORY TABS ═══ */}
        <div className="border border-white/10 rounded-lg bg-black/30 backdrop-blur-sm overflow-hidden">
          <div className="flex border-b border-white/10">
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
              🗳️ CONSENSUS
            </button>
          </div>

          {activeTab === "chart" && (
            <div className="p-4">
              <MiniChart chartData={chartData} signal={signal} ticker={ticker} />
            </div>
          )}

          {activeTab === "watchlist" && (
            <div className="p-4">
              <WatchlistPanel data={watchlistData} isScanning={isScanning} onSelect={(t: string) => { setTicker(t); setActiveTab("chart"); loadChartData(t, timeframe); }} />
            </div>
          )}

          {activeTab === "consensus" && (
            <div className="p-4">
              <ConsensusPanel data={consensusData} isRunning={isConsensusRunning} ticker={ticker} />
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
    </div>
  );
}

// ═══ MINI CHART COMPONENT (TradingView Lightweight Charts) ═══
function MiniChart({ chartData, signal, ticker }: { chartData: any, signal: SignalPayload | null, ticker: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const [lwcLoaded, setLwcLoaded] = useState(false);
  const [lwcModule, setLwcModule] = useState<any>(null);

  // Load LWC library dynamically
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js";
    script.async = true;
    script.onload = () => {
      setLwcLoaded(true);
      setLwcModule((window as any).LightweightCharts);
    };
    document.head.appendChild(script);
    return () => { document.head.removeChild(script); };
  }, []);

  // Render chart when data arrives
  useEffect(() => {
    if (!lwcLoaded || !lwcModule || !containerRef.current || !chartData?.candles?.length) return;

    // Clear previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = lwcModule.createChart(containerRef.current, {
      layout: {
        background: { type: "solid", color: "#0a0a0b" },
        textColor: "#64748b",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.03)" },
        horzLines: { color: "rgba(255,255,255,0.03)" },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: "rgba(103,232,249,0.3)", width: 1, style: 2 },
        horzLine: { color: "rgba(103,232,249,0.3)", width: 1, style: 2 },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: {
        borderColor: "rgba(255,255,255,0.1)",
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: 350,
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candleSeries.setData(chartData.candles);

    // Volume
    const volumeSeries = chart.addHistogramSeries({
      color: "rgba(103,232,249,0.15)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    const volData = chartData.candles.map((c: any) => ({
      time: c.time,
      value: c.volume,
      color: c.close >= c.open ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
    }));
    volumeSeries.setData(volData);

    // EMA 9 overlay
    if (chartData.indicators?.ema9?.length) {
      const ema9Series = chart.addLineSeries({ color: "#67e8f9", lineWidth: 1, priceLineVisible: false });
      ema9Series.setData(chartData.indicators.ema9);
    }

    // EMA 21 overlay
    if (chartData.indicators?.ema21?.length) {
      const ema21Series = chart.addLineSeries({ color: "#fbbf24", lineWidth: 1, priceLineVisible: false });
      ema21Series.setData(chartData.indicators.ema21);
    }

    // VWAP overlay
    if (chartData.indicators?.vwap?.length) {
      const vwapSeries = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1, lineStyle: 2, priceLineVisible: false });
      vwapSeries.setData(chartData.indicators.vwap);
    }

    // Signal levels (entry zone, SL, TP)
    if (signal && signal.signal !== "NO_TRADE") {
      const entryColor = signal.signal === "LONG" ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)";
      
      candleSeries.createPriceLine({
        price: signal.entry_zone.min,
        color: entryColor,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Entry Min",
      });
      candleSeries.createPriceLine({
        price: signal.entry_zone.max,
        color: entryColor,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Entry Max",
      });
      candleSeries.createPriceLine({
        price: signal.stop_loss,
        color: "#ef4444",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "SL",
      });
      signal.take_profit.forEach((tp) => {
        candleSeries.createPriceLine({
          price: tp.price,
          color: "#22c55e",
          lineWidth: 1,
          lineStyle: 0,
          axisLabelVisible: true,
          title: `TP${tp.level}`,
        });
      });
    }

    chart.timeScale().fitContent();
    chartRef.current = chart;

    // Responsive
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [lwcLoaded, lwcModule, chartData, signal]);

  if (!chartData?.candles?.length) {
    return (
      <div className="h-[350px] flex items-center justify-center text-slate-600">
        <div className="text-center">
          <div className="text-3xl mb-2">📊</div>
          <div className="text-sm">Run an analysis to load chart data</div>
          <div className="text-[10px] mt-1 text-slate-700">{ticker} • With EMA 9/21, VWAP overlays & signal levels</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-white font-bold">{chartData.ticker || ticker}</span>
        <span className="text-[10px] text-slate-600">{chartData.symbol}</span>
        <div className="flex gap-3 ml-auto text-[10px]">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-cyan-400 inline-block"></span> EMA 9</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-yellow-400 inline-block"></span> EMA 21</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-purple-400 inline-block" style={{borderTop: "1px dashed"}}></span> VWAP</span>
        </div>
      </div>
      <div ref={containerRef} className="w-full rounded overflow-hidden" />
    </div>
  );
}

// ═══ AGENT CARD COMPONENT ═══
function AgentCard({ title, data, accent = "white" }: { title: string, data?: string, accent?: string }) {
  const isComplete = !!data;
  
  return (
    <Card className="bg-black/30 border-white/10 backdrop-blur-md transition-all duration-500 overflow-hidden h-full flex flex-col">
      <CardHeader className="border-b border-white/5 pb-2 bg-gradient-to-b from-white/[0.02] to-transparent">
        <CardTitle className={`text-sm tracking-wider flex justify-between items-center ${accent === "cyan" ? "text-cyan-400" : "text-slate-300"}`}>
          <span>[{title}]</span>
          {isComplete && <Badge variant="secondary" className="bg-white/10 text-white hover:bg-white/20 px-1 py-0 text-[10px] animate-in fade-in">DONE</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 text-xs leading-relaxed text-slate-400 flex-grow">
        {data ? (
          <div className="animate-in fade-in slide-in-from-top-2">{data}</div>
        ) : (
          <div className="flex space-x-1 items-center opacity-50">
            <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
            <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
            <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce"></div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ═══ WATCHLIST PANEL ═══
function WatchlistPanel({ data, isScanning, onSelect }: { data: any, isScanning: boolean, onSelect: (t: string) => void }) {
  if (isScanning) {
    return (
      <div className="h-[350px] flex items-center justify-center text-purple-400">
        <div className="text-center">
          <div className="text-3xl mb-2 animate-spin">📡</div>
          <div className="text-sm">Scanning 8 tickers across all indicators...</div>
          <div className="text-[10px] mt-2 text-slate-600">RSI • MACD • EMA Cross • ADX • Volume</div>
        </div>
      </div>
    );
  }

  if (!data?.tickers?.length) {
    return (
      <div className="h-[350px] flex items-center justify-center text-slate-600">
        <div className="text-center">
          <div className="text-3xl mb-2">📡</div>
          <div className="text-sm">Click SCAN to scan your watchlist</div>
          <div className="text-[10px] mt-1 text-slate-700">NQ1 • ES1 • AAPL • NVDA • TSLA • BTC • GOLD • AMZN</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-500">
          Scanned: {new Date(data.scanned_at).toLocaleTimeString()} • {data.timeframe}
        </span>
        {data.best_opportunity && (
          <span className="text-xs text-purple-400">
            🏆 Best: <strong>{data.best_opportunity.ticker}</strong> (score: {data.best_opportunity.score})
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        {data.tickers.map((t: any, i: number) => (
          <div
            key={i}
            onClick={() => !t.error && onSelect(t.ticker)}
            className="flex items-center gap-3 p-2.5 bg-black/40 rounded border border-white/5 hover:border-white/20 transition-all cursor-pointer group"
          >
            {/* Rank */}
            <span className="text-[10px] text-slate-600 w-5">#{i + 1}</span>

            {/* Direction badge */}
            <div className={`px-2 py-0.5 rounded text-[10px] font-black min-w-[60px] text-center ${
              t.direction === "LONG" ? "bg-green-500/20 text-green-400" :
              t.direction === "SHORT" ? "bg-red-500/20 text-red-400" :
              "bg-slate-500/20 text-slate-400"
            }`}>
              {t.direction || "ERR"}
            </div>

            {/* Ticker + Price */}
            <div className="w-16">
              <div className="text-white font-bold text-xs group-hover:text-cyan-400 transition-colors">{t.ticker}</div>
            </div>
            <div className="text-slate-300 text-xs w-20">${t.price || "—"}</div>

            {/* Score bar */}
            <div className="flex-1 relative h-4 bg-black/40 rounded overflow-hidden">
              <div
                className={`absolute top-0 h-full rounded transition-all ${
                  t.score > 0 ? "bg-green-500/40 left-1/2" : "bg-red-500/40 right-1/2"
                }`}
                style={{ width: `${Math.abs(t.score || 0) / 2}%` }}
              />
              <span className={`absolute inset-0 flex items-center justify-center text-[10px] font-bold ${
                t.score > 15 ? "text-green-400" : t.score < -15 ? "text-red-400" : "text-slate-500"
              }`}>
                {t.score || 0}
              </span>
            </div>

            {/* Quick indicators */}
            <div className="flex gap-2 text-[10px] text-slate-500 w-48 justify-end">
              {t.rsi && <span>RSI:{t.rsi}</span>}
              {t.adx && <span>ADX:{t.adx}</span>}
              {t.vol_ratio && <span>Vol:{t.vol_ratio}x</span>}
            </div>

            <span className="text-slate-700 text-xs group-hover:text-cyan-500 transition-colors">→</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══ CONSENSUS PANEL ═══
function ConsensusPanel({ data, isRunning, ticker }: { data: any, isRunning: boolean, ticker: string }) {
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
  const consensusBg = data.consensus === "LONG" ? "bg-green-500/20" : data.consensus === "SHORT" ? "bg-red-500/20" : "bg-yellow-500/20";

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
