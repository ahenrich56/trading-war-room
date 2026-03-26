"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

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
    <div className="space-y-4">
      {/* Add ticker + Scan */}
      <div className="space-y-3">
        <div className="flex gap-2">
          <Input
            value={newTicker}
            onChange={e => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Add ticker..."
            className="flex-1 bg-black/50 border-white/20 uppercase text-cyan-400 font-bold text-xs h-8"
            onKeyDown={e => { if (e.key === "Enter") addTicker(); }}
          />
          <Button size="sm" className="bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs h-8 px-3" onClick={addTicker}>
            +
          </Button>
          <Button
            size="sm"
            className="bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs h-8"
            onClick={onScan}
            disabled={isScanning}
          >
            {isScanning ? "SCANNING..." : "SCAN WATCHLIST"}
          </Button>
        </div>
        <div className="flex flex-wrap gap-1">
          {watchlistTickers.map(t => (
            <Badge
              key={t}
              variant="outline"
              className="text-purple-400 border-purple-500/30 bg-purple-500/5 text-[10px] cursor-pointer hover:bg-red-500/20 hover:border-red-500/30 hover:text-red-400 transition-colors"
              onClick={() => setWatchlistTickers(prev => prev.filter(x => x !== t))}
            >
              {t} x
            </Badge>
          ))}
        </div>
      </div>

      {/* Results */}
      {isScanning && (
        <div className="flex items-center justify-center py-12 text-purple-400">
          <div className="text-center">
            <div className="text-2xl mb-2 animate-spin">*</div>
            <div className="text-xs">Scanning {watchlistTickers.length} tickers...</div>
          </div>
        </div>
      )}

      {!isScanning && !watchlistData?.tickers?.length && (
        <div className="text-center text-slate-600 py-12 text-xs">
          Click SCAN WATCHLIST to analyze tickers
        </div>
      )}

      {!isScanning && watchlistData?.tickers?.length > 0 && (
        <div className="space-y-2">
          {watchlistData.best_opportunity && (
            <div className="text-xs text-purple-400 mb-3">
              Best opportunity: <strong className="text-white">{watchlistData.best_opportunity.ticker}</strong> (score: {watchlistData.best_opportunity.score})
            </div>
          )}

          {/* Table header */}
          <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] text-slate-500 font-bold tracking-widest border-b border-white/5">
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
              className="flex items-center gap-3 px-3 py-2.5 bg-black/30 rounded border border-white/5 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all cursor-pointer"
            >
              <span className="text-[10px] text-slate-600 w-6">#{i + 1}</span>
              <div className={`px-1.5 py-0.5 rounded text-[10px] font-black w-16 text-center ${
                t.direction === "LONG" ? "bg-green-500/20 text-green-400" :
                t.direction === "SHORT" ? "bg-red-500/20 text-red-400" :
                "bg-slate-500/20 text-slate-400"
              }`}>
                {t.direction || "NEUTRAL"}
              </div>
              <div className="text-white font-bold text-xs w-14">{t.ticker}</div>
              <div className="text-slate-400 text-xs w-20">${t.price || "-"}</div>
              <div className="flex-1 flex items-center gap-2">
                <div className={`text-sm font-black ${
                  t.score > 15 ? "text-green-400" : t.score < -15 ? "text-red-400" : "text-slate-500"
                }`}>
                  {t.score || 0}
                </div>
                {/* Score bar */}
                <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden max-w-[200px]">
                  <div
                    className={`h-full rounded-full transition-all ${
                      (t.score || 0) > 0 ? "bg-green-500" : (t.score || 0) < 0 ? "bg-red-500" : "bg-slate-600"
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
