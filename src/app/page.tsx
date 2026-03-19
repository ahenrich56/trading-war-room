"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Define the signal payload structure
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

  const runAnalysis = async () => {
    setIsRunning(true);
    setAgentData({});
    setSignal(null);
    setError(null);
    setCurrentStage(ALL_STAGES[0]);
    setProgress(0);

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

              // Parse format: [MARKER] JSON
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
                  
                  // Update progress
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
      {/* Background Dot Grid */}
      <div className="absolute inset-0 bg-[url('/dots.svg')] bg-repeat opacity-[0.03] pointer-events-none" />

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-gradient-to-b from-slate-900 to-slate-950 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-3 w-3 rounded-full bg-cyan-500 animate-pulse" />
          <h1 className="text-xl font-bold text-white tracking-wider">AI TRADING WAR ROOM</h1>
        </div>
        
        {/* Controls */}
        <div className="flex gap-4 items-center">
          <Input 
            value={ticker} 
            onChange={e => setTicker(e.target.value.toUpperCase())}
            placeholder="TICKER" 
            className="w-24 bg-black/50 border-white/20 uppercase text-cyan-400 font-bold"
          />
          <Select value={timeframe} onValueChange={setTimeframe}>
            <SelectTrigger className="w-24 bg-black/50 border-white/20">
              <SelectValue placeholder="TF" />
            </SelectTrigger>
            <SelectContent className="bg-slate-900 border-white/20 text-white">
              <SelectItem value="1m">1m</SelectItem>
              <SelectItem value="5m">5m</SelectItem>
              <SelectItem value="15m">15m</SelectItem>
            </SelectContent>
          </Select>
          <Select value={riskProfile} onValueChange={setRiskProfile}>
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

        {/* Signal Engine Deterministic Output */}
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
                  <CardTitle className="text-xl text-white">SIGNAL ENGINE VERDICT</CardTitle>
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
                </div>

                {/* Automation string */}
                <div className="space-y-4">
                  <h3 className="text-xs text-slate-500 font-bold tracking-widest uppercase">TradingView Webhook Payload</h3>
                  <div className="bg-black/60 border border-white/10 p-3 rounded text-xs text-cyan-400 break-all select-all focus:ring-1 focus:ring-cyan-500 cursor-copy">
                    {signal.tv_alert}
                  </div>
                  <div className="text-xs text-slate-500 mt-2">
                    * Click to select string for Pine Script alerts
                  </div>
                </div>
                
                {/* Reasons List */}
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
