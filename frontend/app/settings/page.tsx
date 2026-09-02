'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useTrading } from '@/context/TradingContext';
import { ArrowLeft, KeyRound, Shield, AlertTriangle, Check } from 'lucide-react';

export default function SettingsPage() {
  const { isEngineRunning, setEngineRunning, settings, updateSettings } = useTrading();
  const [apiKey, setApiKey] = useState('demo_delta_api_key_xxxxxxxx');
  const [apiSecret, setApiSecret] = useState('demo_delta_api_secret_yyyyyyyy');
  const [saveToast, setSaveToast] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2500);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-100"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-xl font-bold text-zinc-100">Terminal Configuration</h1>
        </div>
        {saveToast && (
          <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-3 py-1 rounded">
            <Check className="h-3.5 w-3.5" /> Settings saved locally
          </span>
        )}
      </div>

      {/* Mode Configuration */}
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 space-y-4">
        <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
          <Shield className="h-4 w-4 text-emerald-400" /> Trading Mode
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <div
            onClick={() => setEngineRunning(true)}
            className={`p-4 rounded-xl border cursor-pointer transition ${
              isEngineRunning
                ? 'bg-emerald-950/30 border-emerald-500/50 text-emerald-300'
                : 'bg-zinc-900/40 border-zinc-800 text-zinc-400'
            }`}
          >
            <div className="font-bold text-sm">Engine Running</div>
            <p className="text-xs text-zinc-400 mt-1">Algorithmic trading engine is active and generating signals.</p>
          </div>

          <div
            onClick={() => setEngineRunning(false)}
            className={`p-4 rounded-xl border cursor-pointer transition ${
              !isEngineRunning
                ? 'bg-amber-950/30 border-amber-500/50 text-amber-300'
                : 'bg-zinc-900/40 border-zinc-800 text-zinc-400'
            }`}
          >
            <div className="font-bold text-sm">Engine Stopped</div>
            <p className="text-xs text-zinc-400 mt-1">Algorithmic trading engine is paused.</p>
          </div>
        </div>
      </div>

      {/* Delta Exchange API Keys */}
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-amber-400" /> Delta Exchange API Credentials
          </h2>
          <span className="text-[11px] text-amber-400 bg-amber-950/40 border border-amber-800/50 px-2 py-0.5 rounded">
            Phase 1 Mock
          </span>
        </div>

        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span>Delta Exchange integration will be enabled in a later phase. No live requests will be sent.</span>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-zinc-400 mb-1">API Key</label>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs font-mono text-zinc-200 focus:outline-none focus:border-zinc-600"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-400 mb-1">API Secret (Masked)</label>
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs font-mono text-zinc-200 focus:outline-none focus:border-zinc-600"
            />
          </div>
          <button
            type="button"
            onClick={() => alert('Mock Connection Successful: Delta API Testnet latency 24ms (Simulated).')}
            className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-300 rounded-lg text-xs font-semibold"
          >
            Test Connection
          </button>
        </div>
      </div>

      {/* Risk Management Configuration */}
      <form onSubmit={handleSave} className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-5 space-y-4">
        <h2 className="text-base font-bold text-zinc-100">Algorithmic Risk Parameters</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-zinc-400 mb-1">Simulated Capital ($)</label>
            <input
              type="number"
              value={settings.capital}
              onChange={(e) => updateSettings({ capital: Number(e.target.value) })}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 font-mono text-zinc-200"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1">Risk Per Trade (%)</label>
            <input
              type="number"
              step="0.1"
              value={settings.riskPerTradePct}
              onChange={(e) => updateSettings({ riskPerTradePct: Number(e.target.value) })}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 font-mono text-zinc-200"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1">Max Daily Loss (%)</label>
            <input
              type="number"
              step="0.1"
              value={settings.maxDailyLossPct}
              onChange={(e) => updateSettings({ maxDailyLossPct: Number(e.target.value) })}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 font-mono text-zinc-200"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1">Max Concurrent Trades</label>
            <input
              type="number"
              value={settings.maxConcurrentTrades}
              onChange={(e) => updateSettings({ maxConcurrentTrades: Number(e.target.value) })}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 font-mono text-zinc-200"
            />
          </div>
          <div>
            <label className="block text-zinc-400 mb-1">Maximum Leverage</label>
            <input
              type="number"
              value={settings.maxLeverage}
              onChange={(e) => updateSettings({ maxLeverage: Number(e.target.value) })}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 font-mono text-zinc-200"
            />
          </div>
        </div>

        <button
          type="submit"
          className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold rounded-xl text-xs transition"
        >
          Save Configuration
        </button>
      </form>
    </div>
  );
}