"use client";

import { useEffect, useRef, useState, memo } from "react";
import { createChart, IChartApi, ISeriesApi, LineStyle, CandlestickSeries } from "lightweight-charts";

interface TradingViewChartProps {
  ticker: string;
  timeframe: string;
  signal?: any;
}

function TradingViewChartInner({ ticker, timeframe, signal }: TradingViewChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<any>(null);
  const [dataLoaded, setDataLoaded] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Initialize chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: "solid", color: "rgba(5, 5, 10, 1)" },
        textColor: "#D1D5DB",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.03)" },
        horzLines: { color: "rgba(255, 255, 255, 0.03)" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderVisible: false,
      },
      rightPriceScale: {
        borderVisible: false,
      },
      crosshair: {
        mode: 0,
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  // Fetch data
  useEffect(() => {
    if (!seriesRef.current) return;
    setDataLoaded(false);
    
    let isMounted = true;

    async function fetchData() {
      try {
        const res = await fetch("/api/chart-data", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker, timeframe })
        });
        const json = await res.json();
        if (isMounted && json.candles && json.candles.length > 0) {
          // ensure data is sorted by time and unique
          const sorted = [...json.candles].sort((a: any, b: any) => a.time - b.time);
          
          // Lightweight charts requires strictly distinct increasing time values
          const uniqueCandles = [];
          const seenTimes = new Set();
          for (const c of sorted) {
            if (!seenTimes.has(c.time)) {
              seenTimes.add(c.time);
              uniqueCandles.push(c);
            }
          }
          
          seriesRef.current?.setData(uniqueCandles);
          setDataLoaded(true);
        }
      } catch (e) {
        console.error("Failed to load chart data:", e);
      }
    }

    fetchData();
    // Poll every 10 seconds for real-time updates
    const interval = setInterval(fetchData, 10000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [ticker, timeframe]);

  // Set Entry, SL, TP lines
  const entryLineRef = useRef<any>(null);
  const slLineRef = useRef<any>(null);
  const tp1LineRef = useRef<any>(null);
  const tp2LineRef = useRef<any>(null);

  useEffect(() => {
    if (!seriesRef.current || !dataLoaded || !signal) return;

    // Clear old lines
    if (entryLineRef.current) seriesRef.current.removePriceLine(entryLineRef.current);
    if (slLineRef.current) seriesRef.current.removePriceLine(slLineRef.current);
    if (tp1LineRef.current) seriesRef.current.removePriceLine(tp1LineRef.current);
    if (tp2LineRef.current) seriesRef.current.removePriceLine(tp2LineRef.current);

    // Don't draw if the active signal is for a different ticker than the chart is currently showing
    if (signal.ticker?.toUpperCase() !== ticker.toUpperCase()) return;

    const sigDir = signal.signal;
    if (sigDir === "NO_TRADE" || !signal.entry_zone) return;

    const entryMid = (signal.entry_zone.min + signal.entry_zone.max) / 2;

    entryLineRef.current = seriesRef.current.createPriceLine({
      price: entryMid || signal.entry_zone.max,
      color: "#06b6d4", // Cyan
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "ENTRY",
    });

    if (signal.stop_loss) {
      slLineRef.current = seriesRef.current.createPriceLine({
        price: signal.stop_loss,
        color: "#ef4444", // Red
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: "SL",
      });
    }

    if (signal.take_profit && signal.take_profit.length > 0) {
      tp1LineRef.current = seriesRef.current.createPriceLine({
        price: signal.take_profit[0],
        color: "#22c55e", // Green
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: "TP1",
      });

      if (signal.take_profit.length > 1) {
        tp2LineRef.current = seriesRef.current.createPriceLine({
          price: signal.take_profit[1],
          color: "#22c55e", 
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "TP2",
        });
      }
    }
  }, [signal, dataLoaded, ticker]);

  return (
    <div className="w-full relative" style={{ height: "500px" }}>
      {!dataLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10 transition-opacity">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin"></div>
            <span className="text-cyan-500 font-mono text-sm uppercase tracking-widest">Loading Live Data...</span>
          </div>
        </div>
      )}
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
}

export const TradingViewChart = memo(TradingViewChartInner);
