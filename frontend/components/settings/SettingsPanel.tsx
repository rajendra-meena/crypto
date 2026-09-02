'use client';

import React from 'react';
import { AlertTriangle, Shield, Sliders } from 'lucide-react';
import { useTrading } from '@/context/TradingContext';
import { TerminalSettings } from '@/types/trading';

export const SettingsPanel: React.FC = () => {
  const { settings, updateSettings, isEngineRunning, setEngineRunning, riskSnapshot } = useTrading();

  const field = (
    label: string,
    key: keyof TerminalSettings,
    step = '0.1',
  ) => (
    <div>
      <label className="text-zinc-400 block mb-1">{label}</label>
      <input
        type="number"
        step={step}
        value={Number(settings[key])}
        onChange={(e) => updateSettings({ [key]: Number(e.target.value) } as Partial<TerminalSettings>)}
        className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none"
      />
    </div>
  );

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 text-white shadow-xl space-y-5">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <Sliders className="w-5 h-5 text-emerald-400" />
          <h3 className="font-semibold text-base">Backend Algo Engine & Risk Controls</h3>
        </div>
        <div className="flex items-center gap-3 bg-zinc-950 px-3 py-1.5 rounded-lg border border-zinc-800">
          <span className="text-xs font-semibold">ENGINE: <strong className={isEngineRunning ? 'text-emerald-400' : 'text-zinc-400'}>{isEngineRunning ? 'ON (ARMED)' : 'OFF'}</strong></span>
          <button onClick={() => setEngineRunning(!isEngineRunning)} className={`w-12 h-6 flex items-center rounded-full p-1 transition ${isEngineRunning ? 'bg-emerald-600 justify-end' : 'bg-zinc-700 justify-start'}`}>
            <div className="bg-white w-4 h-4 rounded-full shadow-md" />
          </button>
        </div>
      </div>

      <div className={`p-3 rounded-lg border text-xs flex items-start gap-2 ${riskSnapshot.blocked ? 'bg-amber-950/30 border-amber-800/60 text-amber-300' : isEngineRunning ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300' : 'bg-zinc-950/60 border-zinc-800 text-zinc-400'}`}>
        <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <span>
          {riskSnapshot.blocked
            ? `Risk engine is blocking new entries: ${riskSnapshot.blockReason}`
            : isEngineRunning
              ? 'Backend engine is scanning BTC, ETH, SOL, XRP and BNB using 15m trend → 5m setup → 1m confirmation. Paper execution and exits are server-side.'
              : 'Engine is OFF. Live market data continues, but no new paper positions will be opened.'}
        </span>
      </div>

      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5"><Shield className="w-4 h-4 text-emerald-400" /> Capital & Portfolio Risk</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
          {field('Capital ($)', 'capital', '100')}
          {field('Risk / Trade (%)', 'riskPerTradePct')}
          {field('Max Daily Loss (%)', 'maxDailyLossPct')}
          {field('Max Portfolio Risk (%)', 'maxPortfolioRiskPct')}
          {field('Max Concurrent Trades', 'maxConcurrentTrades', '1')}
          {field('Max Leverage (x)', 'maxLeverage', '1')}
          {field('Max Trades / Day', 'maxTradesPerDay', '1')}
          {field('Max Consecutive Losses', 'maxConsecutiveLosses', '1')}
        </div>
      </div>

      <div className="space-y-3 pt-2 border-t border-zinc-800">
        <h4 className="text-xs font-semibold text-zinc-300">Strategy Quality & Entry Filters</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
          {field('Minimum Setup Score', 'minSetupScore', '1')}
          {field('Cooldown (minutes)', 'cooldownMinutes', '1')}
          {field('Max Entry Drift (%)', 'maxEntryDriftPct', '0.05')}
          {field('ATR Stop Multiplier', 'atrStopMultiplier', '0.1')}
          {field('Min ATR (%)', 'minAtrPct', '0.05')}
          {field('Max ATR (%)', 'maxAtrPct', '0.1')}
          {field('Min Stop (%)', 'minStopPct', '0.05')}
          {field('Max Stop (%)', 'maxStopPct', '0.1')}
        </div>
      </div>

      <div className="space-y-3 pt-2 border-t border-zinc-800">
        <h4 className="text-xs font-semibold text-zinc-300">Position Management</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
          {field('Target R:R', 'targetRR', '0.1')}
          {field('Breakeven At (R)', 'breakevenAtR', '0.1')}
          {field('Trail Start (R)', 'trailingStartR', '0.1')}
          {field('Trail Distance (R)', 'trailingDistanceR', '0.1')}
          {field('Max Hold (minutes)', 'maxHoldMinutes', '15')}
          {field('Fee Rate (%)', 'feeRatePct', '0.01')}
          {field('Slippage (%)', 'slippagePct', '0.01')}
        </div>
      </div>

      <div className="pt-3 border-t border-zinc-800 text-[11px] text-zinc-500">
        Settings are persisted through <code>/api/trading/settings</code>. This execution path is PAPER ONLY; API keys are not used for real orders.
      </div>
    </div>
  );
};
