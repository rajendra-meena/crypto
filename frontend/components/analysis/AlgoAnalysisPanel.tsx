'use client';

import React from 'react';
import { useTrading } from '@/context/TradingContext';
import { Cpu, AlertTriangle } from 'lucide-react';

export const AlgoAnalysisPanel: React.FC = () => {
  const { indicators, dataSource, deltaConnectionState } = useTrading();

  const getBiasBadge = (bias: string) => {
    switch (bias) {
      case 'BUY':
        return <span className="px-3 py-1 rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-extrabold text-sm">BUY</span>;
      case 'SELL':
        return <span className="px-3 py-1 rounded-md bg-rose-500/20 text-rose-400 border border-rose-500/40 font-extrabold text-sm">SELL</span>;
      default:
        return <span className="px-3 py-1 rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/40 font-extrabold text-sm">WAIT</span>;
    }
  };

  if (!indicators) {
    return (
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 flex flex-col justify-between">
        <div className="text-center text-zinc-400 py-10">
          <Cpu className="h-10 w-10 mx-auto mb-3 opacity-50" />
          <p>Waiting for enough live candles to analyze price action</p>
        </div>
      </div>
    );
  }

  const getDataSourceBadge = () => {
    if (dataSource === 'REAL') {
      return (
        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
          LIVE PRICE ACTION
        </span>
      );
    }

    return (
      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40">
        STALE DATA · ANALYSIS PAUSED
      </span>
    );
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800/60 mb-4">
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-emerald-400" />
            <h3 className="font-bold text-zinc-100 text-sm tracking-wide uppercase">Price Action Engine</h3>
          </div>
          <div className="flex items-center gap-2">
            {getDataSourceBadge()}
            {deltaConnectionState === 'STALE' && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40 text-[10px] font-bold">
                <AlertTriangle className="h-3 w-3" />
                STALE
              </span>
            )}
          </div>
        </div>

        <div className="space-y-2.5 text-xs">
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">Market Trend</span>
            <span className="font-semibold text-zinc-200">{indicators.marketTrend.replace(/_/g, ' ')}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">Market Structure</span>
            <span className="font-semibold text-zinc-200">{indicators.marketStructure.replace(/_/g, ' ')}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">Momentum</span>
            <span className="font-semibold text-zinc-200">{indicators.momentum}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">Volatility</span>
            <span className="font-semibold text-zinc-200">{indicators.volatility}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">Volume Strength</span>
            <span className="font-semibold text-zinc-200">{indicators.volumeStrength}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">Support / Resistance</span>
            <span className="font-mono text-zinc-300">${indicators.support} / ${indicators.resistance}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">RSI (context)</span>
            <span className="font-mono font-bold text-emerald-400">{indicators.rsi}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-zinc-900">
            <span className="text-zinc-400">MACD Histogram (context)</span>
            <span className="font-mono font-bold text-zinc-200">{indicators.macd.histogram}</span>
          </div>
        </div>
      </div>

      <div className="mt-5 p-4 rounded-xl bg-zinc-900/80 border border-zinc-800 flex items-center justify-between">
        <div>
          <div className="text-[11px] text-zinc-400 uppercase font-bold tracking-wider mb-1">Price Action Bias</div>
          {getBiasBadge(indicators.finalBias)}
        </div>
        <div className="text-right">
          <div className="text-[11px] text-zinc-400 uppercase font-bold tracking-wider mb-1">Confidence</div>
          <div className="font-mono text-lg font-extrabold text-emerald-400">{indicators.confidence}%</div>
          <div className="text-[10px] text-zinc-500 mt-1">Calculated from live candle structure</div>
        </div>
      </div>
    </div>
  );
};
