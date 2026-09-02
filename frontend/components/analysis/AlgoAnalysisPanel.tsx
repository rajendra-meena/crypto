'use client';

import React from 'react';
import { AlertTriangle, CheckCircle2, Cpu } from 'lucide-react';
import { useTrading } from '@/context/TradingContext';

export const AlgoAnalysisPanel: React.FC = () => {
  const { selectedAnalysis, deltaConnectionState } = useTrading();

  if (!selectedAnalysis) {
    return (
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 flex items-center justify-center min-h-[360px]">
        <div className="text-center text-zinc-400">
          <Cpu className="h-10 w-10 mx-auto mb-3 opacity-50" />
          <p>Waiting for backend PA MTF V4 analysis</p>
        </div>
      </div>
    );
  }

  const biasClass = selectedAnalysis.bias === 'BUY'
    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
    : selectedAnalysis.bias === 'SELL'
      ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
      : 'bg-amber-500/20 text-amber-400 border-amber-500/40';

  const statusClass = selectedAnalysis.status === 'READY' || selectedAnalysis.status === 'EXECUTED'
    ? 'text-emerald-400'
    : selectedAnalysis.status === 'BLOCKED' || selectedAnalysis.status === 'FILTERED'
      ? 'text-amber-400'
      : 'text-zinc-400';

  const blockers = selectedAnalysis.blockers || [];

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 flex flex-col justify-between min-h-[420px]">
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800/60 mb-4">
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-emerald-400" />
            <div>
              <h3 className="font-bold text-zinc-100 text-sm tracking-wide uppercase">PA MTF V4 Engine</h3>
              <p className="text-[10px] text-zinc-500 mt-0.5">15m regime → 5m trend → completed 1m breakout / pullback trigger</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">BACKEND AUTHORITY</span>
            {deltaConnectionState !== 'CONNECTED' && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40 text-[10px] font-bold">
                <AlertTriangle className="h-3 w-3" /> {deltaConnectionState}
              </span>
            )}
          </div>
        </div>

        <div className="space-y-2 text-xs">
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">15m Market Regime</span><span className="font-semibold text-zinc-200">{selectedAnalysis.trend}</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">5m Trend</span><span className="font-semibold text-zinc-200">{selectedAnalysis.mtfTrend || 'NEUTRAL'}</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">Setup</span><span className="font-semibold text-zinc-200">{selectedAnalysis.setup.replace(/_/g, ' ')}</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">1m Completed Trigger</span><span className="font-semibold text-zinc-200">{selectedAnalysis.trigger.replace(/_/g, ' ')}</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">RSI (5m)</span><span className="font-mono text-zinc-200">{selectedAnalysis.rsi}</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">ATR % (5m)</span><span className="font-mono text-zinc-200">{selectedAnalysis.atrPct}%</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">Trigger Volume</span><span className="font-mono text-zinc-200">{selectedAnalysis.volumeRatio}x</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">Trigger Body Quality</span><span className="font-mono text-zinc-200">{Math.round((selectedAnalysis.bodyQuality || 0) * 100)}%</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">Support / Resistance</span><span className="font-mono text-zinc-300">${selectedAnalysis.support} / ${selectedAnalysis.resistance}</span></div>
          <div className="flex justify-between py-1 border-b border-zinc-900"><span className="text-zinc-400">Backend Status</span><span className={`font-bold ${statusClass}`}>{selectedAnalysis.status}</span></div>
        </div>

        <div className="mt-4 rounded-lg bg-zinc-900/60 border border-zinc-800 px-3 py-2 text-[11px] text-zinc-400 leading-relaxed">{selectedAnalysis.reason}</div>

        <div className="mt-3">
          {blockers.length === 0 ? (
            <div className="flex items-center gap-1.5 text-[11px] text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" /> No hard blocker on the latest completed candle.</div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {blockers.map((blocker) => (
                <span key={blocker} className="px-2 py-1 rounded border border-amber-800/60 bg-amber-950/20 text-[10px] text-amber-300">{blocker.replace(/_/g, ' ')}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 p-4 rounded-xl bg-zinc-900/80 border border-zinc-800 flex items-center justify-between">
        <div>
          <div className="text-[11px] text-zinc-400 uppercase font-bold tracking-wider mb-1">Executable Bias</div>
          <span className={`px-3 py-1 rounded-md border font-extrabold text-sm ${biasClass}`}>{selectedAnalysis.bias}</span>
        </div>
        <div className="text-right">
          <div className="text-[11px] text-zinc-400 uppercase font-bold tracking-wider mb-1">Setup Score</div>
          <div className="font-mono text-lg font-extrabold text-emerald-400">{selectedAnalysis.setupScore}/100</div>
          <div className="text-[10px] text-zinc-500 mt-1">Strategy quality score, not win probability</div>
        </div>
      </div>
    </div>
  );
};