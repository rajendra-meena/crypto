'use client';

import React from 'react';
import { useTrading } from '@/context/TradingContext';
import { AlgoSignal, SignalStatus } from '@/types/trading';
import { Radio, ArrowUpRight, ArrowDownRight, Clock, Target, Shield, CheckCircle2 } from 'lucide-react';

export const SignalsPanel: React.FC = () => {
  const { signals, takeTrade } = useTrading();

  const getStatusBadge = (status: SignalStatus) => {
    switch (status) {
      case 'READY':
        return <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] px-2 py-0.5 rounded font-bold animate-pulse">READY</span>;
      case 'WATCHING':
        return <span className="bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[10px] px-2 py-0.5 rounded font-medium">WATCHING</span>;
      case 'EXECUTED':
        return <span className="bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[10px] px-2 py-0.5 rounded font-medium">EXECUTED</span>;
      case 'EXPIRED':
        return <span className="bg-zinc-700/50 text-zinc-400 border border-zinc-600 text-[10px] px-2 py-0.5 rounded font-medium">EXPIRED</span>;
      case 'INVALIDATED':
        return <span className="bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] px-2 py-0.5 rounded font-medium">INVALIDATED</span>;
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 text-white shadow-xl space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <Radio className="w-5 h-5 text-emerald-400" />
          <h3 className="font-semibold text-base">Algorithmic Signals</h3>
        </div>
        <span className="text-xs text-zinc-400 font-mono">{signals.length} Signals Loaded</span>
      </div>

      <div className="space-y-3">
        {signals.map((sig) => {
          const isBuy = sig.side === 'BUY';

          return (
            <div
              key={sig.id}
              className="bg-zinc-950/80 border border-zinc-800/90 rounded-lg p-4 space-y-3 hover:border-zinc-700 transition"
            >
              {/* Header Info */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-zinc-100">{sig.symbol}</span>
                  <span
                    className={`flex items-center text-xs font-bold px-2 py-0.5 rounded ${
                      isBuy ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                    }`}
                  >
                    {isBuy ? <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" /> : <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" />}
                    {sig.side}
                  </span>
                  <span className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded font-mono">
                    {sig.timeframe}
                  </span>
                </div>
                {getStatusBadge(sig.status)}
              </div>

              {/* Targets and Entries Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono bg-zinc-900/60 p-2.5 rounded border border-zinc-800/60">
                <div>
                  <span className="text-zinc-500 block text-[10px]">ENTRY</span>
                  <span className="text-zinc-200">${sig.entry.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">STOP LOSS</span>
                  <span className="text-rose-400 flex items-center gap-0.5">
                    <Shield className="w-3 h-3 inline" /> ${sig.stopLoss.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">TARGET 1</span>
                  <span className="text-emerald-400 flex items-center gap-0.5">
                    <Target className="w-3 h-3 inline" /> ${sig.target1.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">TARGET 2</span>
                  <span className="text-emerald-400 flex items-center gap-0.5">
                    <Target className="w-3 h-3 inline" /> ${sig.target2.toLocaleString()}
                  </span>
                </div>
              </div>

              {/* R:R & Details */}
              <div className="flex flex-wrap items-center justify-between text-xs text-zinc-400 pt-1 gap-2">
                <div className="flex items-center gap-3">
                  <span>R:R <strong className="text-zinc-200">{sig.riskReward}</strong></span>
                  <span>Conf: <strong className="text-emerald-400">{sig.confidence}%</strong></span>
                  <span className="flex items-center gap-1 text-[11px] text-zinc-500">
                    <Clock className="w-3 h-3" /> {sig.generatedTime}
                  </span>
                </div>

                {/* Only READY signals show Take Trade button */}
                {sig.status === 'READY' && (
                  <button
                    onClick={() => takeTrade(sig)}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-3.5 py-1.5 rounded text-xs flex items-center gap-1.5 transition active:scale-95 shadow-md shadow-emerald-950"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" /> Take Trade
                  </button>
                )}
              </div>

              {/* Reason */}
              <p className="text-[11px] text-zinc-500 italic bg-zinc-900/30 px-2 py-1 rounded">
                &ldquo;{sig.reason}&rdquo;
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};