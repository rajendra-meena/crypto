'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi } from 'lightweight-charts';
import { useTrading } from '@/context/TradingContext';
import { Candle } from '@/types/trading';

const timeframes = ['1m', '5m', '15m', '1H', '4H'] as const;
type Timeframe = (typeof timeframes)[number];

function prepareCandles(candles: Candle[], timeframe: Timeframe) {
  const byTime = new Map<number, Candle>();

  for (const candle of candles) {
    if (candle.timeframe !== timeframe) continue;
    if (!Number.isFinite(candle.time)) continue;
    if (!Number.isFinite(candle.open) || !Number.isFinite(candle.high) ||
        !Number.isFinite(candle.low) || !Number.isFinite(candle.close)) continue;

    // The backend snapshot can contain the same candle more than once
    // (historical + current candle). Keep the latest version for each timestamp.
    byTime.set(candle.time, candle);
  }

  return Array.from(byTime.values())
    .sort((a, b) => a.time - b.time)
    .slice(-100);
}

export const TradingChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState<Timeframe>('1m');

  const { symbol, candles, signals } = useTrading();
  const activeSignal = signals.find((s) => s.symbol === symbol && s.status === 'READY');

  const chartCandles = useMemo(
    () => prepareCandles(candles, activeTimeframe),
    [candles, activeTimeframe]
  );

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#09090b' },
        textColor: '#a1a1aa',
      },
      grid: {
        vertLines: { color: '#18181b' },
        horzLines: { color: '#18181b' },
      },
      crosshair: {
        vertLine: { color: '#3f3f46', width: 1, style: 2 },
        horzLine: { color: '#3f3f46', width: 1, style: 2 },
      },
      timeScale: {
        borderColor: '#27272a',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#27272a',
      },
      width: chartContainerRef.current.clientWidth,
      height: 420,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#f43f5e',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#f43f5e',
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      seriesRef.current = null;
      chartRef.current = null;
      chart.remove();
    };
  }, [symbol]);

  // lightweight-charts requires strictly ascending, unique timestamps.
  // Rebuild the visible series from the normalized candle set whenever data,
  // symbol, or timeframe changes. This also makes symbol switching safe.
  useEffect(() => {
    if (!seriesRef.current) return;

    const historical = chartCandles.map((c) => ({
      time: (c.time / 1000) as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    seriesRef.current.setData(historical as any);

    if (historical.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [chartCandles, symbol, activeTimeframe]);

  const lastCandle = chartCandles[chartCandles.length - 1];

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-zinc-800/60">
        <div className="flex items-center gap-3">
          <div className="flex items-baseline gap-2">
            <h2 className="text-xl font-extrabold text-zinc-100">{symbol}</h2>
            <span className="text-xs text-zinc-400 font-mono">PERPETUAL</span>
          </div>
          <div className="font-mono text-lg font-bold text-zinc-200">
            ${lastCandle?.close.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '0.00'}
          </div>
        </div>

        <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-lg border border-zinc-800">
          {timeframes.map((tf) => (
            <button
              key={tf}
              type="button"
              onClick={() => setActiveTimeframe(tf)}
              className={`px-2.5 py-1 rounded text-xs font-semibold font-mono transition-all ${
                activeTimeframe === tf
                  ? 'bg-zinc-700 text-zinc-100'
                  : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {activeSignal && (
        <div className="flex flex-wrap gap-2 text-xs font-mono bg-zinc-900/60 border border-zinc-800 p-2 rounded-lg">
          <span className="text-zinc-400">Signal Targets:</span>
          <span className="text-emerald-400 font-medium">TP1: ${activeSignal.target1}</span>
          <span className="text-emerald-500 font-medium">TP2: ${activeSignal.target2}</span>
          <span className="text-rose-400 font-medium">SL: ${activeSignal.stopLoss}</span>
          <span className="text-zinc-400">R:R: {activeSignal.riskReward}</span>
        </div>
      )}

      <div ref={chartContainerRef} className="w-full rounded-xl overflow-hidden" />
    </div>
  );
};