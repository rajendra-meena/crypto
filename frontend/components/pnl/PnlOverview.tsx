'use client';

import React from 'react';
import { useTrading } from '@/context/TradingContext';
import { DollarSign, Percent, TrendingUp, BarChart3 } from 'lucide-react';

export const PnlOverview: React.FC = () => {
  const { positions, closedTrades, performanceMetrics } = useTrading();

  const totalUnrealizedPnl = positions.reduce((acc, curr) => acc + curr.unrealizedPnL, 0);
  const totalTrades = closedTrades.length;
  const wins = closedTrades.filter((t) => t.realizedPnL > 0).length;
  const losses = closedTrades.filter((t) => t.realizedPnL < 0).length;
  const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : '0.0';
  const todayRealizedPnl = performanceMetrics.totalRealizedPnL;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-3.5">
        <span className="text-[11px] text-zinc-400 uppercase font-medium">Today's Realized P&L</span>
        <div className={`text-lg font-mono font-bold mt-1 ${todayRealizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
          ${todayRealizedPnl.toFixed(2)}
        </div>
      </div>

      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-3.5">
        <span className="text-[11px] text-zinc-400 uppercase font-medium">Unrealized P&L</span>
        <div className={`text-lg font-mono font-bold mt-1 ${totalUnrealizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
          ${totalUnrealizedPnl.toFixed(2)}
        </div>
      </div>

      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-3.5">
        <span className="text-[11px] text-zinc-400 uppercase font-medium">Total Closed Trades</span>
        <div className="text-lg font-mono font-bold text-zinc-100 mt-1">{totalTrades}</div>
      </div>

      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-3.5">
        <span className="text-[11px] text-zinc-400 uppercase font-medium">Wins</span>
        <div className="text-lg font-mono font-bold text-emerald-400 mt-1">{wins}</div>
      </div>

      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-3.5">
        <span className="text-[11px] text-zinc-400 uppercase font-medium">Losses</span>
        <div className="text-lg font-mono font-bold text-rose-400 mt-1">{losses}</div>
      </div>

      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-3.5">
        <span className="text-[11px] text-zinc-400 uppercase font-medium">Win Rate</span>
        <div className="text-lg font-mono font-bold text-cyan-400 mt-1">{winRate}%</div>
      </div>
    </div>
  );
};