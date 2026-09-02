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
} from '@/services/backendMarketService';

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

const ALL_SYMBOLS: SymbolKey[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT'];

const createTicker = (symbol: SymbolKey, price = 0, lastUpdated = 0): TickerData => ({
  symbol,
  price,
  high24h: 0,
  low24h: 0,
  volume24h: 0,
  change24h: 0,
  signalState: 'WATCHING',
  confidence: 0,
  lastUpdated,
});

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
  backendConnectionState: 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';
  deltaConnectionState: 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'STALE' | 'DISCONNECTED';
  dataSource: 'REAL' | 'MOCK' | 'STALE';
  isMarketDataLive: boolean;
  isMarketDataStale: boolean;
  canTrade: boolean;
}

const TradingContext = createContext<TradingContextType | undefined>(undefined);

function assertRealMode(dataSource: 'REAL' | 'MOCK' | 'STALE', context: string) {
  if (process.env.NODE_ENV === 'development' && dataSource !== 'REAL') {
    console.error(`[DEV GUARD] ${context} attempted with non-REAL data source: ${dataSource}`);
  }
}

export const TradingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [symbol, setSymbolState] = useState<SymbolKey>('BTCUSDT');
  const symbolRef = useRef<SymbolKey>('BTCUSDT');
  const [isEngineRunning, setEngineRunning] = useState(false);
  const [ticker, setTicker] = useState<TickerData>(() => createTicker('BTCUSDT'));
  const [watchlist, setWatchlist] = useState<TickerData[]>(() => ALL_SYMBOLS.map((s) => createTicker(s)));
  const [candles, setCandles] = useState<Candle[]>([]);
  const [indicators] = useState<TechnicalIndicators | null>(null);
  const [signals, setSignals] = useState<AlgoSignal[]>([]);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [closedTrades, setClosedTrades] = useState<ClosedTrade[]>([]);
  const [settings, setSettings] = useState<TerminalSettings>(DEFAULT_SETTINGS);

  const [backendConnectionState, setBackendConnectionState] = useState<'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'>('CONNECTING');
  const [deltaConnectionState, setDeltaConnectionState] = useState<'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'STALE' | 'DISCONNECTED'>('CONNECTING');
  const [dataSource, setDataSource] = useState<'REAL' | 'MOCK' | 'STALE'>('REAL');
  const [isMarketDataLive, setIsMarketDataLive] = useState(false);
  const [isMarketDataStale, setIsMarketDataStale] = useState(false);

  const backendServiceRef = useRef<BackendMarketService | null>(null);

  const isMarketDataLiveComputed = deltaConnectionState === 'CONNECTED';
  const isMarketDataStaleComputed = deltaConnectionState === 'STALE' || deltaConnectionState === 'DISCONNECTED';
  const canTrade = isMarketDataLiveComputed && isEngineRunning;

  useEffect(() => {
    setIsMarketDataLive(isMarketDataLiveComputed);
    setIsMarketDataStale(isMarketDataStaleComputed);
    setDataSource(deltaConnectionState === 'CONNECTED' ? 'REAL' : 'STALE');
  }, [deltaConnectionState, isMarketDataLiveComputed, isMarketDataStaleComputed]);

  useEffect(() => {
    if (process.env.NODE_ENV === 'development' && dataSource !== 'REAL') {
      console.warn(`[DEV GUARD] Running with data source: ${dataSource}. Real market data required for production.`);
    }
  }, [dataSource]);

  useEffect(() => {
    const service = getBackendMarketService();
    backendServiceRef.current = service;

    service.setCallbacks({
      onTick: (tick) => {
        assertRealMode('REAL', 'onTick');
        const tickSymbol = tick.symbol as SymbolKey;

        setWatchlist((prev) => {
          const exists = prev.some((w) => w.symbol === tickSymbol);
          if (!exists) return [...prev, createTicker(tickSymbol, tick.price, tick.timestamp)];
          return prev.map((w) =>
            w.symbol === tickSymbol
              ? { ...w, price: tick.price, lastUpdated: tick.timestamp }
              : w
          );
        });

        if (symbolRef.current === tickSymbol) {
          setTicker((prev) => ({
            ...(prev?.symbol === tickSymbol ? prev : createTicker(tickSymbol)),
            price: tick.price,
            lastUpdated: tick.timestamp,
          }));

          setCandles((prev) => {
            if (prev.length === 0) return prev;
            const updated = [...prev];
            const lastIndex = updated.length - 1;
            updated[lastIndex] = {
              ...updated[lastIndex],
              close: tick.price,
              high: Math.max(updated[lastIndex].high, tick.price),
              low: Math.min(updated[lastIndex].low, tick.price),
            };
            return updated;
          });
        }

        setPositions((prev) =>
          prev.map((pos) => {
            if (pos.symbol !== tickSymbol) return pos;
            const priceDiff = pos.side === 'BUY' ? tick.price - pos.entryPrice : pos.entryPrice - tick.price;
            const unrealizedPnL = parseFloat(((priceDiff / pos.entryPrice) * pos.size * pos.leverage).toFixed(2));
            const unrealizedPnLPercent = parseFloat((((priceDiff / pos.entryPrice) * 100) * pos.leverage).toFixed(2));
            return { ...pos, currentPrice: tick.price, unrealizedPnL, unrealizedPnLPercent };
          })
        );
      },

      onCandle: (candle) => {
        assertRealMode('REAL', 'onCandle');
        if (candle.symbol !== symbolRef.current) return;

        setCandles((prev) => {
          const existingIndex = prev.findIndex(
            (c) => c.timeframe === candle.timeframe && c.time === candle.time
          );
          if (existingIndex >= 0) {
            const updated = [...prev];
            updated[existingIndex] = candle;
            return updated;
          }
          return [...prev, candle].slice(-500);
        });
      },

      onSnapshot: (snapshot) => {
        assertRealMode('REAL', 'onSnapshot');
        const snapshotSymbol = snapshot.symbol as SymbolKey;

        setWatchlist((prev) =>
          prev.map((w) =>
            w.symbol === snapshotSymbol
              ? { ...w, price: snapshot.current_price, lastUpdated: snapshot.last_update }
              : w
          )
        );

        if (snapshotSymbol !== symbolRef.current) return;
        setCandles(snapshot.candles);
        setTicker((prev) => ({
          ...(prev?.symbol === snapshotSymbol ? prev : createTicker(snapshotSymbol)),
          price: snapshot.current_price,
          lastUpdated: snapshot.last_update,
        }));
      },

      onConnectionStateChange: (states) => {
        setBackendConnectionState(states.backend);
        setDeltaConnectionState(states.delta);
      },

      onError: (error) => {
        console.error('[TradingContext] Backend error:', error);
      },
    });

    // Subscribe to all watchlist symbols so every card receives live data.
    service.subscribe(ALL_SYMBOLS);

    service.connect().catch((err) => {
      console.error('[TradingContext] Failed to connect to backend:', err);
      setBackendConnectionState('DISCONNECTED');
      setDeltaConnectionState('DISCONNECTED');
    });

    return () => {
      service.disconnect();
    };
  }, []);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('DELTA_ALGO_SETTINGS');
      if (saved) setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(saved) });
    } catch {
      // Keep defaults.
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

  const loadSymbolData = useCallback((sym: SymbolKey) => {
    const service = backendServiceRef.current;
    if (!service) return;

    service.subscribe([sym]);
    const snapshot = service.getSymbolState(sym);
    if (snapshot) {
      setCandles(snapshot.candles);
      setTicker(createTicker(sym, snapshot.currentPrice, snapshot.lastTickTime));
    } else {
      setCandles([]);
      setTicker(createTicker(sym));
    }
  }, []);

  const setSymbol = (sym: SymbolKey) => {
    symbolRef.current = sym;
    setSymbolState(sym);
    loadSymbolData(sym);
  };

  useEffect(() => {
    symbolRef.current = symbol;
    loadSymbolData(symbol);
  }, [symbol, loadSymbolData]);

  useEffect(() => {
    if (dataSource === 'REAL' && ticker) {
      console.log('[TradingContext] Live market data active for', ticker.symbol, ticker.price);
    }
  }, [ticker, dataSource]);

  const takeTrade = (signal: AlgoSignal) => {
    if (signal.status !== 'READY') return;
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
    setSignals((prev) => prev.map((s) => (s.id === signal.id ? { ...s, status: 'EXECUTED' } : s)));
  };

  const closePosition = (positionId: string) => {
    const pos = positions.find((p) => p.id === positionId);
    if (!pos) return;

    const now = Date.now();
    const durationSeconds = Math.floor((now - pos.openedAt) / 1000);
    const realizedPnL = pos.unrealizedPnL;
    const realizedPnLPercent = pos.unrealizedPnLPercent;

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
      isWin: realizedPnL > 0,
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
    totalRealizedPnL: parseFloat(closedTrades.reduce((acc, curr) => acc + curr.realizedPnL, 0).toFixed(2)),
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
  if (!context) throw new Error('useTrading must be used within a TradingProvider');
  return context;
};
