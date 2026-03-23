"use client";

import { useRef, useState, useEffect } from "react";
import { SignalPayload } from "./types";

export function MiniChart({ chartData, signal, ticker }: { chartData: any, signal: SignalPayload | null, ticker: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const [lwcLoaded, setLwcLoaded] = useState(false);
  const [lwcModule, setLwcModule] = useState<any>(null);

  // Load LWC library dynamically
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js";
    script.async = true;
    script.onload = () => {
      setLwcLoaded(true);
      setLwcModule((window as any).LightweightCharts);
    };
    document.head.appendChild(script);
    return () => { document.head.removeChild(script); };
  }, []);

  // Render chart when data arrives
  useEffect(() => {
    if (!lwcLoaded || !lwcModule || !containerRef.current || !chartData?.candles?.length) return;

    // Clear previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = lwcModule.createChart(containerRef.current, {
      layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "rgba(255,255,255,0.03)" }, horzLines: { color: "rgba(255,255,255,0.03)" } },
      width: containerRef.current.clientWidth,
      height: 350,
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true, secondsVisible: false },
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    const candleData = chartData.candles.map((c: any) => ({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeries.setData(candleData);

    // Volume
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    const volData = chartData.candles.map((c: any) => ({
      time: c.time,
      value: c.volume,
      color: c.close >= c.open ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
    }));
    volumeSeries.setData(volData);

    // EMA 9 overlay
    if (chartData.indicators?.ema9?.length) {
      const ema9Series = chart.addLineSeries({ color: "#67e8f9", lineWidth: 1, priceLineVisible: false });
      ema9Series.setData(chartData.indicators.ema9);
    }

    // EMA 21 overlay
    if (chartData.indicators?.ema21?.length) {
      const ema21Series = chart.addLineSeries({ color: "#fbbf24", lineWidth: 1, priceLineVisible: false });
      ema21Series.setData(chartData.indicators.ema21);
    }

    // VWAP overlay
    if (chartData.indicators?.vwap?.length) {
      const vwapSeries = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1, lineStyle: 2, priceLineVisible: false });
      vwapSeries.setData(chartData.indicators.vwap);
    }

    // Signal levels (entry zone, SL, TP)
    if (signal && signal.signal !== "NO_TRADE") {
      const entryColor = signal.signal === "LONG" ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)";
      
      candleSeries.createPriceLine({
        price: signal.entry_zone.min,
        color: entryColor,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Entry Min",
      });
      candleSeries.createPriceLine({
        price: signal.entry_zone.max,
        color: entryColor,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Entry Max",
      });
      candleSeries.createPriceLine({
        price: signal.stop_loss,
        color: "#ef4444",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "SL",
      });
      signal.take_profit.forEach((tp) => {
        candleSeries.createPriceLine({
          price: tp.price,
          color: "#22c55e",
          lineWidth: 1,
          lineStyle: 0,
          axisLabelVisible: true,
          title: `TP${tp.level}`,
        });
      });
    }

    chart.timeScale().fitContent();
    chartRef.current = chart;

    // Responsive
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [lwcLoaded, lwcModule, chartData, signal]);

  if (!chartData?.candles?.length) {
    return (
      <div className="h-[350px] flex items-center justify-center text-slate-600">
        <div className="text-center">
          <div className="text-3xl mb-2">📊</div>
          <div className="text-sm">Run an analysis to load chart data</div>
          <div className="text-[10px] mt-1 text-slate-700">{ticker} • With EMA 9/21, VWAP overlays & signal levels</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-white font-bold">{chartData.ticker || ticker}</span>
        <span className="text-[10px] text-slate-600">{chartData.symbol}</span>
        <div className="flex gap-3 ml-auto text-[10px]">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-cyan-400 inline-block"></span> EMA 9</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-yellow-400 inline-block"></span> EMA 21</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-purple-400 inline-block" style={{borderTop: "1px dashed"}}></span> VWAP</span>
        </div>
      </div>
      <div ref={containerRef} className="w-full rounded overflow-hidden" />
    </div>
  );
}
