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

    // Initialize chart if it doesn't exist
    if (!chartRef.current) {
      const chart = lwcModule.createChart(containerRef.current, {
        layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "rgba(255,255,255,0.03)" }, horzLines: { color: "rgba(255,255,255,0.03)" } },
        width: containerRef.current.clientWidth,
        height: 350,
        crosshair: { mode: 0 },
        rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
        timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true, secondsVisible: false },
      });

      chart.candleSeries = chart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderUpColor: "#22c55e",
        borderDownColor: "#ef4444",
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
      });

      chart.volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      chart.volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.85, bottom: 0 },
      });

      chart.ema9Series = chart.addLineSeries({ color: "#67e8f9", lineWidth: 1, priceLineVisible: false });
      chart.ema21Series = chart.addLineSeries({ color: "#fbbf24", lineWidth: 1, priceLineVisible: false });
      chart.vwapSeries = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1, lineStyle: 2, priceLineVisible: false });

      chart.priceLines = [];
      chartRef.current = chart;

      const handleResize = () => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);
      chart.cleanupResize = () => window.removeEventListener("resize", handleResize);
    }

    const chart = chartRef.current;

    // Process and dedup data
    const uniqueCandles: any[] = [];
    const seenTimes = new Set();
    const sortedCandles = [...chartData.candles].sort((a: any, b: any) => a.time - b.time);
    for (const c of sortedCandles) {
      if (!seenTimes.has(c.time)) {
        seenTimes.add(c.time);
        uniqueCandles.push(c);
      }
    }

    const candleData = uniqueCandles.map((c: any) => ({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    // Note: If using `setData()`, it replaces the whole array. If it's the exact same data, it doesn't flicker.
    // However, if initial zoom was changed by user, setData() might reset the zoom.
    // To be perfectly smooth, setData is usually fine as long as there's a small logical range change handling.
    // For now, setData() is what we used before and is required if we are completely replacing historical data points.
    chart.candleSeries.setData(candleData);

    const volData = uniqueCandles.map((c: any) => ({
      time: c.time,
      value: c.volume,
      color: c.close >= c.open ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
    }));
    chart.volumeSeries.setData(volData);

    if (chartData.indicators?.ema9?.length) chart.ema9Series.setData(chartData.indicators.ema9);
    if (chartData.indicators?.ema21?.length) chart.ema21Series.setData(chartData.indicators.ema21);
    if (chartData.indicators?.vwap?.length) chart.vwapSeries.setData(chartData.indicators.vwap);

    // Update signal lines
    if (chart.priceLines) {
      chart.priceLines.forEach((l: any) => {
        try { chart.candleSeries.removePriceLine(l); } catch(e){}
      });
    }
    chart.priceLines = [];

    if (signal && signal.signal !== "NO_TRADE") {
      const entryColor = signal.signal === "LONG" ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)";
      
      if (signal.entry_zone && signal.entry_zone.min !== undefined && signal.entry_zone.max !== undefined) {
        chart.priceLines.push(chart.candleSeries.createPriceLine({
          price: signal.entry_zone.min,
          color: entryColor,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "Entry Min",
        }));
        chart.priceLines.push(chart.candleSeries.createPriceLine({
          price: signal.entry_zone.max,
          color: entryColor,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "Entry Max",
        }));
      }
      
      if (signal.stop_loss !== undefined && signal.stop_loss !== null) {
        chart.priceLines.push(chart.candleSeries.createPriceLine({
          price: signal.stop_loss,
          color: "#ef4444",
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: "SL",
        }));
      }
      
      if (Array.isArray(signal.take_profit)) {
        signal.take_profit.forEach((tp) => {
          if (tp && tp.price !== undefined) {
            chart.priceLines.push(chart.candleSeries.createPriceLine({
              price: tp.price,
              color: "#22c55e",
              lineWidth: 1,
              lineStyle: 0,
              axisLabelVisible: true,
              title: `TP${tp.level}`,
            }));
          }
        });
      }
    }

  }, [lwcLoaded, lwcModule, chartData, signal]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      if (chartRef.current) {
        if (chartRef.current.cleanupResize) chartRef.current.cleanupResize();
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, []);

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
