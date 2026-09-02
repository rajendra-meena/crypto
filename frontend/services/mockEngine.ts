import { SymbolKey, Candle, TickerData, TechnicalIndicators, AlgoSignal } from '@/types/trading';

interface SymbolState {
  basePrice: number;
  price: number;
  candles: Candle[];
  indicators: TechnicalIndicators;
  signals: AlgoSignal[];
}

const INITIAL_BASE_PRICES: Record<SymbolKey, number> = {
  BTCUSDT: 64250.0,
  ETHUSDT: 3480.0,
  SOLUSDT: 148.5,
  XRPUSDT: 0.585,
  BNBUSDT: 582.0,
};

// Generate realistic synthetic candles
function generateInitialCandles(basePrice: number, symbol: SymbolKey, timeframe: string, count = 50): Candle[] {
  const candles: Candle[] = [];
  const now = Date.now();
  const intervalMs = 60 * 1000;
  let runningPrice = basePrice;

  for (let i = count; i >= 1; i--) {
    const time = now - i * intervalMs;
    const delta = (Math.random() - 0.49) * (basePrice * 0.003);
    const open = runningPrice;
    const close = runningPrice + delta;
    const high = Math.max(open, close) + Math.random() * (basePrice * 0.0015);
    const low = Math.min(open, close) - Math.random() * (basePrice * 0.0015);
    const volume = parseFloat((Math.random() * 5 + 1).toFixed(3));

    candles.push({ symbol, timeframe, time, open, high, low, close, volume });
    runningPrice = close;
  }
  return candles;
}

function calculateIndicators(price: number, candles: Candle[]): TechnicalIndicators {
  const rsi = Math.floor(40 + (Math.sin(price) + 1) * 20 + Math.random() * 10);
  const support = parseFloat((price * 0.985).toFixed(2));
  const resistance = parseFloat((price * 1.018).toFixed(2));
  const macdHistogram = parseFloat(((Math.random() - 0.45) * 15).toFixed(2));
  const confidence = Math.floor(75 + Math.random() * 20);

  const finalBias = rsi > 55 && macdHistogram > 0 ? 'BUY' : rsi < 45 && macdHistogram < 0 ? 'SELL' : 'WAIT';

  return {
    rsi,
    macd: {
      macdLine: parseFloat((macdHistogram * 1.2).toFixed(2)),
      signalLine: parseFloat((macdHistogram * 0.4).toFixed(2)),
      histogram: macdHistogram,
    },
    emaTrend: price > (candles[0]?.close ?? price) ? 'ABOVE_200_EMA' : 'BELOW_200_EMA',
    support,
    resistance,
    marketTrend: price > (candles[0]?.close ?? price) ? 'STRONG_BULLISH' : 'BEARISH',
    momentum: 'STRONG',
    volatility: 'NORMAL',
    volumeStrength: 'HIGH',
    marketStructure: 'TRENDING_UP',
    confidence,
    finalBias,
  };
}

export class MockMarketEngine {
  private static instance: MockMarketEngine;
  private state: Record<SymbolKey, SymbolState>;

  private constructor() {
    this.state = {
      BTCUSDT: this.createInitialSymbolState('BTCUSDT'),
      ETHUSDT: this.createInitialSymbolState('ETHUSDT'),
      SOLUSDT: this.createInitialSymbolState('SOLUSDT'),
      XRPUSDT: this.createInitialSymbolState('XRPUSDT'),
      BNBUSDT: this.createInitialSymbolState('BNBUSDT'),
    };
  }

  public static getInstance(): MockMarketEngine {
    if (!MockMarketEngine.instance) {
      MockMarketEngine.instance = new MockMarketEngine();
    }
    return MockMarketEngine.instance;
  }

  private createInitialSymbolState(symbol: SymbolKey): SymbolState {
    const basePrice = INITIAL_BASE_PRICES[symbol];
    const candles = generateInitialCandles(basePrice, symbol, '15m');
    const price = candles[candles.length - 1].close;
    const indicators = calculateIndicators(price, candles);

    return {
      basePrice,
      price,
      candles,
      indicators,
      signals: this.createInitialSignals(symbol, price),
    };
  }

  private createInitialSignals(symbol: SymbolKey, price: number): AlgoSignal[] {
    const isBuy = Math.random() > 0.4;
    const entry = price;
    const stopLoss = isBuy ? price * 0.988 : price * 1.012;
    const target1 = isBuy ? price * 1.015 : price * 0.985;
    const target2 = isBuy ? price * 1.03 : price * 0.97;

    return [
      {
        id: `SIG-${symbol}-1`,
        symbol,
        side: isBuy ? 'BUY' : 'SELL',
        timeframe: '5m',
        entry: parseFloat(entry.toFixed(2)),
        stopLoss: parseFloat(stopLoss.toFixed(2)),
        target1: parseFloat(target1.toFixed(2)),
        target2: parseFloat(target2.toFixed(2)),
        riskReward: '1:2.4',
        confidence: 86,
        generatedTime: new Date().toLocaleTimeString(),
        reason: 'EMA Crossover + MACD Bullish Momentum Expansion',
        status: 'READY',
      },
      {
        id: `SIG-${symbol}-2`,
        symbol,
        side: !isBuy ? 'BUY' : 'SELL',
        timeframe: '15m',
        entry: parseFloat((price * 1.004).toFixed(2)),
        stopLoss: parseFloat((price * 1.018).toFixed(2)),
        target1: parseFloat((price * 0.988).toFixed(2)),
        target2: parseFloat((price * 0.975).toFixed(2)),
        riskReward: '1:2.0',
        confidence: 72,
        generatedTime: new Date(Date.now() - 15 * 60000).toLocaleTimeString(),
        reason: 'RSI Divergence on key resistance zone',
        status: 'WATCHING',
      },
    ];
  }

  // Ticks one specific symbol and updates active candle and price synchronously
  public tick(symbol: SymbolKey): { price: number; candle: Candle; indicators: TechnicalIndicators } {
    const symState = this.state[symbol];
    const maxShift = symState.price * 0.0008;
    const delta = (Math.random() - 0.495) * maxShift;
    const newPrice = parseFloat((symState.price + delta).toFixed(2));
    symState.price = newPrice;

    // Synchronize current candle
    const lastCandle = symState.candles[symState.candles.length - 1];
    lastCandle.close = newPrice;
    lastCandle.high = Math.max(lastCandle.high, newPrice);
    lastCandle.low = Math.min(lastCandle.low, newPrice);
    lastCandle.volume = parseFloat((lastCandle.volume + Math.random() * 0.05).toFixed(3));

    // Synchronize indicators
    symState.indicators = calculateIndicators(newPrice, symState.candles);

    return {
      price: newPrice,
      candle: { ...lastCandle },
      indicators: symState.indicators,
    };
  }

  public getSnapshot(symbol: SymbolKey) {
    const sym = this.state[symbol];
    const signal = sym.signals[0];
    const ticker: TickerData = {
      symbol,
      price: sym.price,
      high24h: parseFloat((sym.price * 1.035).toFixed(2)),
      low24h: parseFloat((sym.price * 0.965).toFixed(2)),
      volume24h: 14238.45,
      change24h: parseFloat((((sym.price - sym.basePrice) / sym.basePrice) * 100).toFixed(2)),
      signalState: signal?.status || 'WATCHING',
      confidence: signal?.confidence || 0,
      lastUpdated: Date.now(),
    };

    return {
      ticker,
      candles: [...sym.candles],
      indicators: sym.indicators,
      signals: sym.signals,
    };
  }

  public getAllTickers(): TickerData[] {
    return Object.keys(this.state).map((symKey) => {
      const sym = this.state[symKey as SymbolKey];
      const signal = sym.signals[0];
      return {
        symbol: symKey as SymbolKey,
        price: sym.price,
        high24h: parseFloat((sym.price * 1.035).toFixed(2)),
        low24h: parseFloat((sym.price * 0.965).toFixed(2)),
        volume24h: 14238.45,
        change24h: parseFloat((((sym.price - sym.basePrice) / sym.basePrice) * 100).toFixed(2)),
        signalState: signal?.status || 'WATCHING',
        confidence: signal?.confidence || 0,
        lastUpdated: Date.now(),
      };
    });
  }
}