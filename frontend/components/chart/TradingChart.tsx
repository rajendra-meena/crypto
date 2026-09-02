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
    if (!Number.isFinite(candle.open) || !Number.isFinite(candle.high) || !Number.isFinite(candle.low) || !Number.isFinite(candle.close)) continue;
    byTime.set(candle.time, candle);
  }
  return Array.from(byTime.values()).sort((a, b) => a.time - b.time).slice(-100);
}

export const TradingChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState<Timeframe>('1m');

  const { symbol, candles, signals, positions } = useTrading();
  const activePosition = positions.find((position) => position.symbol === symbol);
  const activeSignal = signals.find((signal) => signal.symbol === symbol && (signal.status === 'READY' || signal.status === 'EXECUTED'));

  const tradeLevels = activePosition
    ? {
        label: 'OPEN PAPER POSITION',
        entry: activePosition.entryPrice,
        stopLoss: activePosition.stopLoss,
        target: activePosition.target1,
        riskReward: activeSignal?.riskReward || '--',
        side: activePosition.side,
        status: 'EXECUTED',
      }
    : activeSignal
      ? {
          label: 'BACKEND SIGNAL',
          entry: activeSignal.entry,
          stopLoss: activeSignal.stopLoss,
          target: activeSignal.target1,
          riskReward: activeSignal.riskReward,
          side: activeSignal.side,
          status: activeSignal.status,
        }
      : null;

  const chartCandles = useMemo(() => prepareCandles(candles, activeTimeframe), [candles, activeTimeframe]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#09090b' }, textColor: '#a1a1aa' },
      grid: { vertLines: { color: '#18181b' }, horzLines: { color: '#18181b' } },
      crosshair: {
        vertLine: { color: '#3f3f46', width: 1, style: 2 },
        horzLine: { color: '#3f3f46', width: 1, style: 2 },
      },
      timeScale: { borderColor: '#27272a', timeVisible: true, secondsVisible: false },
      rightPriceScale: { borderColor: '#27272a' },
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
    if (historical.length > 0) chartRef.current?.timeScale().fitContent();
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
              className={`px-2.5 py-1 rounded text-xs font-semibold font-mono transition-all ${activeTimeframe === tf ? 'bg-zinc-700 text-zinc-100' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'}`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {tradeLevels && (
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono bg-zinc-900/60 border border-zinc-800 p-2 rounded-lg">
          <span className="text-zinc-400">{tradeLevels.label}:</span>
          <span className={tradeLevels.side === 'BUY' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{tradeLevels.side}</span>
          <span className="text-zinc-300">Entry: ${tradeLevels.entry}</span>
          <span className="text-rose-400 font-medium">SL: ${tradeLevels.stopLoss}</span>
          <span className="text-emerald-400 font-medium">Target: ${tradeLevels.target}</span>
          <span className="text-zinc-400">R:R: {tradeLevels.riskReward}</span>
          <span className="ml-auto text-zinc-500">{tradeLevels.status}</span>
        </div>
      )}

      <div ref={chartContainerRef} className="w-full rounded-xl overflow-hidden" />
    </div>
  );
};
