"use client";

import { useEffect, useRef, memo } from "react";

interface TradingViewChartProps {
  ticker: string;
  timeframe: string;
}

function TradingViewChartInner({ ticker, timeframe }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

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
      symbol: ticker,
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
  }, [ticker, tvInterval]);

  return (
    <div className="tradingview-widget-container w-full" style={{ height: "500px" }}>
      <div ref={containerRef} className="tradingview-widget-container__widget w-full h-full" />
    </div>
  );
}

export const TradingViewChart = memo(TradingViewChartInner);
