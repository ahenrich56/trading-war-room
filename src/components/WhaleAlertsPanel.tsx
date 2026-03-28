"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, TrendingUp, TrendingDown, Activity } from "lucide-react";

interface WhaleAlert {
  alert_type: string;
  ticker: string;
  amount_usd: number;
  magnitude: number;
  confidence: number;
  timestamp: number;
  details: {
    magnitude: string;
    latest_volume: number;
    avg_volume: number;
    price_change_pct: string;
    label: string;
  };
}

export function WhaleAlertsPanel({ alerts }: { alerts: WhaleAlert[] }) {
  if (!alerts || alerts.length === 0) return null;

  const formatCurrency = (val: number) => {
    if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`;
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
    return `$${val.toFixed(0)}`;
  };

  return (
    <Card className="border-cyan-500/20 bg-gradient-to-r from-cyan-500/5 to-transparent backdrop-blur-sm shadow-[0_0_20px_rgba(6,182,212,0.1)] mb-6 overflow-hidden">
      <CardHeader className="py-3 px-4 border-b border-white/5 flex flex-row items-center justify-between">
        <CardTitle className="text-xs font-bold tracking-wider text-cyan-400 font-mono flex items-center gap-2">
          <Activity className="h-4 w-4 animate-pulse" />
          WHALE FLOW ALERTS
        </CardTitle>
        <Badge variant="outline" className="text-[10px] border-cyan-500/30 text-cyan-500/70 bg-cyan-500/5">
          {alerts.length} detected
        </Badge>
      </CardHeader>
      <CardContent className="p-3 grid gap-2 max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        {alerts.map((alert, i) => {
          const isBuy = alert.alert_type === "buy_wall";
          const isSell = alert.alert_type === "panic_distribution";
          
          return (
            <div key={i} className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3 rounded-xl border border-white/8 bg-white/[0.02] backdrop-blur-sm hover:border-white/12 transition-all gap-3 group">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-xl ${
                  isBuy ? "bg-emerald-500/15 text-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.1)]" : 
                  isSell ? "bg-rose-500/15 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.1)]" : 
                  "bg-cyan-500/15 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.1)]"
                }`}>
                  {isBuy ? <TrendingUp className="h-4 w-4" /> : isSell ? <TrendingDown className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                </div>
                <div>
                  <div className="font-bold text-slate-200 text-sm group-hover:text-white transition-colors">
                    {alert.details.label}
                  </div>
                  <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                    <Badge variant="outline" className="border-white/10 text-cyan-300 font-mono px-1.5 text-[10px]">
                      {alert.details.magnitude}
                    </Badge>
                    <span className={`font-bold ${isBuy ? "text-emerald-400" : isSell ? "text-rose-400" : "text-slate-300"}`}>
                      {alert.details.price_change_pct}
                    </span>
                  </div>
                </div>
              </div>
              
              <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto mt-2 sm:mt-0 pt-2 sm:pt-0 border-t border-white/5 sm:border-t-0">
                <span className="text-slate-200 font-mono text-sm font-bold">{formatCurrency(alert.amount_usd)}</span>
                <span className="text-[10px] text-slate-600">Conf: {alert.confidence.toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
