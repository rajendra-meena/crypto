'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlgoSignal,
  BackendAnalysis,
  Candle,
  ClosedTrade,
  PaperPosition,
  RiskSnapshot,
  SymbolKey,
  TechnicalIndicators,
  TerminalSettings,
  TickerData,
} from '@/types/trading';
import { BackendMarketService, getBackendMarketService } from '@/services/backendMarketService';
import {
  closeTradingPosition,
  getTradingState,
  setTradingEngine,
  updateTradingSettings,
} from '@/services/tradingApiService';

const ALL_SYMBOLS: SymbolKey[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT'];

const DEFAULT_SETTINGS: TerminalSettings = {
  capital: 10000,
  riskPerTradePct: 0.75,
  maxDailyLossPct: 2.5,
  maxPortfolioRiskPct: 1.5,
  maxConcurrentTrades: 2,
  maxLeverage: 3,
  minSetupScore: 72,
  maxTradesPerDay: 6,
  maxConsecutiveLosses: 3,
  cooldownMinutes: 20,
  atrStopMultiplier: 1.3,
  targetRR: 2.2,
  feeRatePct: 0.05,
  slippagePct: 0.02,
  maxEntryDriftPct: 0.35,
  minStopPct: 0.3,
  maxStopPct: 1.8,
  breakevenAtR: 1,
  trailingStartR: 1.5,
  trailingDistanceR: 0.75,
  maxHoldMinutes: 240,
  minAtrPct: 0.18,
  maxAtrPct: 3.5,
  isLiveMode: false,
  apiKey: '',
  apiSecret: '',
};

const EMPTY_RISK: RiskSnapshot = {
  todayTrades: 0,
  todayRealizedPnL: 0,
  consecutiveLosses: 0,
  openPositions: 0,
  openRisk: 0,
  maxDailyLoss: 0,
  maxPortfolioRisk: 0,
  blocked: false,
  blockReason: null,
};

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

function settingsFromApi(raw?: Record<string, unknown>): TerminalSettings {
  const next = { ...DEFAULT_SETTINGS } as Record<string, unknown>;
  if (raw) {
    Object.keys(DEFAULT_SETTINGS).forEach((key) => {
      if (raw[key] !== undefined) next[key] = raw[key];
    });
  }
  // Real exchange execution is intentionally disabled in this app path.
  next.isLiveMode = false;
  next.apiKey = '';
  next.apiSecret = '';
  return next as unknown as TerminalSettings;
}

function analysisToIndicators(analysis?: BackendAnalysis): TechnicalIndicators | null {
  if (!analysis) return null;
  const trend = analysis.trend === 'BULLISH' ? 'BULLISH' : analysis.trend === 'BEARISH' ? 'BEARISH' : 'NEUTRAL';
  const structure = analysis.setup === 'BREAKOUT' || analysis.setup === 'BREAKDOWN'
    ? 'BREAKOUT'
    : analysis.trend === 'BULLISH'
      ? 'TRENDING_UP'
      : analysis.trend === 'BEARISH'
        ? 'TRENDING_DOWN'
        : 'RANGE_BOUND';
  return {
    rsi: analysis.rsi,
    macd: { macdLine: 0, signalLine: 0, histogram: 0 },
    emaTrend: analysis.trend === 'BULLISH' ? 'ABOVE_200_EMA' : analysis.trend === 'BEARISH' ? 'BELOW_200_EMA' : 'CONSOLIDATING',
    support: analysis.support,
    resistance: analysis.resistance,
    marketTrend: trend,
    momentum: analysis.trigger === 'NONE' ? 'WEAK' : 'STRONG',
    volatility: analysis.atrPct > 1 ? 'HIGH' : analysis.atrPct < 0.25 ? 'LOW' : 'NORMAL',
    volumeStrength: analysis.volumeRatio >= 1.2 ? 'HIGH' : analysis.volumeRatio < 0.8 ? 'LOW' : 'AVERAGE',
    marketStructure: structure,
    confidence: analysis.setupScore,
    finalBias: analysis.bias,
  };
}

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
  analyses: BackendAnalysis[];
  selectedAnalysis: BackendAnalysis | null;
  signals: AlgoSignal[];
  positions: PaperPosition[];
  closedTrades: ClosedTrade[];
  executedSignalIds: string[];
  riskSnapshot: RiskSnapshot;
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

export const TradingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [symbol, setSymbolState] = useState<SymbolKey>('BTCUSDT');
  const symbolRef = useRef<SymbolKey>('BTCUSDT');
  const backendServiceRef = useRef<BackendMarketService | null>(null);

  const [isEngineRunning, setEngineRunningState] = useState(false);
  const [ticker, setTicker] = useState<TickerData>(() => createTicker('BTCUSDT'));
  const [watchlist, setWatchlist] = useState<TickerData[]>(() => ALL_SYMBOLS.map((s) => createTicker(s)));
  const [candles, setCandles] = useState<Candle[]>([]);
  const [analyses, setAnalyses] = useState<BackendAnalysis[]>([]);
  const [signals, setSignals] = useState<AlgoSignal[]>([]);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [closedTrades, setClosedTrades] = useState<ClosedTrade[]>([]);
  const [executedSignalIds, setExecutedSignalIds] = useState<string[]>([]);
  const [riskSnapshot, setRiskSnapshot] = useState<RiskSnapshot>(EMPTY_RISK);
  const [settings, setSettings] = useState<TerminalSettings>(DEFAULT_SETTINGS);

  const [backendConnectionState, setBackendConnectionState] = useState<'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'>('CONNECTING');
  const [deltaConnectionState, setDeltaConnectionState] = useState<'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'STALE' | 'DISCONNECTED'>('CONNECTING');

  const selectedAnalysis = useMemo(
    () => analyses.find((item) => item.symbol === symbol) || null,
    [analyses, symbol],
  );
  const indicators = useMemo(() => analysisToIndicators(selectedAnalysis || undefined), [selectedAnalysis]);
  const isMarketDataLive = deltaConnectionState === 'CONNECTED';
  const isMarketDataStale = deltaConnectionState === 'STALE' || deltaConnectionState === 'DISCONNECTED';
  const dataSource: 'REAL' | 'MOCK' | 'STALE' = isMarketDataLive ? 'REAL' : 'STALE';
  const canTrade = isMarketDataLive && isEngineRunning && !riskSnapshot.blocked;

  const applyTradingState = useCallback((state: Awaited<ReturnType<typeof getTradingState>>) => {
    setEngineRunningState(Boolean(state.engine_running));
    setPositions(Array.isArray(state.positions) ? state.positions : []);
    setClosedTrades(Array.isArray(state.closed_trades) ? state.closed_trades : []);
    setExecutedSignalIds(Array.isArray(state.executed_signal_ids) ? state.executed_signal_ids : []);
    setSignals(Array.isArray(state.signals) ? state.signals : []);
    setAnalyses(Array.isArray(state.analyses) ? state.analyses : []);
    if (state.risk) setRiskSnapshot(state.risk);
    if (state.settings) setSettings(settingsFromApi(state.settings));

    const analysisMap = new Map((state.analyses || []).map((item) => [item.symbol, item]));
    const signalMap = new Map((state.signals || []).map((item) => [item.symbol, item]));
    setWatchlist((prev) => prev.map((coin) => {
      const analysis = analysisMap.get(coin.symbol);
      const signal = signalMap.get(coin.symbol);
      let signalState = analysis?.status || 'WATCHING';
      if (signal?.status === 'EXECUTED') signalState = 'EXECUTED';
      else if (signal?.status === 'READY') signalState = 'READY';
      else if (signal?.status === 'BLOCKED' || signal?.status === 'FILTERED') signalState = signal.status;
      return {
        ...coin,
        signalState,
        confidence: analysis?.setupScore || signal?.confidence || 0,
      };
    }));
  }, []);

  const refreshTradingState = useCallback(async () => {
    const state = await getTradingState();
    applyTradingState(state);
  }, [applyTradingState]);

  useEffect(() => {
    let active = true;
    const sync = async () => {
      try {
        const state = await getTradingState();
        if (active) applyTradingState(state);
      } catch (error) {
        console.error('[TradingContext] Trading API state sync failed:', error);
      }
    };
    void sync();
    const timer = window.setInterval(() => void sync(), 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [applyTradingState]);

  useEffect(() => {
    const service = getBackendMarketService();
    backendServiceRef.current = service;
    service.setCallbacks({
      onTick: (tick) => {
        const tickSymbol = tick.symbol as SymbolKey;
        setWatchlist((prev) => prev.map((coin) =>
          coin.symbol === tickSymbol ? { ...coin, price: tick.price, lastUpdated: tick.timestamp } : coin
        ));
        if (symbolRef.current === tickSymbol) {
          setTicker((prev) => ({
            ...(prev?.symbol === tickSymbol ? prev : createTicker(tickSymbol)),
            price: tick.price,
            lastUpdated: tick.timestamp,
          }));
          setCandles((prev) => {
            const updated = [...prev];
            const indices = updated
              .map((c, index) => ({ c, index }))
              .filter(({ c }) => c.symbol === tickSymbol && c.timeframe === '1m');
            const target = indices.at(-1)?.index;
            if (target === undefined) return prev;
            updated[target] = {
              ...updated[target],
              close: tick.price,
              high: Math.max(updated[target].high, tick.price),
              low: Math.min(updated[target].low, tick.price),
            };
            return updated;
          });
        }
      },
      onCandle: (candle) => {
        if (candle.symbol !== symbolRef.current) return;
        setCandles((prev) => {
          const index = prev.findIndex((c) => c.timeframe === candle.timeframe && c.time === candle.time);
          if (index >= 0) {
            const updated = [...prev];
            updated[index] = candle;
            return updated;
          }
          return [...prev, candle].slice(-500);
        });
      },
      onSnapshot: (snapshot) => {
        const snapshotSymbol = snapshot.symbol as SymbolKey;
        setWatchlist((prev) => prev.map((coin) =>
          coin.symbol === snapshotSymbol
            ? { ...coin, price: snapshot.current_price, lastUpdated: snapshot.last_update }
            : coin
        ));
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
      onError: (error) => console.error('[TradingContext] Market WebSocket error:', error),
    });

    service.subscribe(ALL_SYMBOLS);
    service.connect().catch((error) => {
      console.error('[TradingContext] Backend market connection failed:', error);
      setBackendConnectionState('DISCONNECTED');
      setDeltaConnectionState('DISCONNECTED');
    });
    return () => service.disconnect();
  }, []);

  const loadSymbolData = useCallback((sym: SymbolKey) => {
    const service = backendServiceRef.current;
    if (!service) return;
    service.subscribe([sym]);
    const snapshot = service.getSymbolState(sym);
    if (snapshot) {
      setCandles(snapshot.candles);
      const existing = watchlist.find((coin) => coin.symbol === sym);
      setTicker({ ...(existing || createTicker(sym)), price: snapshot.currentPrice, lastUpdated: snapshot.lastTickTime });
    } else {
      setCandles([]);
      setTicker(watchlist.find((coin) => coin.symbol === sym) || createTicker(sym));
    }
  }, [watchlist]);

  const setSymbol = useCallback((sym: SymbolKey) => {
    symbolRef.current = sym;
    setSymbolState(sym);
    loadSymbolData(sym);
  }, [loadSymbolData]);

  const setEngineRunning = useCallback((val: boolean) => {
    setEngineRunningState(val);
    void setTradingEngine(val)
      .then((running) => setEngineRunningState(running))
      .then(() => refreshTradingState())
      .catch((error) => {
        console.error('[TradingContext] Failed to change engine state:', error);
        void refreshTradingState();
      });
  }, [refreshTradingState]);

  const updateSettings = useCallback((newSettings: Partial<TerminalSettings>) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
    void updateTradingSettings(newSettings)
      .then(() => refreshTradingState())
      .catch((error) => {
        console.error('[TradingContext] Failed to update backend settings:', error);
        void refreshTradingState();
      });
  }, [refreshTradingState]);

  const takeTrade = useCallback((_signal: AlgoSignal) => {
    console.warn('[TradingContext] Manual signal execution is disabled. Backend engine owns all entries.');
  }, []);

  const closePosition = useCallback((positionId: string) => {
    void closeTradingPosition(positionId)
      .then(() => refreshTradingState())
      .catch((error) => console.error('[TradingContext] Manual backend close failed:', error));
  }, [refreshTradingState]);

  const performanceMetrics = useMemo(() => {
    const wins = closedTrades.filter((trade) => trade.isWin).length;
    const totalTrades = closedTrades.length;
    return {
      totalTrades,
      wins,
      losses: totalTrades - wins,
      winRate: totalTrades ? Number(((wins / totalTrades) * 100).toFixed(1)) : 0,
      totalRealizedPnL: Number(closedTrades.reduce((sum, trade) => sum + trade.realizedPnL, 0).toFixed(2)),
    };
  }, [closedTrades]);

  return (
    <TradingContext.Provider value={{
      symbol,
      setSymbol,
      isEngineRunning,
      setEngineRunning,
      autoTradingArmed: isEngineRunning,
      ticker,
      watchlist,
      candles,
      indicators,
      analyses,
      selectedAnalysis,
      signals,
      positions,
      closedTrades,
      executedSignalIds,
      riskSnapshot,
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
    }}>
      {children}
    </TradingContext.Provider>
  );
};

export const useTrading = () => {
  const context = useContext(TradingContext);
  if (!context) throw new Error('useTrading must be used within a TradingProvider');
  return context;
};
