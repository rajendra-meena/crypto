'use client';

import React, { useState } from 'react';
import { useTrading } from '@/context/TradingContext';
import { saveTradingSettings } from '@/services/paperPersistenceService';
import { Sliders, Shield, Key, AlertTriangle, Check } from 'lucide-react';
import { TerminalSettings } from '@/types/trading';

export const SettingsPanel: React.FC = () => {
  const { settings, updateSettings, isEngineRunning, setEngineRunning } = useTrading();
  const [testApiSuccess, setTestApiSuccess] = useState<boolean | null>(null);
  const [saveStatus, setSaveStatus] = useState<'IDLE' | 'SAVED' | 'ERROR'>('IDLE');

  const updateRiskSetting = (patch: Partial<TerminalSettings>) => {
    updateSettings(patch);
    setSaveStatus('IDLE');
    void saveTradingSettings(patch as Partial<TerminalSettings> & Record<string, unknown>)
      .then(() => setSaveStatus('SAVED'))
      .catch((error) => {
        console.error('[SettingsPanel] Failed to save backend risk settings:', error);
        setSaveStatus('ERROR');
      });
  };

  const handleTestConnection = () => {
    setTestApiSuccess(null);
    setTimeout(() => setTestApiSuccess(true), 600);
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 text-white shadow-xl space-y-5">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <Sliders className="w-5 h-5 text-emerald-400" />
          <h3 className="font-semibold text-base">Terminal Engine & Risk Controls</h3>
        </div>
        <div className="flex items-center gap-3 bg-zinc-950 px-3 py-1.5 rounded-lg border border-zinc-800">
          <span className="text-xs font-semibold">ENGINE: <strong className={isEngineRunning ? 'text-emerald-400' : 'text-zinc-400'}>{isEngineRunning ? 'ON (ARMED)' : 'OFF'}</strong></span>
          <button onClick={() => setEngineRunning(!isEngineRunning)} className={`w-12 h-6 flex items-center rounded-full p-1 transition duration-300 ${isEngineRunning ? 'bg-emerald-600 justify-end' : 'bg-zinc-700 justify-start'}`}>
            <div className="bg-white w-4 h-4 rounded-full shadow-md transform" />
          </button>
        </div>
      </div>

      <div className={`p-3 rounded-lg border text-xs flex items-center gap-2 ${isEngineRunning ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300' : 'bg-zinc-950/60 border-zinc-800 text-zinc-400'}`}>
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span>{isEngineRunning ? 'Backend engine is ARMED. All supported coins are scanned continuously and paper positions are managed server-side.' : 'Engine is OFF. Live market data continues, but no new automatic paper entries will be created.'}</span>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5"><Shield className="w-4 h-4 text-emerald-400" /> Risk Management (Backend DB)</h4>
          {saveStatus === 'SAVED' && <span className="text-[11px] text-emerald-400">Saved to database</span>}
          {saveStatus === 'ERROR' && <span className="text-[11px] text-rose-400">Database save failed</span>}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div><label className="text-zinc-400 block mb-1">Capital ($)</label><input type="number" value={settings.capital} onChange={(e) => updateRiskSetting({ capital: Number(e.target.value) })} className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none" /></div>
          <div><label className="text-zinc-400 block mb-1">Risk per Trade (%)</label><input type="number" step="0.1" value={settings.riskPerTradePct} onChange={(e) => updateRiskSetting({ riskPerTradePct: Number(e.target.value) })} className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none" /></div>
          <div><label className="text-zinc-400 block mb-1">Max Leverage (x)</label><input type="number" value={settings.maxLeverage} onChange={(e) => updateRiskSetting({ maxLeverage: Number(e.target.value) })} className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none" /></div>
          <div><label className="text-zinc-400 block mb-1">Max Daily Loss (%)</label><input type="number" step="0.1" value={settings.maxDailyLossPct} onChange={(e) => updateRiskSetting({ maxDailyLossPct: Number(e.target.value) })} className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none" /></div>
          <div><label className="text-zinc-400 block mb-1">Max Concurrent Trades</label><input type="number" value={settings.maxConcurrentTrades} onChange={(e) => updateRiskSetting({ maxConcurrentTrades: Number(e.target.value) })} className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none" /></div>
        </div>
        <p className="text-[11px] text-zinc-500">Backend defaults also enforce minimum setup score 72%, max 8 closed trades/day, 3 consecutive-loss circuit breaker, 30-minute symbol cooldown, ATR-based stop, 1:2 target, and paper fees/slippage.</p>
      </div>

      <div className="space-y-3 pt-2 border-t border-zinc-800">
        <h4 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5"><Key className="w-4 h-4 text-amber-400" /> Exchange API Credentials (MOCK SIMULATION ONLY)</h4>
        <div className="bg-amber-950/20 border border-amber-800/40 rounded p-2.5 text-xs text-amber-300">Live execution remains disabled. The new backend engine executes PAPER trades only.</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div><label className="text-zinc-400 block mb-1">API Key</label><input type="password" placeholder="delta_mock_key_xxxx" value={settings.apiKey} onChange={(e) => updateSettings({ apiKey: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none" /></div>
          <div><label className="text-zinc-400 block mb-1">API Secret</label><input type="password" placeholder="delta_mock_secret_xxxx" value={settings.apiSecret} onChange={(e) => updateSettings({ apiSecret: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none" /></div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleTestConnection} className="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs px-3 py-2 rounded transition">Test Mock Connection</button>
          {testApiSuccess && <span className="text-xs text-emerald-400 flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Mock Delta API Ping Successful (200 OK)</span>}
        </div>
      </div>
    </div>
  );
};
