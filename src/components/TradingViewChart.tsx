"use client";

import { useEffect, useRef, memo } from "react";

interface TradingViewChartProps {
  ticker: string;
  timeframe: string;
}

function TradingViewChartInner({ ticker, timeframe }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Map common shorthand tickers to TradingView symbols
  // NOTE: CME futures feeds are restricted on the free embedded widget,
  // so we use CFD/index equivalents that provide full intraday data
  const TV_SYMBOL_MAP: Record<string, string> = {
    // ── Index Futures → CFD/Index equivalents ──
    "NQ": "PEPPERSTONE:NAS100", "NQ1": "PEPPERSTONE:NAS100", "NASDAQ": "PEPPERSTONE:NAS100", "MNQ": "PEPPERSTONE:NAS100",
    "ES": "PEPPERSTONE:US500", "ES1": "PEPPERSTONE:US500", "SPX": "SP:SPX", "MES": "PEPPERSTONE:US500",
    "YM": "PEPPERSTONE:US30", "YM1": "PEPPERSTONE:US30", "DOW": "PEPPERSTONE:US30", "MYM": "PEPPERSTONE:US30",
    "RTY": "PEPPERSTONE:US2000", "RTY1": "PEPPERSTONE:US2000", "M2K": "PEPPERSTONE:US2000",
    // ── Commodities ──
    "CL": "PEPPERSTONE:USOIL", "CL1": "PEPPERSTONE:USOIL", "OIL": "PEPPERSTONE:USOIL",
    "GC": "PEPPERSTONE:XAUUSD", "GC1": "PEPPERSTONE:XAUUSD", "GOLD": "PEPPERSTONE:XAUUSD", "XAUUSD": "PEPPERSTONE:XAUUSD",
    "SI": "PEPPERSTONE:XAGUSD", "SI1": "PEPPERSTONE:XAGUSD", "SILVER": "PEPPERSTONE:XAGUSD",
    "NG": "PEPPERSTONE:NATGAS", "NG1": "PEPPERSTONE:NATGAS",
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
