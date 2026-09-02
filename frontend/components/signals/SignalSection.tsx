'use client';

import React, { useEffect, useState } from 'react';
import { useTrading } from '@/context/TradingContext';
import { loadPaperState } from '@/services/paperPersistenceService';
import { ArrowUpRight, ArrowDownRight, Zap } from 'lucide-react';
import { AlgoSignal } from '@/types/trading';

export const SignalSection: React.FC = () => {
  const { settings, canTrade } = useTrading();
  const [backendSignals, setBackendSignals] = useState<AlgoSignal[]>([]);

  useEffect(() => {
    let active = true;

    const sync = async () => {
      try {
        const state = await loadPaperState();
        if (active) setBackendSignals(Array.isArray(state.signals) ? state.signals : []);
      } catch (error) {
        console.error('[SignalSection] Failed to sync backend signals:', error);
      }
    };

    void sync();
    const timer = window.setInterval(() => void sync(), 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-amber-400" />
          <h3 className="font-bold text-zinc-100 text-base">Algo Trading Signals</h3>
        </div>
        <span className="text-xs text-zinc-400">
          {settings.isLiveMode ? 'Live execution disabled' : 'Backend scanner · authoritative signals'}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-400 uppercase font-mono text-[11px]">
              <th className="pb-3 px-3">Coin</th><th className="pb-3 px-3">Action</th><th className="pb-3 px-3">Timeframe</th>
              <th className="pb-3 px-3">Entry</th><th className="pb-3 px-3">Stop Loss</th><th className="pb-3 px-3">Target</th>
              <th className="pb-3 px-3">R:R</th><th className="pb-3 px-3">Setup Score</th><th className="pb-3 px-3">Time</th>
              <th className="pb-3 px-3">Reason</th><th className="pb-3 px-3">Status</th><th className="pb-3 px-3 text-right">Execution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 font-mono">
            {backendSignals.map((sig) => {
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
                      {isBuy ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}{sig.side}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-zinc-300">{sig.timeframe}</td>
                  <td className="py-3 px-3 text-zinc-200">${sig.entry}</td>
                  <td className="py-3 px-3 text-rose-400">${sig.stopLoss}</td>
                  <td className="py-3 px-3 text-emerald-400">${sig.target1}</td>
                  <td className="py-3 px-3 text-zinc-300">{sig.riskReward}</td>
                  <td className="py-3 px-3 font-bold text-zinc-200">{sig.confidence}%</td>
                  <td className="py-3 px-3 text-zinc-400 text-[11px]">{sig.generatedTime}</td>
                  <td className="py-3 px-3 text-zinc-500 text-[11px] max-w-[280px] truncate" title={sig.reason}>{sig.reason}</td>
                  <td className="py-3 px-3"><span className={`px-2 py-0.5 rounded border text-[10px] font-bold ${statusClass}`}>{sig.status}</span></td>
                  <td className="py-3 px-3 text-right">
                    <span className={sig.status === 'EXECUTED' ? 'text-blue-400 text-xs' : sig.status === 'READY' && canTrade ? 'text-emerald-400 text-xs' : 'text-zinc-500 text-xs'}>
                      {sig.status === 'EXECUTED' ? 'AUTO EXECUTED' : sig.status === 'READY' && canTrade ? 'AUTO' : sig.status}
                    </span>
                  </td>
                </tr>
              );
            })}
            {backendSignals.length === 0 && (
              <tr>
                <td colSpan={12} className="py-8 text-center text-zinc-500 font-sans">
                  No backend-confirmed setup right now. Scanner is waiting for a completed-candle setup.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
