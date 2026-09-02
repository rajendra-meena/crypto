'use client';

import React from 'react';
import { TrendingDown, TrendingUp } from 'lucide-react';
import { useTrading } from '@/context/TradingContext';

export const Watchlist: React.FC = () => {
  const { watchlist, symbol, setSymbol } = useTrading();

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {watchlist.map((coin) => {
        const isSelected = symbol === coin.symbol;
        const isPos = coin.change24h >= 0;
        const statusClass = coin.signalState === 'READY'
          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
          : coin.signalState === 'EXECUTED'
            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
            : coin.signalState === 'BLOCKED'
              ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
              : coin.signalState === 'FILTERED'
                ? 'bg-zinc-700/40 text-zinc-400 border border-zinc-700'
                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30';

        return (
          <div
            key={coin.symbol}
            onClick={() => setSymbol(coin.symbol)}
            className={`cursor-pointer rounded-xl p-3.5 border transition-all duration-200 ${
              isSelected
                ? 'bg-zinc-900/90 border-emerald-500/50 shadow-md shadow-emerald-500/5 ring-1 ring-emerald-500/30'
                : 'bg-zinc-950/60 border-zinc-800/80 hover:bg-zinc-900/50 hover:border-zinc-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-bold text-sm text-zinc-200">{coin.symbol.replace('USDT', '')}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${statusClass}`}>
                {coin.signalState}
              </span>
            </div>

            <div className="flex items-baseline justify-between">
              <span className="font-mono text-base font-semibold text-zinc-100">
                ${coin.price > 1 ? coin.price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : coin.price.toFixed(4)}
              </span>
              <div className={`flex items-center gap-0.5 text-xs font-semibold font-mono ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isPos ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                <span>{isPos ? `+${coin.change24h}%` : `${coin.change24h}%`}</span>
              </div>
            </div>

            <div className="mt-2 pt-2 border-t border-zinc-800/50 flex items-center justify-between text-[11px] text-zinc-400">
              <span>Setup Score</span>
              <span className="font-mono text-zinc-300 font-medium">{coin.confidence}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
