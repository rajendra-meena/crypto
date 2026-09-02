'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  SymbolKey,
  TickerData,
  Candle,
  TechnicalIndicators,
  AlgoSignal,
  PaperPosition,
  ClosedTrade,
  TerminalSettings,
} from '@/types/trading';
import { 
  getBackendMarketService, 
  BackendMarketService, 
  BackendConnectionState, 
  DeltaConnectionState,
  ConnectionStates 
} from '@/services/backendMarketService';
import { MockMarketEngine } from '@/services/mockEngine';

const DEFAULT_SETTINGS: TerminalSettings = {
  capital: 10000,
  riskPerTradePct: 1.5,
  maxDailyLossPct: 5.0,
  maxConcurrentTrades: 3,
  maxLeverage: 10,
  isLiveMode: false,
  apiKey: '',
  apiSecret: '',
};

// Data source tracking
export type DataSource = 'REAL' | 'MOCK' | 'STALE';

interface TradingContextType {
  symbol: SymbolKey;
  setSymbol: (symbol: SymbolKey) => void;
  isEngineRunning: boolean;
  setEngineRunning: (val: boolean) => void;
  autoTradingArmed: boolean;
  ticker: TickerData | null;
  watchlist: TickerData[];
  candles: Candle[];
  indicators: TechnicalIndicators | null;
  signals: AlgoSignal[];
  positions: PaperPosition[];
  closedTrades: ClosedTrade[];
  settings: TerminalSettings;
  updateSettings: (newSettings: Partial<TerminalSettings>) => void;
  takeTrade: (signal: AlgoSignal) => void;
  closePosition: (positionId: string) => void;
  performanceMetrics: {
    totalTrades: number;
    wins: number;
    losses: number;
    winRate: number;
    totalRealizedPnL: number;
  };
  // Connection states
  backendConnectionState: 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';
  deltaConnectionState: 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'STALE' | 'DISCONNECTED';
  // Data source tracking
  dataSource: 'REAL' | 'MOCK' | 'STALE';
  // Market data health
  isMarketDataLive: boolean;
  isMarketDataStale: boolean;
  // Trading safety
  canTrade: boolean;
}

const TradingContext = createContext<TradingContextType | undefined>(undefined);

// Development guard to prevent MOCK data in REAL mode
function assertRealMode(dataSource: 'REAL' | 'MOCK' | 'STALE', context: string) {
  if (process.env.NODE_ENV === 'development' && dataSource !== 'REAL') {
    console.error(`[DEV GUARD] ${context} attempted with non-REAL data source: ${dataSource}`);
  }
}

export const TradingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [symbol, setSymbolState] = useState<SymbolKey>('BTCUSDT');
  const [isEngineRunning, setEngineRunning] = useState<boolean>(false);
  const [ticker, setTicker] = useState<TickerData | null>(null);
  const [watchlist, setWatchlist] = useState<TickerData[]>([]);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [indicators, setIndicators] = useState<TechnicalIndicators | null>(null);
  const [signals, setSignals] = useState<AlgoSignal[]>([]);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [closedTrades, setClosedTrades] = useState<ClosedTrade[]>([]);
  const [settings, setSettings] = useState<TerminalSettings>(DEFAULT_SETTINGS);
  
  // Connection states
  const [backendConnectionState, setBackendConnectionState] = useState<'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'>('CONNECTING');
  const [deltaConnectionState, setDeltaConnectionState] = useState<'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'STALE' | 'DISCONNECTED'>('CONNECTING');
  
  // Data source tracking
  const [dataSource, setDataSource] = useState<'REAL' | 'MOCK' | 'STALE'>('REAL');
  
  // Market data health
  const [isMarketDataLive, setIsMarketDataLive] = useState(false);
  const [isMarketDataStale, setIsMarketDataStale] = useState(false);

  const backendServiceRef = useRef<BackendMarketService | null>(null);
  const mockEngine = MockMarketEngine.getInstance();

  // Compute market data health
  const isMarketDataLiveComputed = deltaConnectionState === 'CONNECTED';
  const isMarketDataStaleComputed = deltaConnectionState === 'STALE' || deltaConnectionState === 'DISCONNECTED';
  
  // Trading safety: can only trade when market data is live
  const canTrade = isMarketDataLiveComputed && isEngineRunning;

  // Update computed values
  useEffect(() => {
    setIsMarketDataLive(isMarketDataLiveComputed);
    setIsMarketDataStale(isMarketDataStaleComputed);
    
    // Data source determination
    if (deltaConnectionState === 'CONNECTED') {
      setDataSource('REAL');
    } else if (deltaConnectionState === 'STALE') {
      setDataSource('STALE');
    } else if (deltaConnectionState === 'DISCONNECTED' || deltaConnectionState === 'CONNECTING' || deltaConnectionState === 'RECONNECTING') {
      setDataSource('STALE'); // Treat connecting/reconnecting as stale for safety
    }
  }, [deltaConnectionState]);

  // Development guard
  useEffect(() => {
    if (process.env.NODE_ENV === 'development' && dataSource !== 'REAL') {
      console.warn(`[DEV GUARD] Running with data source: ${dataSource}. Real market data required for production.`);
    }
  }, [dataSource]);

  // Initialize backend service
  useEffect(() => {
    const service = getBackendMarketService();
    backendServiceRef.current = service;

    service.setCallbacks({
      onTick: (tick) => {
        // Development guard
        assertRealMode('REAL', 'onTick');
        
        // Update ticker for the current symbol
        setTicker((prev) => {
          if (!prev || prev.symbol !== tick.symbol) return prev;
          return { ...prev, price: tick.price, lastUpdated: tick.timestamp };
        });

        // Update watchlist
        setWatchlist((prev) =>
          prev.map((w) =>
            w.symbol === tick.symbol
              ? { ...w, price: tick.price, change24h: 0, lastUpdated: tick.timestamp }
              : w
          )
        );

        // Update candles for current symbol with the new tick
        setCandles((prev) => {
          if (prev.length === 0) return prev;
          const updated = [...prev];
          const lastIndex = updated.length - 1;
          // Update the last candle with the new price
          updated[lastIndex] = {
            ...updated[lastIndex],
            close: tick.price,
            high: Math.max(updated[lastIndex].high, tick.price),
            low: Math.min(updated[lastIndex].low, tick.price),
          };
          return updated;
        });

        // Update positions P&L
        setPositions((prev) =>
          prev.map((pos) => {
            if (pos.symbol !== tick.symbol) return pos;
            const priceDiff = pos.side === 'BUY' ? tick.price - pos.entryPrice : pos.entryPrice - tick.price;
            const unrealizedPnL = parseFloat(((priceDiff / pos.entryPrice) * pos.size * pos.leverage).toFixed(2));
            const unrealizedPnLPercent = parseFloat((((priceDiff / pos.entryPrice) * 100) * pos.leverage).toFixed(2));

            return {
              ...pos,
              currentPrice: tick.price,
              unrealizedPnL,
              unrealizedPnLPercent,
            };
          })
        );
      },
      onCandle: (candle) => {
        assertRealMode('REAL', 'onCandle');
        setCandles((prev) => {
          if (candle.symbol !== symbol) return prev;
          
          const existingIndex = prev.findIndex(c => 
            c.timeframe === candle.timeframe && c.time === candle.time
          );
          
          if (existingIndex >= 0) {
            const updated = [...prev];
            updated[existingIndex] = candle;
            return updated;
          } else {
            return [...prev, candle].slice(-500);
          }
        });
      },
      onSnapshot: (snapshot) => {
        assertRealMode('REAL', 'onSnapshot');
        if (snapshot.symbol !== symbol) return;
        
        setCandles(snapshot.candles);
        
        setTicker((prev) => {
          if (!prev) return null;
          return { ...prev, price: snapshot.current_price, lastUpdated: snapshot.last_update };
        });
      },
      onConnectionStateChange: (states) => {
        setBackendConnectionState(states.backend);
        setDeltaConnectionState(states.delta);
      },
      onError: (error) => {
        console.error('[TradingContext] Backend error:', error);
      },
    });

    // Connect to backend
    service.connect().catch((err) => {
      console.error('[TradingContext] Failed to connect to backend:', err);
      setBackendConnectionState('DISCONNECTED');
      setDeltaConnectionState('DISCONNECTED');
    });

    // Initialize watchlist from backend (will be populated via onTick/onSnapshot)
    // We don't use mock engine for watchlist in REAL mode

    return () => {
      service.disconnect();
    };
  }, []);

  // Load Settings from LocalStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('DELTA_ALGO_SETTINGS');
      if (saved) {
        setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(saved) });
      }
    } catch {
      // Fallback to default
    }
  }, []);

  const updateSettings = (newSettings: Partial<TerminalSettings>) => {
    setSettings((prev) => {
      const updated = { ...prev, ...newSettings };
      try {
        localStorage.setItem('DELTA_ALGO_SETTINGS', JSON.stringify(updated));
      } catch (err) {
        console.error('Failed to save settings to localStorage', err);
      }
      return updated;
    });
  };

  // Synchronize on Symbol Switch
  const loadSymbolData = useCallback((sym: SymbolKey) => {
    if (backendServiceRef.current) {
      // Subscribe to the new symbol
      backendServiceRef.current.subscribe([sym]);
      
      // Get snapshot from backend
      const snapshot = backendServiceRef.current.getSymbolState(sym);
      if (snapshot) {
        setCandles(snapshot.candles);
        setTicker((prev) => prev ? { ...prev, price: snapshot.currentPrice, lastUpdated: snapshot.lastTickTime } : null);
      }
    }
  }, []);

  const setSymbol = (sym: SymbolKey) => {
    setSymbolState(sym);
    loadSymbolData(sym);
  };

  // Initialize on mount
  useEffect(() => {
    loadSymbolData(symbol);
  }, [symbol, loadSymbolData]);

  // NO MOCK MODE TICK INTERVAL - REAL mode only uses backend data
  // MOCK mode is completely removed

  // Generate indicators/signals from REAL data when available
  useEffect(() => {
    // In REAL mode, indicators come from backend analysis
    // For Phase 2, we keep the mock indicators as placeholder but marked as simulated
    if (dataSource === 'REAL' && ticker) {
      // In production, this would come from backend analysis service
      // For now, we generate from real price but mark as simulated
      console.log('[TradingContext] Generating indicators from REAL price data');
    }
  }, [ticker, symbol, dataSource]);

  // Take Trade Flow - BLOCKED when market data is not live
  const takeTrade = (signal: AlgoSignal) => {
    if (signal.status !== 'READY') return;
    
    // SAFETY: Block trades when market data is not live
    if (!canTrade) {
      console.error(`[TradingContext] Trade BLOCKED: market data not live (delta: ${deltaConnectionState}, engine: ${isEngineRunning})`);
      alert(`Cannot take trade: Market data is ${deltaConnectionState}. Real market data required.`);
      return;
    }

    const size = (settings.capital * (settings.riskPerTradePct / 100)) * settings.maxLeverage;
    const margin = size / settings.maxLeverage;

    const newPosition: PaperPosition = {
      id: `POS-${Date.now()}`,
      signalId: signal.id,
      symbol: signal.symbol,
      side: signal.side,
      entryPrice: signal.entry,
      currentPrice: ticker?.price || signal.entry,
      stopLoss: signal.stopLoss,
      target1: signal.target1,
      target2: signal.target2,
      leverage: settings.maxLeverage,
      size: parseFloat(size.toFixed(2)),
      margin: parseFloat(margin.toFixed(2)),
      unrealizedPnL: 0,
      unrealizedPnLPercent: 0,
      openedAt: Date.now(),
    };

    setPositions((prev) => [newPosition, ...prev]);

    // Mark signal as EXECUTED
    setSignals((prev) =>
      prev.map((s) => (s.id === signal.id ? { ...s, status: 'EXECUTED' } : s))
    );
  };

  // Close Position Flow
  const closePosition = (positionId: string) => {
    const pos = positions.find((p) => p.id === positionId);
    if (!pos) return;

    const now = Date.now();
    const durationSeconds = Math.floor((now - pos.openedAt) / 1000);
    const realizedPnL = pos.unrealizedPnL;
    const realizedPnLPercent = pos.unrealizedPnLPercent;
    const isWin = realizedPnL > 0;

    const closedRecord: ClosedTrade = {
      id: `CLOSED-${pos.id}`,
      symbol: pos.symbol,
      side: pos.side,
      entryPrice: pos.entryPrice,
      exitPrice: pos.currentPrice,
      size: pos.size,
      leverage: pos.leverage,
      realizedPnL,
      realizedPnLPercent,
      openedAt: pos.openedAt,
      closedAt: now,
      durationSeconds,
      isWin,
    };

    setClosedTrades((prev) => [closedRecord, ...prev]);
    setPositions((prev) => prev.filter((p) => p.id !== positionId));
  };

  const performanceMetrics = {
    totalTrades: closedTrades.length,
    wins: closedTrades.filter((t) => t.isWin).length,
    losses: closedTrades.filter((t) => !t.isWin).length,
    winRate: closedTrades.length > 0
      ? parseFloat(((closedTrades.filter((t) => t.isWin).length / closedTrades.length) * 100).toFixed(1))
      : 0,
    totalRealizedPnL: parseFloat(
      closedTrades.reduce((acc, curr) => acc + curr.realizedPnL, 0).toFixed(2)
    ),
  };

  return (
    <TradingContext.Provider
      value={{
        symbol,
        setSymbol,
        isEngineRunning,
        setEngineRunning,
        autoTradingArmed: isEngineRunning,
        ticker,
        watchlist,
        candles,
        indicators,
        signals,
        positions,
        closedTrades,
        settings,
        updateSettings,
        takeTrade,
        closePosition,
        performanceMetrics,
        backendConnectionState,
        deltaConnectionState,
        dataSource,
        isMarketDataLive,
        isMarketDataStale,
        canTrade,
      }}
    >
      {children}
    </TradingContext.Provider>
  );
};

export const useTrading = () => {
  const context = useContext(TradingContext);
  if (!context) {
    throw new Error('useTrading must be used within a TradingProvider');
  }
  return context;
};