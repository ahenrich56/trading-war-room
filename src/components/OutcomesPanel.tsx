"use client";

import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, X, TrendingUp, TrendingDown, Clock } from "lucide-react";

interface SignalData {
  ticker: string;
  timeframe: string;
  signal: string;
  confidence: number;
  entry_zone?: { min: number; max: number };
  stop_loss?: number;
  take_profit?: { level: number; price: number }[];
  timestamp?: string;
  reasons?: string[];
}

interface OutcomeStats {
  total: number;
  wins: number;
  losses: number;
  win_rate: number;
  outcomes: any[];
}

export function OutcomesPanel() {
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [stats, setStats] = useState<OutcomeStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [sigRes, outRes] = await Promise.all([
        fetch("/api/signals?limit=10"),
        fetch("/api/outcomes")
      ]);

      if (sigRes.ok) {
        const sigData = await sigRes.json();
        setSignals(sigData.signals || []);
      }
      if (outRes.ok) {
        const outData = await outRes.json();
        setStats(outData);
      }
    } catch (error) {
      console.error("Error fetching outcomes or signals:", error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    // Refresh periodically
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const reportOutcome = async (sig: SignalData, result: "WIN" | "LOSS") => {
    try {
      // Send a POST to /api/outcomes
      const payload = {
        ticker: sig.ticker,
        signal: sig.signal,
        entry: sig.entry_zone ? (sig.entry_zone.max + sig.entry_zone.min)/2 : 0,
        result: result,
        pnl_pct: result === "WIN" ? 1.5 : -1.0, // Default mock values for PnL
        notes: "Marked manually from OutcomesPanel"
      };

      await fetch("/api/outcomes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      // Refresh to get updated stats
      fetchData();
    } catch (e) {
      console.error("Failed to report outcome", e);
    }
  };

  // Format date safely
  const formatDate = (isoStr?: string) => {
    if (!isoStr) return "Just now";
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return isoStr;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Stats Section */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white/[0.03] backdrop-blur-md border-white/8">
          <CardContent className="p-6">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm font-medium text-slate-400">Total Tracked</p>
                <h3 className="text-2xl font-bold mt-1 text-white">{stats?.total || 0}</h3>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <Clock className="w-5 h-5 text-blue-400" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-white/[0.03] backdrop-blur-md border-white/8">
          <CardContent className="p-6">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm font-medium text-slate-400">Win Rate</p>
                <h3 className="text-2xl font-bold mt-1 text-emerald-400">{stats?.win_rate.toFixed(1) || 0}%</h3>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white/[0.03] backdrop-blur-md border-white/8">
          <CardContent className="p-6">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm font-medium text-slate-400">Wins</p>
                <h3 className="text-2xl font-bold mt-1 text-white">{stats?.wins || 0}</h3>
              </div>
              <div className="p-3 bg-emerald-500/20 rounded-lg">
                <Check className="w-5 h-5 text-emerald-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white/[0.03] backdrop-blur-md border-white/8">
          <CardContent className="p-6">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm font-medium text-slate-400">Losses</p>
                <h3 className="text-2xl font-bold mt-1 text-white">{stats?.losses || 0}</h3>
              </div>
              <div className="p-3 bg-rose-500/20 rounded-lg">
                <X className="w-5 h-5 text-rose-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Signals List */}
        <Card className="bg-white/[0.03] backdrop-blur-md border-white/8 flex-1">
          <CardHeader>
            <CardTitle className="text-white text-lg flex items-center gap-2">
              Recent AI Signals
              {loading && <span className="text-xs text-slate-500 font-normal">Refreshing...</span>}
            </CardTitle>
            <CardDescription className="text-slate-400">
              Grade recent signals to train the self-learning loop.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {signals.length === 0 ? (
              <div className="text-center p-8 text-slate-500">
                No recent signals configured in the database yet.
              </div>
            ) : (
              <div className="space-y-4">
                {signals.map((sig, i) => (
                  <div key={i} className="flex flex-col sm:flex-row items-center justify-between p-4 bg-white/[0.03] backdrop-blur-sm border border-white/8 rounded-lg gap-4">
                    <div className="flex items-center gap-4 w-full sm:w-auto">
                      <div className={`p-2 rounded-md ${sig.signal === "LONG" ? "bg-emerald-500/20 text-emerald-500" : sig.signal === "SHORT" ? "bg-rose-500/20 text-rose-500" : "bg-slate-500/20 text-slate-500"}`}>
                        {sig.signal === "LONG" ? <TrendingUp size={20} /> : sig.signal === "SHORT" ? <TrendingDown size={20} /> : <Clock size={20} />}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white">{sig.ticker}</span>
                          <Badge variant="outline" className="text-xs border-slate-700 text-slate-300 bg-slate-800/50">
                            {formatDate(sig.timestamp)}
                          </Badge>
                          <Badge variant="outline" className="text-xs border-slate-700 text-slate-300">
                            {sig.timeframe}
                          </Badge>
                        </div>
                        <p className="text-sm border-slate-700 text-slate-400 mt-1">
                          Conf: {sig.confidence}% | Entry: {sig.entry_zone?.min || 0}-{sig.entry_zone?.max || 0}
                        </p>
                      </div>
                    </div>
                    {/* Action Buttons to Grade */}
                    <div className="flex gap-2 w-full sm:w-auto justify-end">
                      <Button 
                        size="sm" 
                        variant="ghost" 
                        className="bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20"
                        onClick={() => reportOutcome(sig, "WIN")}
                      >
                        <Check className="w-4 h-4 mr-1" /> Win
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost" 
                        className="bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/20"
                        onClick={() => reportOutcome(sig, "LOSS")}
                      >
                        <X className="w-4 h-4 mr-1" /> Loss
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Historic Outcomes List */}
        <Card className="bg-white/[0.03] backdrop-blur-md border-white/8 flex-1">
          <CardHeader>
            <CardTitle className="text-white text-lg">Self-Learning History</CardTitle>
            <CardDescription className="text-slate-400">
              Recently tracked outcomes that feed into the AI context.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {stats?.outcomes && stats.outcomes.length > 0 ? (
              <div className="space-y-3">
                {stats.outcomes.slice(0, 10).map((out, i) => (
                  <div key={i} className="flex justify-between items-center p-3 border-b border-slate-800/50 last:border-0">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${out.result === "WIN" ? "bg-emerald-500" : "bg-rose-500"}`}></div>
                      <span className="text-white font-medium">{out.ticker}</span>
                      <span className="text-slate-400 text-sm">{out.signal}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400 text-xs">{formatDate(out.reported_at)}</span>
                      <Badge className={out.result === "WIN" ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"}>
                        {out.result === "WIN" ? `+${out.pnl_pct}%` : `${out.pnl_pct}%`}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
               <div className="text-center p-8 text-slate-500">
                No outcomes logged yet. Grade a signal to start.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
