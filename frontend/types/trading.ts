export type SymbolKey = 'BTCUSDT' | 'ETHUSDT' | 'SOLUSDT' | 'XRPUSDT' | 'BNBUSDT';

export type SignalStatus = 'WATCHING' | 'READY' | 'EXECUTED' | 'FILTERED' | 'BLOCKED' | 'EXPIRED' | 'INVALIDATED';
export type TradeSide = 'BUY' | 'SELL';
export type MarketTrend = 'STRONG_BULLISH' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'STRONG_BEARISH';

export interface Candle {
  symbol: SymbolKey;
  timeframe: string;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_complete?: boolean;
}

export interface TickerData {
  symbol: SymbolKey;
  price: number;
  high24h: number;
  low24h: number;
  volume24h: number;
  change24h: number;
  signalState: SignalStatus;
  confidence: number;
  lastUpdated: number;
}

export interface MarketTick {
  symbol: SymbolKey;
  exchange_symbol: string;
  product_id: number;
  price: number;
  timestamp: number;
  volume?: number;
}

export interface TechnicalIndicators {
  rsi: number;
  macd: {
    macdLine: number;
    signalLine: number;
    histogram: number;
  };
  emaTrend: 'ABOVE_200_EMA' | 'BELOW_200_EMA' | 'CONSOLIDATING';
  support: number;
  resistance: number;
  marketTrend: MarketTrend;
  momentum: 'STRONG' | 'MODERATE' | 'WEAK';
  volatility: 'HIGH' | 'NORMAL' | 'LOW';
  volumeStrength: 'HIGH' | 'AVERAGE' | 'LOW';
  marketStructure: 'BREAKOUT' | 'RANGE_BOUND' | 'TRENDING_UP' | 'TRENDING_DOWN';
  confidence: number;
  finalBias: 'BUY' | 'SELL' | 'WAIT';
}

export interface AlgoSignal {
  id: string;
  symbol: SymbolKey;
  side: TradeSide;
  timeframe: string;
  entry: number;
  stopLoss: number;
  target1: number;
  target2: number;
  riskReward: string;
  confidence: number;
  generatedTime: string;
  reason: string;
  status: SignalStatus;
}

export interface PaperPosition {
  id: string;
  signalId?: string;
  symbol: SymbolKey;
  side: TradeSide;
  entryPrice: number;
  currentPrice: number;
  stopLoss: number;
  target1: number;
  target2: number;
  leverage: number;
  size: number;
  margin: number;
  unrealizedPnL: number;
  unrealizedPnLPercent: number;
  openedAt: number;
}

export interface ClosedTrade {
  id: string;
  symbol: SymbolKey;
  side: TradeSide;
  entryPrice: number;
  exitPrice: number;
  size: number;
  leverage: number;
  realizedPnL: number;
  realizedPnLPercent: number;
  openedAt: number;
  closedAt: number;
  durationSeconds: number;
  isWin: boolean;
}

export interface TerminalSettings {
  capital: number;
  riskPerTradePct: number;
  maxDailyLossPct: number;
  maxConcurrentTrades: number;
  maxLeverage: number;
  isLiveMode: boolean;
  apiKey: string;
  apiSecret: string;
}
