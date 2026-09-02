'use client';

import React, { useEffect, useState } from 'react';
import { useTrading } from '@/context/TradingContext';
import { loadPaperState } from '@/services/paperPersistenceService';
import { PaperPosition } from '@/types/trading';

export const ActiveTradePanel: React.FC = () => {
  const { positions: contextPositions, closePosition, backendConnectionState } = useTrading();
  const [positions, setPositions] = useState<PaperPosition[]>(contextPositions);

  useEffect(() => {
    setPositions(contextPositions);
  }, [contextPositions]);

  useEffect(() => {
    if (backendConnectionState !== 'CONNECTED') return;

    let cancelled = false;
    const sync = async () => {
      try {
        const state = await loadPaperState();
        if (!cancelled && Array.isArray(state.positions)) setPositions(state.positions);
      } catch (error) {
        console.error('[ActiveTradePanel] Failed to sync paper positions:', error);
      }
    };

    void sync();
    const timer = window.setInterval(sync, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [backendConnectionState]);

  if (positions.length === 0) {
    return (
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 text-center">
        <h3 className="font-bold text-zinc-100 text-base mb-1">Active Positions (Paper)</h3>
        <p className="text-xs text-zinc-400">No open paper positions. Backend strategy engine is scanning all supported coins.</p>
      </div>
    );
  }

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-zinc-100 text-base">Active Positions (Paper Execution)</h3>
        <span className="text-xs font-mono text-zinc-400">{positions.length} Open · DB synced</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-400 uppercase font-mono text-[11px]">
              <th className="pb-3 px-3">Symbol</th>
              <th className="pb-3 px-3">Side</th>
              <th className="pb-3 px-3">Notional</th>
              <th className="pb-3 px-3">Entry</th>
              <th className="pb-3 px-3">Current</th>
              <th className="pb-3 px-3">SL / TP</th>
              <th className="pb-3 px-3">Net Est. P&L</th>
              <th className="pb-3 px-3">Capital %</th>
              <th className="pb-3 px-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 font-mono">
            {positions.map((pos) => {
              const isProfit = pos.unrealizedPnL >= 0;
              return (
                <tr key={pos.id} className="hover:bg-zinc-900/40 transition">
                  <td className="py-3 px-3 font-sans font-bold text-zinc-200">{pos.symbol}</td>
                  <td className="py-3 px-3"><span className={`inline-flex font-bold px-2 py-0.5 rounded text-[11px] ${pos.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>{pos.side}</span></td>
                  <td className="py-3 px-3 text-zinc-300">${Number(pos.size).toFixed(2)}</td>
                  <td className="py-3 px-3 text-zinc-300">${pos.entryPrice}</td>
                  <td className="py-3 px-3 font-bold text-zinc-100">${pos.currentPrice}</td>
                  <td className="py-3 px-3 text-zinc-400"><span className="text-rose-400">${pos.stopLoss}</span> / <span className="text-emerald-400">${pos.target1}</span></td>
                  <td className={`py-3 px-3 font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>{isProfit ? `+$${pos.unrealizedPnL}` : `-$${Math.abs(pos.unrealizedPnL)}`}</td>
                  <td className={`py-3 px-3 font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>{isProfit ? `+${pos.unrealizedPnLPercent}%` : `${pos.unrealizedPnLPercent}%`}</td>
                  <td className="py-3 px-3 text-right">
                    <button onClick={() => closePosition(pos.id)} className="px-2.5 py-1 bg-zinc-900 hover:bg-rose-950 border border-zinc-700 hover:border-rose-700 text-zinc-300 hover:text-rose-300 rounded font-medium text-xs transition">Close</button>
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
