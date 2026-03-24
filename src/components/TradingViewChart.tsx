"use client";

import { useEffect, useRef, memo } from "react";

interface TradingViewChartProps {
  ticker: string;
  timeframe: string;
}

function TradingViewChartInner({ ticker, timeframe }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Map common shorthand tickers to TradingView exchange-prefixed symbols
  // Futures need the exchange prefix + continuous contract suffix for intraday data
  const TV_SYMBOL_MAP: Record<string, string> = {
    // ── Index Futures ──
    "NQ": "CME_MINI:NQ1!", "NQ1": "CME_MINI:NQ1!", "NASDAQ": "CME_MINI:NQ1!", "MNQ": "CME_MINI:MNQ1!",
    "ES": "CME_MINI:ES1!", "ES1": "CME_MINI:ES1!", "SPX": "CME_MINI:ES1!", "MES": "CME_MINI:MES1!",
    "YM": "CBOT_MINI:YM1!", "YM1": "CBOT_MINI:YM1!", "DOW": "CBOT_MINI:YM1!", "MYM": "CBOT_MINI:MYM1!",
    "RTY": "CME_MINI:RTY1!", "RTY1": "CME_MINI:RTY1!", "M2K": "CME_MINI:M2K1!",
    // ── Commodities ──
    "CL": "NYMEX:CL1!", "CL1": "NYMEX:CL1!", "OIL": "NYMEX:CL1!",
    "GC": "COMEX:GC1!", "GC1": "COMEX:GC1!", "GOLD": "COMEX:GC1!", "XAUUSD": "OANDA:XAUUSD",
    "SI": "COMEX:SI1!", "SI1": "COMEX:SI1!", "SILVER": "COMEX:SI1!",
    "NG": "NYMEX:NG1!", "NG1": "NYMEX:NG1!",
    // ── Bonds ──
    "ZB": "CBOT:ZB1!", "ZB1": "CBOT:ZB1!", "ZN": "CBOT:ZN1!", "ZN1": "CBOT:ZN1!",
    // ── Crypto ──
    "BTCUSD": "COINBASE:BTCUSD", "BTC": "COINBASE:BTCUSD",
    "ETHUSD": "COINBASE:ETHUSD", "ETH": "COINBASE:ETHUSD",
    "SOLUSD": "COINBASE:SOLUSD", "SOL": "COINBASE:SOLUSD",
    // ── Forex ──
    "DXY": "TVC:DXY",
    "EURUSD": "FX:EURUSD", "GBPUSD": "FX:GBPUSD", "USDJPY": "FX:USDJPY",
  };

  const tvSymbol = TV_SYMBOL_MAP[ticker.toUpperCase()] || ticker;

  // Map our timeframes to TradingView intervals
  const tvInterval = (() => {
    switch (timeframe) {
      case "1m": return "1";
      case "5m": return "5";
      case "15m": return "15";
      case "1h": return "60";
      case "4h": return "240";
      case "1d": return "D";
      default: return "5";
    }
  })();

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear previous widget
    containerRef.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: tvSymbol,
      interval: tvInterval,
      timezone: "Etc/UTC",
      theme: "dark",
      style: "1",
      locale: "en",
      backgroundColor: "rgba(5, 5, 10, 1)",
      gridColor: "rgba(255, 255, 255, 0.03)",
      hide_top_toolbar: false,
      hide_legend: false,
      allow_symbol_change: true,
      save_image: true,
      calendar: false,
      hide_volume: false,
      support_host: "https://www.tradingview.com",
      studies: [
        "STD;EMA",
        "STD;VWAP"
      ],
      overrides: {
        "mainSeriesProperties.candleStyle.upColor": "#22c55e",
        "mainSeriesProperties.candleStyle.downColor": "#ef4444",
        "mainSeriesProperties.candleStyle.borderUpColor": "#22c55e",
        "mainSeriesProperties.candleStyle.borderDownColor": "#ef4444",
        "mainSeriesProperties.candleStyle.wickUpColor": "#22c55e",
        "mainSeriesProperties.candleStyle.wickDownColor": "#ef4444",
      },
    });

    containerRef.current.appendChild(script);
  }, [tvSymbol, tvInterval]);

  return (
    <div className="tradingview-widget-container w-full" style={{ height: "500px" }}>
      <div ref={containerRef} className="tradingview-widget-container__widget w-full h-full" />
    </div>
  );
}

export const TradingViewChart = memo(TradingViewChartInner);
