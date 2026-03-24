"use client";

import { TermTooltip } from "@/components/TermTooltip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, BarChart3, Target, Shield, Zap } from "lucide-react";

export function BacktestPanel({ data, isRunning, ticker }: { data: any, isRunning: boolean, ticker: string }) {
  if (isRunning) {
    return (
      <div className="h-[450px] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="relative">
            <div className="h-16 w-16 mx-auto rounded-full border-2 border-orange-500/30 border-t-orange-400 animate-spin" />
            <BarChart3 className="h-6 w-6 text-orange-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          </div>
          <div className="text-sm text-orange-400 font-bold tracking-wider">BACKTESTING <span className="text-white">{ticker}</span></div>
          <div className="text-[10px] text-slate-600">Replaying signals against historical data</div>
        </div>
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div className="h-[450px] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="h-16 w-16 mx-auto rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
            <BarChart3 className="h-8 w-8 text-orange-500/40" />
          </div>
          <div className="text-sm text-slate-500">{data?.error || "Click BACKTEST to replay signals"}</div>
          <div className="text-[10px] text-slate-700">Win rate • Sharpe • Max DD • Kelly sizing</div>
        </div>
      </div>
    );
  }

  const wrColor = data.win_rate >= 60 ? "text-green-400" : data.win_rate >= 45 ? "text-yellow-400" : "text-red-400";
  const wrBg = data.win_rate >= 60 ? "from-green-500/10 to-green-500/5 border-green-500/20" : data.win_rate >= 45 ? "from-yellow-500/10 to-yellow-500/5 border-yellow-500/20" : "from-red-500/10 to-red-500/5 border-red-500/20";
  const eqColor = data.equity_change_pct >= 0 ? "text-green-400" : "text-red-400";
  const kelly = data.kelly_optimal_pct || {};

  return (
    <div className="space-y-4">
      {/* Hero Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className={`bg-gradient-to-b ${wrBg} backdrop-blur-sm`}>
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-slate-500 font-bold tracking-wider mb-1">
              <TermTooltip term="Win Rate" description="Percentage of winning trades out of total trades executed.">
                WIN RATE
              </TermTooltip>
            </div>
            <div className={`text-2xl font-black ${wrColor}`}>{data.win_rate}%</div>
            <div className="text-[10px] text-slate-600 mt-1">{data.wins}W / {data.losses}L</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-b from-white/5 to-transparent border-white/10 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-slate-500 font-bold tracking-wider mb-1">
              <TermTooltip term="Profit Factor" description="Gross profit divided by gross loss. Above 1.0 is profitable.">
                PROFIT FACTOR
              </TermTooltip>
            </div>
            <div className="text-2xl font-black text-white">{data.profit_factor}</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-b from-white/5 to-transparent border-white/10 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-slate-500 font-bold tracking-wider mb-1">
              <TermTooltip term="Sharpe Ratio" description="Measure of risk-adjusted return. Over 1.0 is good, over 2.0 is excellent.">
                SHARPE
              </TermTooltip>
            </div>
            <div className={`text-2xl font-black ${data.sharpe_ratio > 1 ? "text-green-400" : "text-yellow-400"}`}>{data.sharpe_ratio}</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-b from-red-500/10 to-transparent border-red-500/20 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-slate-500 font-bold tracking-wider mb-1">
              <TermTooltip term="Max Drawdown" description="Largest peak-to-trough drop in account equity. Lower is better.">
                MAX DRAWDOWN
              </TermTooltip>
            </div>
            <div className="text-2xl font-black text-red-400">{data.max_drawdown_pct}%</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-b from-cyan-500/10 to-transparent border-cyan-500/20 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-slate-500 font-bold tracking-wider mb-1">EQUITY</div>
            <div className={`text-2xl font-black ${eqColor}`}>${data.final_equity?.toLocaleString()}</div>
            <div className={`text-[10px] ${eqColor}`}>{data.equity_change_pct > 0 ? "+" : ""}{data.equity_change_pct}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Kelly Criterion */}
      {kelly.recommended !== undefined && (
        <Card className="border-orange-500/20 bg-gradient-to-r from-orange-500/5 to-transparent backdrop-blur-sm">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-xs text-orange-400 font-bold tracking-wider flex items-center gap-2">
              <Target className="h-4 w-4" />
              <TermTooltip term="Kelly Criterion" description="A mathematical formula that determines the optimal size of a series of bets to maximize wealth over time.">
                KELLY CRITERION SIZING
              </TermTooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="grid grid-cols-4 gap-3 text-center">
              <div className="p-2 rounded-lg bg-black/20">
                <div className="text-[10px] text-slate-500">Full Kelly</div>
                <div className="text-sm font-bold text-white">{kelly.full_kelly}%</div>
              </div>
              <div className="p-2 rounded-lg bg-black/20">
                <div className="text-[10px] text-slate-500">Half Kelly</div>
                <div className="text-sm font-bold text-white">{kelly.half_kelly}%</div>
              </div>
              <div className="p-2 rounded-lg bg-orange-500/15 border border-orange-500/30">
                <div className="text-[10px] text-orange-400 font-bold">★ Recommended</div>
                <div className="text-sm font-black text-orange-400">{kelly.quarter_kelly}%</div>
              </div>
              <div className="p-2 rounded-lg bg-black/20">
                <div className="text-[10px] text-slate-500">Edge</div>
                <div className={`text-sm font-bold ${kelly.edge > 0 ? "text-green-400" : "text-red-400"}`}>{kelly.edge}%</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Trades */}
      {data.trades?.length > 0 && (
        <div>
          <div className="text-[10px] text-slate-500 font-bold tracking-wider mb-2 flex items-center gap-2">
            <Zap className="h-3 w-3" /> RECENT TRADES ({data.total_trades} total)
          </div>
          <div className="space-y-1 max-h-[200px] overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
            {data.trades.map((t: any, i: number) => (
              <div key={i} className="flex items-center gap-3 p-2.5 bg-black/30 rounded-lg border border-white/5 hover:border-white/10 transition-colors text-xs group">
                <span className={`font-bold min-w-[50px] flex items-center gap-1 ${t.direction === "LONG" ? "text-green-400" : "text-red-400"}`}>
                  {t.direction === "LONG" ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                  {t.direction}
                </span>
                <span className="text-slate-500">Entry: <span className="text-slate-300">${t.entry}</span></span>
                <span className="text-slate-600">→</span>
                <span className="text-slate-500">Exit: <span className="text-slate-300">${t.exit}</span></span>
                <Badge variant="outline" className={`text-[10px] ${t.result === "WIN" ? "border-green-500/30 text-green-400 bg-green-500/10" : "border-red-500/30 text-red-400 bg-red-500/10"}`}>
                  {t.result}
                </Badge>
                <span className={`text-[10px] ml-auto font-bold ${t.pnl_pct >= 0 ? "text-green-500" : "text-red-500"}`}>
                  {t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
