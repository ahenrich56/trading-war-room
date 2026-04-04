"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Radar, Search, X } from "lucide-react";

interface WatchlistPageProps {
  watchlistTickers: string[];
  setWatchlistTickers: React.Dispatch<React.SetStateAction<string[]>>;
  watchlistData: any;
  isScanning: boolean;
  onScan: () => void;
  onSelect: (ticker: string) => void;
  newTicker: string;
  setNewTicker: (v: string) => void;
}

export function WatchlistPage({
  watchlistTickers,
  setWatchlistTickers,
  watchlistData,
  isScanning,
  onScan,
  onSelect,
  newTicker,
  setNewTicker,
}: WatchlistPageProps) {
  const addTicker = () => {
    if (newTicker && !watchlistTickers.includes(newTicker)) {
      setWatchlistTickers(prev => [...prev, newTicker]);
      setNewTicker("");
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-white tracking-wide">Watchlist</h2>
          <p className="text-[10px] text-slate-600 mt-0.5">{watchlistTickers.length} instruments tracked</p>
        </div>
        <Button
          size="sm"
          className="bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-500 hover:to-violet-500 text-white font-bold text-xs h-8 px-4 border border-purple-500/30 shadow-[0_0_12px_rgba(168,85,247,0.2)]"
          onClick={onScan}
          disabled={isScanning}
        >
          {isScanning ? (
            <span className="flex items-center gap-1.5"><Radar className="h-3.5 w-3.5 animate-spin [animation-duration:2s]" /> SCANNING...</span>
          ) : (
            <span className="flex items-center gap-1.5"><Search className="h-3.5 w-3.5" /> SCAN ALL</span>
          )}
        </Button>
      </div>

      {/* Add ticker */}
      <div className="space-y-3">
        <div className="flex gap-2">
          <Input
            value={newTicker}
            onChange={e => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Add ticker..."
            className="flex-1 bg-white/[0.04] border-white/[0.08] uppercase text-cyan-400 font-bold text-xs h-8 focus:border-purple-500/40 focus:ring-purple-500/20 placeholder:text-slate-600"
            onKeyDown={e => { if (e.key === "Enter") addTicker(); }}
          />
          <Button
            size="sm"
            className="bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] text-white font-bold text-xs h-8 w-8 p-0"
            onClick={addTicker}
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {watchlistTickers.map(t => (
            <Badge
              key={t}
              variant="outline"
              className="text-purple-400 border-purple-500/20 bg-purple-500/5 text-[10px] cursor-pointer hover:bg-red-500/10 hover:border-red-500/20 hover:text-red-400 transition-all group px-2 py-0.5"
              onClick={() => setWatchlistTickers(prev => prev.filter(x => x !== t))}
            >
              {t} <X className="h-2.5 w-2.5 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
            </Badge>
          ))}
        </div>
      </div>

      {/* Results */}
      {isScanning && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center space-y-3">
            <div className="relative mx-auto w-12 h-12">
              <div className="absolute inset-0 rounded-full border-2 border-purple-500/20 animate-ping" />
              <div className="absolute inset-0 flex items-center justify-center">
                <Radar className="h-6 w-6 text-purple-400 animate-spin [animation-duration:3s]" />
              </div>
            </div>
            <div className="text-xs text-purple-400 font-medium">Scanning {watchlistTickers.length} instruments...</div>
          </div>
        </div>
      )}

      {!isScanning && !watchlistData?.tickers?.length && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center space-y-3">
            <div className="mx-auto w-14 h-14 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
              <Search className="h-6 w-6 text-slate-600" />
            </div>
            <div>
              <div className="text-sm text-slate-500 font-medium">No scan results</div>
              <div className="text-[10px] mt-1 text-slate-700">Click <span className="text-purple-400 font-bold">SCAN ALL</span> to analyze your watchlist</div>
            </div>
          </div>
        </div>
      )}

      {!isScanning && watchlistData?.tickers?.length > 0 && (
        <div className="space-y-2">
          {watchlistData.best_opportunity && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-500/5 border border-purple-500/15 text-xs">
              <span className="text-purple-400 font-semibold">Best opportunity:</span>
              <span className="text-white font-bold">{watchlistData.best_opportunity.ticker}</span>
              <span className="text-slate-500">(score: {watchlistData.best_opportunity.score})</span>
            </div>
          )}

          {/* Table header */}
          <div className="flex items-center gap-3 px-3 py-2 text-[10px] text-slate-500 font-bold tracking-widest border-b border-white/[0.04]">
            <span className="w-6">#</span>
            <span className="w-16">SIGNAL</span>
            <span className="w-14">TICKER</span>
            <span className="w-20">PRICE</span>
            <span className="flex-1">SCORE</span>
            <span className="w-32 text-right">INDICATORS</span>
          </div>

          {watchlistData.tickers.map((t: any, i: number) => (
            <div
              key={i}
              onClick={() => { if (!t.error) onSelect(t.ticker); }}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:border-purple-500/25 hover:bg-purple-500/[0.03] transition-all cursor-pointer group"
              style={{ backdropFilter: "blur(4px)" }}
            >
              <span className="text-[10px] text-slate-600 w-6 font-mono">{i + 1}</span>
              <div className={`px-1.5 py-0.5 rounded text-[10px] font-black w-16 text-center ${
                t.direction === "LONG" ? "bg-green-500/15 text-green-400 border border-green-500/20" :
                t.direction === "SHORT" ? "bg-red-500/15 text-red-400 border border-red-500/20" :
                "bg-slate-500/15 text-slate-400 border border-slate-500/20"
              }`}>
                {t.direction || "NEUTRAL"}
              </div>
              <div className="text-white font-bold text-xs w-14 group-hover:text-purple-300 transition-colors">{t.ticker}</div>
              <div className="text-slate-400 text-xs w-20 tabular-nums">${t.price || "-"}</div>
              <div className="flex-1 flex items-center gap-2">
                <div className={`text-sm font-black tabular-nums ${
                  t.score > 15 ? "text-green-400" : t.score < -15 ? "text-red-400" : "text-slate-500"
                }`}>
                  {t.score || 0}
                </div>
                <div className="flex-1 h-1.5 bg-white/[0.04] rounded-full overflow-hidden max-w-[200px]">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      (t.score || 0) > 0 ? "bg-green-500/70" : (t.score || 0) < 0 ? "bg-red-500/70" : "bg-slate-600"
                    }`}
                    style={{ width: `${Math.min(Math.abs(t.score || 0), 100)}%` }}
                  />
                </div>
              </div>
              <div className="text-[10px] text-slate-500 w-32 text-right font-mono">
                {t.rsi ? `RSI:${t.rsi.toFixed(1)}` : ""}
                {t.adx ? ` ADX:${t.adx.toFixed(1)}` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
