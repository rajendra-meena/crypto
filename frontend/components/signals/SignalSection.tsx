'use client';

import React, { useEffect, useMemo, useRef } from 'react';
import { useTrading } from '@/context/TradingContext';
import { ArrowUpRight, ArrowDownRight, Zap } from 'lucide-react';
import { AlgoSignal, Candle } from '@/types/trading';

const roundPrice = (value: number) => {
  if (value < 10) return Number(value.toFixed(4));
  if (value < 100) return Number(value.toFixed(3));
  return Number(value.toFixed(2));
};

const getAnalysisSeries = (candles: Candle[]) => {
  for (const timeframe of ['15m', '5m', '1m']) {
    const series = candles
      .filter((c) => c.timeframe === timeframe)
      .sort((a, b) => a.time - b.time);
    if (series.length >= 20) return { timeframe, series };
  }

  const series = [...candles].sort((a, b) => a.time - b.time);
  return { timeframe: series.at(-1)?.timeframe || '1m', series };
};

export const SignalSection: React.FC = () => {
  const {
    signals,
    takeTrade,
    symbol,
    ticker,
    candles,
    indicators,
    positions,
    executedSignalIds,
    settings,
    canTrade,
  } = useTrading();

  const lastAutoExecutedSignalRef = useRef<string | null>(null);

  const priceActionSignal = useMemo<AlgoSignal | null>(() => {
    if (!indicators || !ticker || ticker.price <= 0 || indicators.finalBias === 'WAIT') return null;

    const symbolCandles = candles.filter((c) => c.symbol === symbol);
    const { timeframe, series } = getAnalysisSeries(symbolCandles);
    const latest = series.at(-1);
    if (!latest) return null;

    const entry = ticker.price;
    const isBuy = indicators.finalBias === 'BUY';

    const structureRisk = isBuy
      ? entry - indicators.support
      : indicators.resistance - entry;
    const minRisk = entry * 0.003;
    const maxRisk = entry * 0.015;
    const risk = Math.min(maxRisk, Math.max(minRisk, structureRisk > 0 ? structureRisk : minRisk));

    const stopLoss = isBuy ? entry - risk : entry + risk;
    const target1 = isBuy ? entry + risk * 1.5 : entry - risk * 1.5;
    const target2 = isBuy ? entry + risk * 2.5 : entry - risk * 2.5;

    const reasonParts = [
      indicators.marketStructure.replace(/_/g, ' '),
      indicators.marketTrend.replace(/_/g, ' '),
      `${indicators.momentum.toLowerCase()} momentum`,
    ];

    return {
      id: `PA-${symbol}-${timeframe}-${latest.time}-${indicators.finalBias}`,
      symbol,
      side: indicators.finalBias,
      timeframe,
      entry: roundPrice(entry),
      stopLoss: roundPrice(stopLoss),
      target1: roundPrice(target1),
      target2: roundPrice(target2),
      riskReward: '1:2.5',
      confidence: indicators.confidence,
      generatedTime: new Date(latest.time).toLocaleTimeString(),
      reason: `Price action: ${reasonParts.join(' · ')}`,
      status: 'READY',
    };
  }, [indicators, ticker, candles, symbol]);

  useEffect(() => {
    if (!priceActionSignal) return;
    if (settings.isLiveMode) return;
    if (!canTrade) return;
    if (executedSignalIds.includes(priceActionSignal.id)) return;
    if (positions.length >= settings.maxConcurrentTrades) return;
    if (positions.some((position) => position.symbol === priceActionSignal.symbol)) return;
    if (lastAutoExecutedSignalRef.current === priceActionSignal.id) return;

    lastAutoExecutedSignalRef.current = priceActionSignal.id;
    takeTrade(priceActionSignal);
  }, [
    priceActionSignal,
    settings.isLiveMode,
    settings.maxConcurrentTrades,
    canTrade,
    positions,
    executedSignalIds,
    takeTrade,
  ]);

  const visibleSignals = useMemo(() => {
    if (!priceActionSignal) return signals;

    const wasExecuted = executedSignalIds.includes(priceActionSignal.id)
      || positions.some((position) => position.signalId === priceActionSignal.id);

    const liveSignal: AlgoSignal = wasExecuted
      ? { ...priceActionSignal, status: 'EXECUTED' }
      : priceActionSignal;

    return [liveSignal, ...signals.filter((signal) => signal.id !== liveSignal.id)].slice(0, 20);
  }, [priceActionSignal, signals, positions, executedSignalIds]);

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-amber-400" />
          <h3 className="font-bold text-zinc-100 text-base">Algo Trading Signals</h3>
        </div>
        <span className="text-xs text-zinc-400">
          {settings.isLiveMode ? 'Live mode · manual execution only' : 'Paper mode · auto execution'}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-400 uppercase font-mono text-[11px]">
              <th className="pb-3 px-3">Coin</th>
              <th className="pb-3 px-3">Action</th>
              <th className="pb-3 px-3">Timeframe</th>
              <th className="pb-3 px-3">Entry</th>
              <th className="pb-3 px-3">Stop Loss</th>
              <th className="pb-3 px-3">Target 1 & 2</th>
              <th className="pb-3 px-3">R:R</th>
              <th className="pb-3 px-3">Confidence</th>
              <th className="pb-3 px-3">Time</th>
              <th className="pb-3 px-3">Reason</th>
              <th className="pb-3 px-3">Status</th>
              <th className="pb-3 px-3 text-right">Execution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 font-mono">
            {visibleSignals.map((sig) => {
              const isBuy = sig.side === 'BUY';
              const isReady = sig.status === 'READY';

              return (
                <tr key={sig.id} className="hover:bg-zinc-900/40 transition">
                  <td className="py-3 px-3 font-sans font-bold text-zinc-200">{sig.symbol}</td>
                  <td className="py-3 px-3">
                    <span
                      className={`inline-flex items-center gap-1 font-bold px-2 py-0.5 rounded text-[11px] ${
                        isBuy ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                      }`}
                    >
                      {isBuy ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                      {sig.side}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-zinc-300">{sig.timeframe}</td>
                  <td className="py-3 px-3 text-zinc-200">${sig.entry}</td>
                  <td className="py-3 px-3 text-rose-400">${sig.stopLoss}</td>
                  <td className="py-3 px-3 text-emerald-400">
                    ${sig.target1} / ${sig.target2}
                  </td>
                  <td className="py-3 px-3 text-zinc-300">{sig.riskReward}</td>
                  <td className="py-3 px-3 font-bold text-zinc-200">{sig.confidence}%</td>
                  <td className="py-3 px-3 text-zinc-400 font-mono text-[11px]">{sig.generatedTime}</td>
                  <td className="py-3 px-3 text-zinc-500 text-[11px] max-w-[220px] truncate" title={sig.reason}>
                    {sig.reason}
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        isReady
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                          : sig.status === 'EXECUTED'
                          ? 'bg-blue-950 text-blue-400 border border-blue-800'
                          : 'bg-zinc-900 text-zinc-400'
                      }`}
                    >
                      {sig.status}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right">
                    {isReady ? (
                      settings.isLiveMode ? (
                        <button
                          onClick={() => takeTrade(sig)}
                          className="px-3 py-1 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold rounded-lg transition-all shadow-md shadow-emerald-500/10 text-xs"
                        >
                          Take Trade
                        </button>
                      ) : canTrade ? (
                        <span className="text-emerald-400 font-sans text-xs">AUTO</span>
                      ) : (
                        <span className="text-amber-400 font-sans text-xs">WAITING</span>
                      )
                    ) : (
                      <span className="text-zinc-600 font-sans text-xs">--</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
