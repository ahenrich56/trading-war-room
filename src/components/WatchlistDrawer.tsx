"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

interface WatchlistDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  watchlistTickers: string[];
  setWatchlistTickers: React.Dispatch<React.SetStateAction<string[]>>;
  watchlistData: any;
  isScanning: boolean;
  onScan: () => void;
  onSelect: (ticker: string) => void;
  newTicker: string;
  setNewTicker: (v: string) => void;
}

export function WatchlistDrawer({
  isOpen,
  onClose,
  watchlistTickers,
  setWatchlistTickers,
  watchlistData,
  isScanning,
  onScan,
  onSelect,
  newTicker,
  setNewTicker,
}: WatchlistDrawerProps) {
  if (!isOpen) return null;

  const addTicker = () => {
    if (newTicker && !watchlistTickers.includes(newTicker)) {
      setWatchlistTickers(prev => [...prev, newTicker]);
      setNewTicker("");
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[340px] bg-[#0A0A15] border-l border-white/10 z-50 flex flex-col animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <span className="text-xs font-bold tracking-widest text-white">WATCHLIST</span>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Add ticker + Scan */}
        <div className="px-4 py-3 border-b border-white/5 space-y-2">
          <div className="flex gap-1">
            <Input
              value={newTicker}
              onChange={e => setNewTicker(e.target.value.toUpperCase())}
              placeholder="Add ticker..."
              className="flex-1 bg-black/50 border-white/20 uppercase text-cyan-400 font-bold text-xs h-8"
              onKeyDown={e => { if (e.key === "Enter") addTicker(); }}
            />
            <Button size="sm" className="bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs h-8 px-2" onClick={addTicker}>
              +
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
          <Button
            size="sm"
            className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs h-8"
            onClick={onScan}
            disabled={isScanning}
          >
            {isScanning ? "SCANNING..." : "SCAN WATCHLIST"}
          </Button>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {isScanning && (
            <div className="flex items-center justify-center py-8 text-purple-400">
              <div className="text-center">
                <div className="text-2xl mb-2 animate-spin">*</div>
                <div className="text-xs">Scanning...</div>
              </div>
            </div>
          )}

          {!isScanning && !watchlistData?.tickers?.length && (
            <div className="text-center text-slate-600 py-8 text-xs">
              Click SCAN to analyze tickers
            </div>
          )}

          {!isScanning && watchlistData?.tickers?.length > 0 && (
            <div className="space-y-1.5">
              {watchlistData.best_opportunity && (
                <div className="text-[10px] text-purple-400 mb-2">
                  Best: <strong>{watchlistData.best_opportunity.ticker}</strong> (score: {watchlistData.best_opportunity.score})
                </div>
              )}
              {watchlistData.tickers.map((t: any, i: number) => (
                <div
                  key={i}
                  onClick={() => { if (!t.error) { onSelect(t.ticker); onClose(); } }}
                  className="flex items-center gap-2 p-2 bg-black/40 rounded border border-white/5 hover:border-white/20 transition-all cursor-pointer"
                >
                  <span className="text-[10px] text-slate-600 w-4">#{i + 1}</span>
                  <div className={`px-1.5 py-0.5 rounded text-[10px] font-black min-w-[45px] text-center ${
                    t.direction === "LONG" ? "bg-green-500/20 text-green-400" :
                    t.direction === "SHORT" ? "bg-red-500/20 text-red-400" :
                    "bg-slate-500/20 text-slate-400"
                  }`}>
                    {t.direction || "ERR"}
                  </div>
                  <div className="text-white font-bold text-xs">{t.ticker}</div>
                  <div className="text-slate-400 text-[10px]">${t.price || "-"}</div>
                  <div className={`ml-auto text-xs font-bold ${
                    t.score > 15 ? "text-green-400" : t.score < -15 ? "text-red-400" : "text-slate-500"
                  }`}>
                    {t.score || 0}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
