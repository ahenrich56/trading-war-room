"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { SignalPayload } from "./types";
import { getSessionZones } from "@/lib/sessions";

interface MiniChartProps {
  chartData: any;
  signal: SignalPayload | null;
  ticker: string;
  showSessions?: boolean;
  showBubbles?: boolean;
  showDelta?: boolean;
  showCVD?: boolean;
  showVwapBands?: boolean;
  showVP?: boolean;
}

export function MiniChart({
  chartData, signal, ticker,
  showSessions = false,
  showBubbles = false,
  showDelta = false,
  showCVD = false,
  showVwapBands = false,
  showVP = false,
}: MiniChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<any>(null);
  const prevTickerRef = useRef<string>("");
  const prevTimeframeRef = useRef<string>("");
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

  // ── Draw big-trade bubbles on canvas overlay ──
  const drawBubbles = useCallback(() => {
    const chart = chartRef.current;
    const canvas = canvasRef.current;
    if (!chart || !canvas || !showBubbles || !chartData?.candles?.length) {
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Match canvas size to container
    const rect = canvas.parentElement?.getBoundingClientRect();
    if (rect) {
      canvas.width = rect.width;
      canvas.height = rect.height;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const candles = chartData.candles;
    const deltaMap = new Map<number, any>();
    if (chartData.order_flow?.delta_bars) {
      for (const d of chartData.order_flow.delta_bars) {
        deltaMap.set(d.time, d);
      }
    }

    // Calculate volume stats for threshold
    const volumes = candles.map((c: any) => c.volume).filter((v: number) => v > 0);
    if (volumes.length < 5) return;
    const avgVol = volumes.reduce((a: number, b: number) => a + b, 0) / volumes.length;
    const threshold = avgVol * 1.5; // Show bubbles for 1.5x+ average volume

    const timeScale = chart.timeScale();
    const candleSeries = chart.candleSeries;

    for (const candle of candles) {
      if (candle.volume < threshold) continue;

      const x = timeScale.timeToCoordinate(candle.time);
      if (x === null || x < 0 || x > canvas.width) continue;

      // Position bubble at the body midpoint
      const midPrice = (candle.open + candle.close) / 2;
      const y = candleSeries.priceToCoordinate(midPrice);
      if (y === null || y < 0 || y > canvas.height) continue;

      // Size: proportional to volume magnitude (min 6px, max 28px)
      const ratio = candle.volume / avgVol;
      const radius = Math.min(28, Math.max(6, ratio * 8));

      // Color: buy (green/cyan) vs sell (red/magenta) based on delta
      const delta = deltaMap.get(candle.time);
      const isBuy = delta ? delta.value > 0 : candle.close >= candle.open;

      const color = isBuy ? "rgba(34, 211, 238, 0.55)" : "rgba(192, 38, 211, 0.55)";
      const borderColor = isBuy ? "rgba(34, 211, 238, 0.8)" : "rgba(192, 38, 211, 0.8)";

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = borderColor;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Show volume text inside large bubbles
      if (radius >= 14) {
        ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
        ctx.font = `bold ${Math.max(8, radius * 0.55)}px JetBrains Mono, monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const volText = candle.volume >= 10000 ? `${(candle.volume / 1000).toFixed(0)}K` : `${candle.volume}`;
        ctx.fillText(volText, x, y);
      }
    }
  }, [chartData, showBubbles]);

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
      chart._ofSeries = {}; // order flow series refs
      chartRef.current = chart;

      const handleResize = () => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
          drawBubbles(); // redraw bubbles on resize
        }
      };
      window.addEventListener("resize", handleResize);
      chart.cleanupResize = () => window.removeEventListener("resize", handleResize);

      // Redraw bubbles on scroll/zoom
      chart.timeScale().subscribeVisibleLogicalRangeChange(() => drawBubbles());
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
      time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
    }));
    chart.candleSeries.setData(candleData);

    // ── Volume / Delta bars ──
    const of = chartData.order_flow || {};

    if (showDelta && of.delta_bars?.length) {
      // Delta-colored volume: use actual volume value but color by delta direction
      const deltaMap = new Map<number, any>();
      for (const d of of.delta_bars) deltaMap.set(d.time, d);

      const deltaVolData = uniqueCandles.map((c: any) => {
        const d = deltaMap.get(c.time);
        const isBuy = d ? d.value > 0 : c.close >= c.open;
        return {
          time: c.time,
          value: c.volume,
          color: isBuy ? "rgba(34, 211, 238, 0.35)" : "rgba(192, 38, 211, 0.35)",
        };
      });
      chart.volumeSeries.setData(deltaVolData);
    } else {
      const volData = uniqueCandles.map((c: any) => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
      }));
      chart.volumeSeries.setData(volData);
    }

    // ── CVD line ──
    if (chart._ofSeries.cvd) {
      try { chart.removeSeries(chart._ofSeries.cvd); } catch (e) {}
      chart._ofSeries.cvd = null;
    }
    if (showCVD && of.cvd?.length) {
      const cvdSeries = chart.addLineSeries({
        color: "#f59e0b",
        lineWidth: 1.5,
        priceLineVisible: false,
        priceScaleId: "cvd",
        lastValueVisible: false,
      });
      cvdSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.1, bottom: 0.4 },
        visible: false,
      });
      cvdSeries.setData(of.cvd);
      chart._ofSeries.cvd = cvdSeries;
    }

    // ── VWAP Bands ──
    const vwapBandKeys = ["upper_1", "lower_1", "upper_2", "lower_2"];
    for (const key of vwapBandKeys) {
      if (chart._ofSeries[`vwap_${key}`]) {
        try { chart.removeSeries(chart._ofSeries[`vwap_${key}`]); } catch (e) {}
        chart._ofSeries[`vwap_${key}`] = null;
      }
    }
    if (showVwapBands && of.vwap_bands) {
      const bandDefs = [
        { key: "upper_1", color: "rgba(167, 139, 250, 0.3)", style: 2 },
        { key: "lower_1", color: "rgba(167, 139, 250, 0.3)", style: 2 },
        { key: "upper_2", color: "rgba(239, 68, 68, 0.25)", style: 2 },
        { key: "lower_2", color: "rgba(239, 68, 68, 0.25)", style: 2 },
      ];
      for (const bd of bandDefs) {
        const data = of.vwap_bands[bd.key];
        if (data?.length) {
          const series = chart.addLineSeries({
            color: bd.color,
            lineWidth: 1,
            lineStyle: bd.style,
            priceLineVisible: false,
            lastValueVisible: false,
          });
          series.setData(data);
          chart._ofSeries[`vwap_${bd.key}`] = series;
        }
      }
    }

    // ── Volume Profile: POC / VAH / VAL price lines ──
    if (chart._ofSeries.vpLines) {
      for (const l of chart._ofSeries.vpLines) {
        try { chart.candleSeries.removePriceLine(l); } catch (e) {}
      }
    }
    chart._ofSeries.vpLines = [];

    if (showVP && of.volume_profile) {
      const vp = of.volume_profile;
      if (vp.poc) {
        chart._ofSeries.vpLines.push(chart.candleSeries.createPriceLine({
          price: vp.poc, color: "#f59e0b", lineWidth: 2, lineStyle: 0,
          axisLabelVisible: true, title: "POC",
        }));
      }
      if (vp.vah) {
        chart._ofSeries.vpLines.push(chart.candleSeries.createPriceLine({
          price: vp.vah, color: "rgba(245, 158, 11, 0.4)", lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: "VAH",
        }));
      }
      if (vp.val) {
        chart._ofSeries.vpLines.push(chart.candleSeries.createPriceLine({
          price: vp.val, color: "rgba(245, 158, 11, 0.4)", lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: "VAL",
        }));
      }
    }

    // ── Indicators ──
    if (chartData.indicators?.ema9?.length) chart.ema9Series.setData(chartData.indicators.ema9);
    if (chartData.indicators?.ema21?.length) chart.ema21Series.setData(chartData.indicators.ema21);
    if (chartData.indicators?.vwap?.length) chart.vwapSeries.setData(chartData.indicators.vwap);

    // ── Session zone markers ──
    if (chart._sessionMarkers) {
      try { chart.candleSeries.setMarkers([]); } catch (e) {}
    }
    chart._sessionMarkers = false;

    if (showSessions && candleData.length > 0) {
      const timeframe = chartData.timeframe || "5m";
      const zones = getSessionZones(candleData, timeframe);
      if (zones.length > 0) {
        const markers: any[] = [];
        const sessionColors: Record<string, string> = {
          asian: "#8b5cf6", london: "#3b82f6", newyork: "#f97316",
        };
        for (const zone of zones) {
          if (zone.isKillZone) continue;
          const startCandle = candleData.find((c: any) => c.time >= zone.start);
          if (startCandle) {
            markers.push({
              time: startCandle.time, position: "aboveBar",
              color: sessionColors[zone.type] || "#94a3b8", shape: "square",
              text: zone.type === "asian" ? "ASIA" : zone.type === "london" ? "LDN" : "NY",
            });
          }
        }
        markers.sort((a: any, b: any) => a.time - b.time);
        const dedupedMarkers: any[] = [];
        const seenMarkerTimes = new Set();
        for (const m of markers) {
          if (!seenMarkerTimes.has(m.time)) {
            seenMarkerTimes.add(m.time);
            dedupedMarkers.push(m);
          }
        }
        if (dedupedMarkers.length > 0) {
          chart.candleSeries.setMarkers(dedupedMarkers);
          chart._sessionMarkers = true;
        }
      }
    }

    // ── Scroll control ──
    const currentTimeframe = chartData.timeframe || "";
    if (prevTickerRef.current !== ticker || prevTimeframeRef.current !== currentTimeframe) {
      chart.timeScale().scrollToRealTime();
      prevTickerRef.current = ticker;
      prevTimeframeRef.current = currentTimeframe;
    }

    // ── Signal price lines ──
    if (chart.priceLines) {
      chart.priceLines.forEach((l: any) => {
        try { chart.candleSeries.removePriceLine(l); } catch (e) {}
      });
    }
    chart.priceLines = [];

    if (signal && signal.signal !== "NO_TRADE") {
      const entryColor = signal.signal === "LONG" ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)";

      if (signal.entry_zone && signal.entry_zone.min !== undefined && signal.entry_zone.max !== undefined) {
        chart.priceLines.push(chart.candleSeries.createPriceLine({
          price: signal.entry_zone.min, color: entryColor, lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: "Entry Min",
        }));
        chart.priceLines.push(chart.candleSeries.createPriceLine({
          price: signal.entry_zone.max, color: entryColor, lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: "Entry Max",
        }));
      }

      if (signal.stop_loss !== undefined && signal.stop_loss !== null) {
        chart.priceLines.push(chart.candleSeries.createPriceLine({
          price: signal.stop_loss, color: "#ef4444", lineWidth: 2, lineStyle: 0,
          axisLabelVisible: true, title: "SL",
        }));
      }

      if (Array.isArray(signal.take_profit)) {
        signal.take_profit.forEach((tp) => {
          if (tp && tp.price !== undefined) {
            chart.priceLines.push(chart.candleSeries.createPriceLine({
              price: tp.price, color: "#22c55e", lineWidth: 1, lineStyle: 0,
              axisLabelVisible: true, title: `TP${tp.level}`,
            }));
          }
        });
      }
    }

    // Draw bubbles after chart data is set
    requestAnimationFrame(drawBubbles);

  }, [lwcLoaded, lwcModule, chartData, signal, showSessions, showBubbles, showDelta, showCVD, showVwapBands, showVP, drawBubbles]);

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
          {showCVD && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block"></span> CVD</span>}
        </div>
      </div>
      <div className="relative">
        <div ref={containerRef} className="w-full rounded overflow-hidden" />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 pointer-events-none"
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}
