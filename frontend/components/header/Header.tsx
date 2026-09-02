'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useTrading } from '@/context/TradingContext';
import { 
  Activity, 
  Settings, 
  Power, 
  ShieldCheck, 
  ShieldAlert, 
  Zap, 
  Clock 
} from 'lucide-react';

export const Header: React.FC = () => {
  const { 
    isEngineRunning, 
    setEngineRunning, 
    backendConnectionState, 
    deltaConnectionState,
    dataSource,
    isMarketDataLive,
    isMarketDataStale,
    canTrade 
  } = useTrading();
  const [timeStr, setTimeStr] = useState<string>('');

  // Determine connection display states
  const getBackendDisplay = () => {
    switch (backendConnectionState) {
      case 'CONNECTED':
        return { label: 'Backend: CONNECTED', color: 'bg-emerald-500', textColor: 'text-emerald-400' };
      case 'CONNECTING':
        return { label: 'Backend: CONNECTING...', color: 'bg-amber-500 animate-pulse', textColor: 'text-amber-400' };
      case 'RECONNECTING':
        return { label: 'Backend: RECONNECTING...', color: 'bg-amber-500 animate-pulse', textColor: 'text-amber-400' };
      case 'DISCONNECTED':
        return { label: 'Backend: DISCONNECTED', color: 'bg-rose-500', textColor: 'text-rose-400' };
    }
  };

  const getDeltaDisplay = () => {
    switch (deltaConnectionState) {
      case 'CONNECTED':
        return { label: 'Delta Feed: LIVE', color: 'bg-emerald-500', textColor: 'text-emerald-400' };
      case 'CONNECTING':
        return { label: 'Delta Feed: CONNECTING...', color: 'bg-amber-500 animate-pulse', textColor: 'text-amber-400' };
      case 'RECONNECTING':
        return { label: 'Delta Feed: RECONNECTING...', color: 'bg-amber-500 animate-pulse', textColor: 'text-amber-400' };
      case 'STALE':
        return { label: 'Delta Feed: STALE', color: 'bg-amber-500', textColor: 'text-amber-400' };
      case 'DISCONNECTED':
        return { label: 'Delta Feed: DISCONNECTED', color: 'bg-rose-500', textColor: 'text-rose-400' };
    }
  };

  const backendDisplay = getBackendDisplay();
  const deltaDisplay = getDeltaDisplay();

  // Data source badge
  const getDataSourceDisplay = () => {
    switch (dataSource) {
      case 'REAL':
        return { label: 'REAL MARKET DATA', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40', icon: '●' };
      case 'STALE':
        return { label: 'STALE DATA', color: 'bg-amber-500/20 text-amber-400 border-amber-500/40', icon: '◐' };
      case 'MOCK':
        return { label: 'MOCK DATA', color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40', icon: '○' };
    }
  };

  const dataSourceDisplay = getDataSourceDisplay();

  // Engine status with data quality
  const getEngineDisplay = () => {
    if (!isEngineRunning) return { label: 'ENGINE OFF', color: 'bg-zinc-900 border-zinc-700/80 text-zinc-400' };
    if (isMarketDataStale) return { label: 'ENGINE ON · DATA BLOCKED', color: 'bg-amber-500/20 text-amber-400 border-amber-500/40' };
    return { label: 'ENGINE ON · ARMED', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/60' };
  };

  const engineDisplay = getEngineDisplay();

useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setTimeStr(now.toUTCString().replace('GMT', 'UTC'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-16 border-b border-zinc-800/80 bg-zinc-950/70 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
      {/* Brand & Connection */}
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/10">
            <Zap className="h-5 w-5 text-zinc-950 fill-zinc-950" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold tracking-tight text-zinc-100 text-lg">DELTA</span>
              <span className="text-emerald-400 font-extrabold text-sm px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/50">ALGO</span>
            </div>
            <p className="text-[10px] text-zinc-400 font-mono tracking-wide">PHASE 1 TERMINAL</p>
          </div>
        </Link>

        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs">
          <span className={`h-2 w-2 rounded-full ${backendDisplay.color}`} />
          <span className={`text-zinc-300 font-medium ${backendDisplay.textColor}`}>{backendDisplay.label}</span>
          <span className="mx-1 text-zinc-600">|</span>
          <span className={`h-2 w-2 rounded-full ${deltaDisplay.color}`} />
          <span className={`text-zinc-300 font-medium ${deltaDisplay.textColor}`}>{deltaDisplay.label}</span>
        </div>
      </div>

      {/* Center Engine & Mode Controls */}
      <div className="flex items-center gap-4">
        {/* Mode Selector */}
        <div className="flex items-center p-1 rounded-lg bg-zinc-900 border border-zinc-800">
          <button
            onClick={() => setEngineRunning(true)}
            className={`px-3 py-1 rounded text-xs font-semibold transition-all flex items-center gap-1.5 ${
              isEngineRunning
                ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            RUNNING
          </button>
          <button
            onClick={() => setEngineRunning(false)}
            className={`px-3 py-1 rounded text-xs font-semibold transition-all flex items-center gap-1.5 ${
              !isEngineRunning
                ? 'bg-amber-600/30 text-amber-400 border border-amber-500/50 shadow-md shadow-amber-500/10 animate-pulse'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            STOPPED
          </button>
        </div>

        {/* Engine ON/OFF Switch with Data Quality */}
        <button
          onClick={() => setEngineRunning(!isEngineRunning)}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-lg border text-xs font-bold transition-all shadow-md ${engineDisplay.color}`}
        >
          <Power className={`h-3.5 w-3.5 ${isEngineRunning ? 'text-emerald-400' : 'text-zinc-500'}`} />
          <span>{engineDisplay.label}</span>
          {isMarketDataStale && (
            <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 rounded">
              STALE DATA
            </span>
          )}
          {isMarketDataLive && !isMarketDataStale && (
            <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded">
              LIVE
            </span>
          )}
          <span
            className={`h-2 w-2 rounded-full ${isEngineRunning && isMarketDataLive ? 'bg-emerald-400 animate-ping' : 'bg-zinc-600'}`}
          />
        </button>
      </div>

      {/* Right side: Data Source, Clock & Settings */}
      <div className="flex items-center gap-4">
        {/* Data Source Badge */}
        <div className={`hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-bold ${dataSourceDisplay.color}`}>
          <span>{dataSourceDisplay.icon}</span>
          <span>{dataSourceDisplay.label}</span>
        </div>

        {/* Stale Data Warning */}
        {isMarketDataStale && (
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40 text-xs font-bold">
            <Activity className="h-3 w-3 animate-pulse" />
            <span>MARKET DATA STALE — TRADING DISABLED</span>
          </div>
        )}

        <div className="hidden lg:flex items-center gap-2 text-xs font-mono text-zinc-400 bg-zinc-900/80 px-3 py-1 rounded-md border border-zinc-800">
          <Clock className="h-3.5 w-3.5 text-zinc-400" />
          <span>{timeStr || 'Connecting clock...'}</span>
        </div>

        <Link
          href="/settings"
          className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-100 hover:border-zinc-700 transition"
          title="Terminal Settings"
        >
          <Settings className="h-4 w-4" />
        </Link>
      </div>
    </header>
  );
};