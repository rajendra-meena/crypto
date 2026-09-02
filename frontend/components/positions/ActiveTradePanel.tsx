'use client';

import React, { useState } from 'react';
import { useTrading } from '@/context/TradingContext';

export const ActiveTradePanel: React.FC = () => {
  const { positions, closePosition } = useTrading();
  const [closingId, setClosingId] = useState<string | null>(null);

  const handleClose = (positionId: string) => {
    setClosingId(positionId);
    closePosition(positionId);
    window.setTimeout(() => setClosingId(null), 1200);
  };

  if (positions.length === 0) {
    return (
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 text-center">
        <h3 className="font-bold text-zinc-100 text-base mb-1">Active Positions (Paper)</h3>
        <p className="text-xs text-zinc-400">No open positions. Backend MTF strategy is scanning all supported coins.</p>
      </div>
    );
  }

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-zinc-100 text-base">Active Positions (Backend Paper Execution)</h3>
        <span className="text-xs font-mono text-zinc-400">{positions.length} Open · API synced</span>
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
              <th className="pb-3 px-3">R</th>
              <th className="pb-3 px-3">Stage</th>
              <th className="pb-3 px-3">Net Est. P&L</th>
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
                  <td className={`py-3 px-3 font-bold ${(pos.rMultiple || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{Number(pos.rMultiple || 0).toFixed(2)}R</td>
                  <td className="py-3 px-3 text-zinc-300">{pos.managementStage || 'INITIAL'}</td>
                  <td className={`py-3 px-3 font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>{isProfit ? `+$${pos.unrealizedPnL}` : `-$${Math.abs(pos.unrealizedPnL)}`}</td>
                  <td className="py-3 px-3 text-right">
                    <button disabled={closingId === pos.id} onClick={() => handleClose(pos.id)} className="px-2.5 py-1 bg-zinc-900 hover:bg-rose-950 border border-zinc-700 hover:border-rose-700 disabled:opacity-50 text-zinc-300 hover:text-rose-300 rounded font-medium text-xs transition">
                      {closingId === pos.id ? 'Closing...' : 'Close'}
                    </button>
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
