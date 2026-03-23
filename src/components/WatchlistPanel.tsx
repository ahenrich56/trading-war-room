"use client";

export function WatchlistPanel({ data, isScanning, onSelect }: { data: any, isScanning: boolean, onSelect: (t: string) => void }) {
  if (isScanning) {
    return (
      <div className="h-[350px] flex items-center justify-center text-purple-400">
        <div className="text-center">
          <div className="text-3xl mb-2 animate-spin">📡</div>
          <div className="text-sm">Scanning tickers across all indicators...</div>
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
          <div className="text-[10px] mt-1 text-slate-700">Add tickers above, then scan</div>
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
