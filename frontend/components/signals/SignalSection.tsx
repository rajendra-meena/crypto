'use client';

import React from 'react';
import { ArrowDownRight, ArrowUpRight, Zap } from 'lucide-react';
import { useTrading } from '@/context/TradingContext';

export const SignalSection: React.FC = () => {
  const { signals, isEngineRunning, riskSnapshot } = useTrading();

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-amber-400" />
          <h3 className="font-bold text-zinc-100 text-base">Algo Trading Signals</h3>
        </div>
        <span className="text-xs text-zinc-400">
          MTF Price Action · backend authoritative · {isEngineRunning ? 'SCANNING' : 'ENGINE OFF'}
        </span>
      </div>

      {riskSnapshot.blocked && (
        <div className="mb-4 rounded-lg border border-amber-800/60 bg-amber-950/20 px-3 py-2 text-xs text-amber-300">
          New entries blocked by risk engine: <strong>{riskSnapshot.blockReason}</strong>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-400 uppercase font-mono text-[11px]">
              <th className="pb-3 px-3">Coin</th>
              <th className="pb-3 px-3">Action</th>
              <th className="pb-3 px-3">MTF</th>
              <th className="pb-3 px-3">Entry</th>
              <th className="pb-3 px-3">Stop</th>
              <th className="pb-3 px-3">Target</th>
              <th className="pb-3 px-3">R:R</th>
              <th className="pb-3 px-3">Setup Score</th>
              <th className="pb-3 px-3">Reason</th>
              <th className="pb-3 px-3">Status</th>
              <th className="pb-3 px-3 text-right">Execution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 font-mono">
            {signals.map((sig) => {
              const isBuy = sig.side === 'BUY';
              const statusClass = sig.status === 'EXECUTED'
                ? 'bg-blue-950 text-blue-400 border-blue-800'
                : sig.status === 'READY'
                  ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                  : sig.status === 'BLOCKED'
                    ? 'bg-amber-950 text-amber-400 border-amber-800'
                    : 'bg-zinc-900 text-zinc-400 border-zinc-700';
              return (
                <tr key={sig.id} className="hover:bg-zinc-900/40 transition">
                  <td className="py-3 px-3 font-sans font-bold text-zinc-200">{sig.symbol}</td>
                  <td className="py-3 px-3">
                    <span className={`inline-flex items-center gap-1 font-bold px-2 py-0.5 rounded text-[11px] ${isBuy ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                      {isBuy ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                      {sig.side}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-zinc-300">{sig.timeframe}</td>
                  <td className="py-3 px-3 text-zinc-200">${sig.entry}</td>
                  <td className="py-3 px-3 text-rose-400">${sig.stopLoss}</td>
                  <td className="py-3 px-3 text-emerald-400">${sig.target1}</td>
                  <td className="py-3 px-3 text-zinc-300">{sig.riskReward}</td>
                  <td className="py-3 px-3 font-bold text-zinc-100">{sig.confidence}%</td>
                  <td className="py-3 px-3 text-zinc-500 text-[11px] max-w-[360px] truncate" title={sig.reason}>{sig.reason}</td>
                  <td className="py-3 px-3"><span className={`px-2 py-0.5 rounded border text-[10px] font-bold ${statusClass}`}>{sig.status}</span></td>
                  <td className="py-3 px-3 text-right text-xs">
                    {sig.status === 'EXECUTED' ? <span className="text-blue-400">AUTO EXECUTED</span> :
                      sig.status === 'READY' ? <span className="text-emerald-400">AUTO</span> :
                        <span className="text-zinc-500">{sig.status}</span>}
                  </td>
                </tr>
              );
            })}
            {signals.length === 0 && (
              <tr>
                <td colSpan={11} className="py-8 text-center text-zinc-500 font-sans">
                  No confirmed multi-timeframe setup. Backend is scanning 15m trend → 5m setup → 1m trigger.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
