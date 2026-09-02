'use client';

import React from 'react';
import { AlertTriangle, Shield, Sliders } from 'lucide-react';
import { useTrading } from '@/context/TradingContext';
import { TerminalSettings } from '@/types/trading';

export const SettingsPanel: React.FC = () => {
  const { settings, updateSettings, isEngineRunning, setEngineRunning, riskSnapshot } = useTrading();

  const numberField = (label: string, key: keyof TerminalSettings, step = '0.1') => (
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
          <div>
            <h3 className="font-semibold text-base">Backend Algo Engine & Risk Controls</h3>
            <p className="text-[11px] text-zinc-500 mt-0.5">MTPA 3TF · 15m regime → 5m trend → completed 1m breakout</p>
          </div>
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
            ? `New entries are blocked by the backend risk engine: ${riskSnapshot.blockReason}`
            : isEngineRunning
              ? 'The server is independently scanning BTC, ETH, SOL, XRP and BNB. Browser refresh/close does not create or cancel signals.'
              : 'Engine is OFF. Live market data continues, but the backend will not open new paper positions.'}
        </span>
      </div>

      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5"><Shield className="w-4 h-4 text-emerald-400" /> Capital & Portfolio Risk</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
          {numberField('Capital ($)', 'capital', '100')}
          {numberField('Risk / Trade (%)', 'riskPerTradePct', '0.05')}
          {numberField('Max Daily Loss (%)', 'maxDailyLossPct', '0.1')}
          {numberField('Max Portfolio Risk (%)', 'maxPortfolioRiskPct', '0.1')}
          {numberField('Max Concurrent Trades', 'maxConcurrentTrades', '1')}
          {numberField('Max Same-Direction Trades', 'maxSameDirection', '1')}
          {numberField('Max Leverage (x)', 'maxLeverage', '1')}
          {numberField('Max Trades / UTC Day', 'maxTradesPerDay', '1')}
          {numberField('Max Consecutive Losses', 'maxConsecutiveLosses', '1')}
        </div>
      </div>

      <div className="space-y-3 pt-2 border-t border-zinc-800">
        <h4 className="text-xs font-semibold text-zinc-300">Strategy Quality & Entry Filters</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
          {numberField('Minimum Setup Score', 'minSetupScore', '1')}
          {numberField('Min 1m Volume Ratio', 'minVolumeRatio', '0.05')}
          {numberField('Cooldown (minutes)', 'cooldownMinutes', '1')}
          {numberField('Max Entry Drift (%)', 'maxEntryDriftPct', '0.05')}
          {numberField('ATR Stop Multiplier', 'atrStopMultiplier', '0.1')}
          {numberField('Min 5m ATR (%)', 'minAtrPct', '0.01')}
          {numberField('Max 5m ATR (%)', 'maxAtrPct', '0.1')}
          {numberField('Min Stop (%)', 'minStopPct', '0.05')}
          {numberField('Max Stop (%)', 'maxStopPct', '0.1')}
          <div className="sm:col-span-2 lg:col-span-1">
            <label className="text-zinc-400 block mb-1">BTC Regime Filter for Altcoins</label>
            <button
              type="button"
              onClick={() => updateSettings({ btcTrendFilter: !settings.btcTrendFilter })}
              className={`w-full rounded border px-3 py-2 font-semibold transition ${settings.btcTrendFilter ? 'bg-emerald-950/40 border-emerald-700 text-emerald-300' : 'bg-zinc-950 border-zinc-800 text-zinc-400'}`}
            >
              {settings.btcTrendFilter ? 'ON · block BTC-conflicting alt setups' : 'OFF'}
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-3 pt-2 border-t border-zinc-800">
        <h4 className="text-xs font-semibold text-zinc-300">Position Management</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
          {numberField('Target R:R', 'targetRR', '0.1')}
          {numberField('Breakeven At (R)', 'breakevenAtR', '0.1')}
          {numberField('Trail Start (R)', 'trailingStartR', '0.1')}
          {numberField('Trail Distance (R)', 'trailingDistanceR', '0.1')}
          {numberField('Max Hold (minutes)', 'maxHoldMinutes', '15')}
          {numberField('Fee Rate (%)', 'feeRatePct', '0.01')}
          {numberField('Slippage (%)', 'slippagePct', '0.01')}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-zinc-800 text-xs">
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3"><div className="text-zinc-500">Today Trades</div><div className="font-mono text-zinc-100 mt-1">{riskSnapshot.todayTrades}</div></div>
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3"><div className="text-zinc-500">Realized P&L</div><div className={`font-mono mt-1 ${riskSnapshot.todayRealizedPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>${riskSnapshot.todayRealizedPnL}</div></div>
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3"><div className="text-zinc-500">Open Risk</div><div className="font-mono text-zinc-100 mt-1">${riskSnapshot.openRisk} / ${riskSnapshot.maxPortfolioRisk}</div></div>
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3"><div className="text-zinc-500">Loss Streak</div><div className="font-mono text-zinc-100 mt-1">{riskSnapshot.consecutiveLosses}</div></div>
      </div>

      <div className="pt-2 text-[11px] text-zinc-500">
        All values are persisted via <code>/api/trading/settings</code>. Execution is PAPER ONLY; the frontend cannot create a position directly.
      </div>
    </div>
  );
};
