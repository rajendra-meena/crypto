'use client';

import React, { useEffect, useState } from 'react';
import { useTrading } from '@/context/TradingContext';
import { PaperPosition } from '@/types/trading';
import { DollarSign, Percent, TrendingUp, XCircle, Award } from 'lucide-react';

export const PaperTradingPanel: React.FC = () => {
  const { positions, closedTrades, closePosition, performanceMetrics } = useTrading();
  const [, setTimer] = useState<number>(Date.now());

  // Trigger re-render every second for real-time trade duration update
  useEffect(() => {
    const t = setInterval(() => setTimer(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const formatDuration = (openedAt: number) => {
    const totalSecs = Math.max(0, Math.floor((Date.now() - openedAt) / 1000));
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 text-white shadow-xl space-y-6">
      {/* Header & Metrics */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <h3 className="font-semibold text-base flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-emerald-400" /> Paper Trade Execution Engine
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5">Real-time simulation engine (Zero exchange API calls)</p>
        </div>

        {/* Realized Metrics */}
        <div className="flex items-center gap-4 bg-zinc-950 px-3.5 py-2 rounded-lg border border-zinc-800 font-mono text-xs">
          <div>
            <span className="text-zinc-500 block text-[10px]">TOTAL P&L</span>
            <span className={`font-bold ${performanceMetrics.totalRealizedPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              ${performanceMetrics.totalRealizedPnL.toFixed(2)}
            </span>
          </div>
          <div className="h-6 w-px bg-zinc-800" />
          <div>
            <span className="text-zinc-500 block text-[10px]">WIN RATE</span>
            <span className="font-bold text-zinc-200">{performanceMetrics.winRate}%</span>
          </div>
          <div className="h-6 w-px bg-zinc-800" />
          <div>
            <span className="text-zinc-500 block text-[10px]">TRADES (W/L)</span>
            <span className="font-bold text-zinc-200">
              {performanceMetrics.totalTrades} ({performanceMetrics.wins}W / {performanceMetrics.losses}L)
            </span>
          </div>
        </div>
      </div>

      {/* Active Positions */}
      <div>
        <h4 className="text-xs font-semibold text-zinc-300 mb-3 flex items-center gap-1.5">
          <TrendingUp className="w-4 h-4 text-emerald-400" /> Active Paper Positions ({positions.length})
        </h4>

        {positions.length === 0 ? (
          <div className="text-center py-6 border border-dashed border-zinc-800 rounded-lg text-zinc-500 text-xs">
            No active paper positions. Click &apos;Take Trade&apos; on any READY signal.
          </div>
        ) : (
          <div className="space-y-2.5">
            {positions.map((pos: PaperPosition) => {
              const isProfit = pos.unrealizedPnL >= 0;

              return (
                <div
                  key={pos.id}
                  className="bg-zinc-950 border border-zinc-800 rounded-lg p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-zinc-100">{pos.symbol}</span>
                      <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${pos.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                        {pos.side} {pos.leverage}x
                      </span>
                    </div>
                    <div className="text-zinc-400 font-mono text-[11px]">
                      Entry: ${pos.entryPrice.toLocaleString()} | Mark: ${pos.currentPrice.toLocaleString()}
                    </div>
                  </div>

                  <div className="font-mono text-center">
                    <span className="text-zinc-500 block text-[10px]">UNREALIZED P&L</span>
                    <span className={`font-bold text-sm ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isProfit ? '+' : ''}${pos.unrealizedPnL.toFixed(2)} ({isProfit ? '+' : ''}{pos.unrealizedPnLPercent}%)
                    </span>
                  </div>

                  <div className="font-mono text-right">
                    <span className="text-zinc-500 block text-[10px]">DURATION</span>
                    <span className="text-zinc-300 text-[11px]">{formatDuration(pos.openedAt)}</span>
                  </div>

                  <button
                    onClick={() => closePosition(pos.id)}
                    className="bg-rose-600/80 hover:bg-rose-600 text-white px-3 py-1.5 rounded flex items-center gap-1 text-xs transition active:scale-95"
                  >
                    <XCircle className="w-3.5 h-3.5" /> Close Trade
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Closed Trade History */}
      {closedTrades.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-400 mb-2 flex items-center gap-1">
            <Award className="w-3.5 h-3.5 text-zinc-400" /> Recent Closed Positions
          </h4>
          <div className="max-h-40 overflow-y-auto space-y-1.5 text-xs font-mono pr-1">
            {closedTrades.map((trade) => (
              <div key={trade.id} className="bg-zinc-950/50 border border-zinc-800/60 p-2 rounded flex justify-between items-center text-[11px]">
                <span>{trade.symbol} ({trade.side})</span>
                <span>Exit: ${trade.exitPrice.toLocaleString()}</span>
                <span className={trade.realizedPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                  {trade.realizedPnL >= 0 ? '+' : ''}${trade.realizedPnL.toFixed(2)} ({trade.realizedPnLPercent}%)
                </span>
                <span className="text-zinc-500">{trade.durationSeconds}s</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};