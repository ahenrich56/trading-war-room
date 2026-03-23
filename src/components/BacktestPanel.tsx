"use client";

import { TermTooltip } from "@/components/TermTooltip";

export function BacktestPanel({ data, isRunning, ticker }: { data: any, isRunning: boolean, ticker: string }) {
  if (isRunning) {
    return (
      <div className="h-[350px] flex items-center justify-center text-orange-400">
        <div className="text-center">
          <div className="text-3xl mb-2 animate-spin">📈</div>
          <div className="text-sm">Backtesting <span className="text-white font-bold">{ticker}</span>...</div>
          <div className="text-[10px] mt-2 text-slate-600">Replaying signals against historical data</div>
        </div>
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div className="h-[350px] flex items-center justify-center text-slate-600">
        <div className="text-center">
          <div className="text-3xl mb-2">📈</div>
          <div className="text-sm">{data?.error || "Click BACKTEST to replay signals"}</div>
          <div className="text-[10px] mt-1 text-slate-700">Win rate • Sharpe • Max DD • Kelly sizing</div>
        </div>
      </div>
    );
  }

  const wrColor = data.win_rate >= 60 ? "text-green-400" : data.win_rate >= 45 ? "text-yellow-400" : "text-red-400";
  const eqColor = data.equity_change_pct >= 0 ? "text-green-400" : "text-red-400";
  const kelly = data.kelly_optimal_pct || {};

  return (
    <div>
      {/* Stats Header */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500">
            <TermTooltip term="Win Rate" description="Percentage of winning trades out of total trades executed.">
              WIN RATE
            </TermTooltip>
          </div>
          <div className={`text-xl font-black ${wrColor}`}>{data.win_rate}%</div>
          <div className="text-[10px] text-slate-600">{data.wins}W / {data.losses}L</div>
        </div>
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500">
            <TermTooltip term="Profit Factor" description="Gross profit divided by gross loss. Above 1.0 is profitable.">
              PROFIT FACTOR
            </TermTooltip>
          </div>
          <div className="text-xl font-black text-white">{data.profit_factor}</div>
        </div>
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500">
            <TermTooltip term="Sharpe Ratio" description="Measure of risk-adjusted return. Over 1.0 is good, over 2.0 is excellent.">
              SHARPE
            </TermTooltip>
          </div>
          <div className={`text-xl font-black ${data.sharpe_ratio > 1 ? "text-green-400" : "text-yellow-400"}`}>{data.sharpe_ratio}</div>
        </div>
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500">
            <TermTooltip term="Max Drawdown" description="Largest peak-to-trough drop in account equity. Lower is better.">
              MAX DRAWDOWN
            </TermTooltip>
          </div>
          <div className="text-xl font-black text-red-400">{data.max_drawdown_pct}%</div>
        </div>
        <div className="p-3 rounded bg-black/40 border border-white/10 text-center">
          <div className="text-[10px] text-slate-500">EQUITY</div>
          <div className={`text-xl font-black ${eqColor}`}>${data.final_equity?.toLocaleString()}</div>
          <div className={`text-[10px] ${eqColor}`}>{data.equity_change_pct > 0 ? "+" : ""}{data.equity_change_pct}%</div>
        </div>
      </div>

      {/* Kelly Criterion */}
      {kelly.recommended !== undefined && (
        <div className="mb-4 p-3 rounded bg-black/40 border border-orange-500/20">
          <div className="text-[10px] text-orange-400 font-bold mb-2">
            🎯 <TermTooltip term="Kelly Criterion" description="A mathematical formula that determines the optimal size of a series of bets to maximize wealth over time.">KELLY CRITERION RECOMMENDED SIZING</TermTooltip>
          </div>
          <div className="grid grid-cols-4 gap-3 text-center">
            <div>
              <div className="text-[10px] text-slate-500">Full Kelly</div>
              <div className="text-sm font-bold text-white">{kelly.full_kelly}%</div>
            </div>
            <div>
              <div className="text-[10px] text-slate-500">Half Kelly</div>
              <div className="text-sm font-bold text-white">{kelly.half_kelly}%</div>
            </div>
            <div className="bg-orange-500/10 rounded p-1">
              <div className="text-[10px] text-orange-400">★ Recommended</div>
              <div className="text-sm font-black text-orange-400">{kelly.quarter_kelly}%</div>
            </div>
            <div>
              <div className="text-[10px] text-slate-500">Edge</div>
              <div className={`text-sm font-bold ${kelly.edge > 0 ? "text-green-400" : "text-red-400"}`}>{kelly.edge}%</div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Trades */}
      {data.trades?.length > 0 && (
        <div>
          <div className="text-[10px] text-slate-500 font-bold mb-2">RECENT TRADES ({data.total_trades} total)</div>
          <div className="space-y-1 max-h-[200px] overflow-y-auto">
            {data.trades.map((t: any, i: number) => (
              <div key={i} className="flex items-center gap-3 p-2 bg-black/30 rounded text-xs">
                <span className={`font-bold min-w-[50px] ${t.direction === "LONG" ? "text-green-400" : "text-red-400"}`}>{t.direction}</span>
                <span className="text-slate-400">Entry: ${t.entry}</span>
                <span className="text-slate-400">→ ${t.exit}</span>
                <span className={`font-black ${t.result === "WIN" ? "text-green-400" : "text-red-400"}`}>{t.result}</span>
                <span className={`text-[10px] ${t.pnl_pct >= 0 ? "text-green-500" : "text-red-500"}`}>{t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
