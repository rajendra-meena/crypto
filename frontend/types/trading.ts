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
  macd: { macdLine: number; signalLine: number; histogram: number };
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

export interface BackendAnalysis {
  symbol: SymbolKey;
  bias: 'BUY' | 'SELL' | 'WAIT';
  status: SignalStatus;
  setupScore: number;
  timeframe: string;
  trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  mtfTrend?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  setup: 'BREAKOUT' | 'BREAKDOWN' | 'PULLBACK_RECLAIM' | 'PULLBACK_REJECT' | 'NONE';
  trigger: 'LONG_CONFIRM' | 'SHORT_CONFIRM' | 'NONE';
  rsi: number;
  atrPct: number;
  volumeRatio: number;
  bodyQuality?: number;
  support: number;
  resistance: number;
  blockers?: string[];
  reason: string;
  updatedAt: number;
  triggerCandleTime?: number;
  referencePrice?: number;
  atr?: number;
  dataVersion?: string;
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
  setupScore?: number;
  generatedTime: string;
  generatedAt?: number;
  reason: string;
  status: SignalStatus;
  initialRisk?: number;
  dataVersion?: string;
}

export interface PaperPosition {
  id: string;
  signalId?: string;
  strategyVersion?: string;
  symbol: SymbolKey;
  side: TradeSide;
  entryPrice: number;
  currentPrice: number;
  stopLoss: number;
  initialStopLoss?: number;
  target1: number;
  target2: number;
  leverage: number;
  quantity?: number;
  size: number;
  margin: number;
  unrealizedPnL: number;
  unrealizedPnLPercent: number;
  initialRisk?: number;
  initialRiskAmount?: number;
  rMultiple?: number;
  breakEvenActivated?: boolean;
  trailingActivated?: boolean;
  openedAt: number;
  lastUpdated?: number;
  setupScore?: number;
  reason?: string;
}

export interface ClosedTrade {
  id: string;
  signalId?: string;
  strategyVersion?: string;
  symbol: SymbolKey;
  side: TradeSide;
  entryPrice: number;
  exitPrice: number;
  size: number;
  quantity?: number;
  leverage: number;
  realizedPnL: number;
  realizedPnLPercent: number;
  realizedR?: number;
  openedAt: number;
  closedAt: number;
  durationSeconds: number;
  isWin: boolean;
  fees?: number;
  exitReason?: string;
}

export interface TerminalSettings {
  capital: number;
  riskPerTradePct: number;
  maxDailyLossPct: number;
  maxPortfolioRiskPct: number;
  maxConcurrentTrades: number;
  maxSameDirection: number;
  maxLeverage: number;
  minSetupScore: number;
  maxTradesPerDay: number;
  maxConsecutiveLosses: number;
  cooldownMinutes: number;
  atrStopMultiplier: number;
  targetRR: number;
  feeRatePct: number;
  slippagePct: number;
  maxEntryDriftPct: number;
  minStopPct: number;
  maxStopPct: number;
  breakevenAtR: number;
  trailingStartR: number;
  trailingDistanceR: number;
  maxHoldMinutes: number;
  minAtrPct: number;
  maxAtrPct: number;
  minVolumeRatio: number;
  signalRetentionMinutes?: number;
  btcTrendFilter: boolean;
  isLiveMode: boolean;
  apiKey: string;
  apiSecret: string;
}

export interface RiskSnapshot {
  todayTrades: number;
  todayRealizedPnL: number;
  consecutiveLosses: number;
  openPositions: number;
  openRisk: number;
  maxDailyLoss: number;
  dailyLossRemaining?: number;
  maxPortfolioRisk: number;
  engineRunning?: boolean;
  lastScan?: number;
  blocked: boolean;
  blockReason: string | null;
}

export interface TradingApiState {
  engine_running: boolean;
  mode: 'PAPER_ONLY';
  strategy: string;
  scanner?: { status: string; lastScan: number; symbols: string[] };
  positions: PaperPosition[];
  closed_trades: ClosedTrade[];
  executed_signal_ids: string[];
  analyses: BackendAnalysis[];
  signals: AlgoSignal[];
  risk: RiskSnapshot;
  settings: Record<string, unknown>;
}
