import { Candle, TechnicalIndicators } from '@/types/trading';

const round = (value: number, digits = 2) => Number(value.toFixed(digits));
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

function ema(values: number[], period: number): number[] {
  if (!values.length) return [];
  const k = 2 / (period + 1);
  const result: number[] = [values[0]];
  for (let i = 1; i < values.length; i += 1) {
    result.push(values[i] * k + result[i - 1] * (1 - k));
  }
  return result;
}

function calculateRsi(closes: number[], period = 14): number {
  if (closes.length <= period) return 50;
  let gains = 0;
  let losses = 0;
  for (let i = closes.length - period; i < closes.length; i += 1) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gains += diff;
    else losses += Math.abs(diff);
  }
  if (losses === 0) return 100;
  const rs = (gains / period) / (losses / period);
  return 100 - 100 / (1 + rs);
}

function calculateMacd(closes: number[]) {
  const ema12 = ema(closes, 12);
  const ema26 = ema(closes, 26);
  const macdLineSeries = closes.map((_, i) => (ema12[i] ?? 0) - (ema26[i] ?? 0));
  const signalSeries = ema(macdLineSeries, 9);
  const macdLine = macdLineSeries[macdLineSeries.length - 1] ?? 0;
  const signalLine = signalSeries[signalSeries.length - 1] ?? 0;
  return {
    macdLine: round(macdLine, 4),
    signalLine: round(signalLine, 4),
    histogram: round(macdLine - signalLine, 4),
  };
}

function dedupeAndSort(candles: Candle[]): Candle[] {
  const byTime = new Map<number, Candle>();
  candles.forEach((candle) => {
    if (Number.isFinite(candle.time) && candle.close > 0) byTime.set(candle.time, candle);
  });
  return Array.from(byTime.values()).sort((a, b) => a.time - b.time);
}

function selectAnalysisCandles(candles: Candle[]): Candle[] {
  const preferred = ['15m', '5m', '1m'];
  for (const timeframe of preferred) {
    const series = dedupeAndSort(candles.filter((c) => c.timeframe === timeframe));
    if (series.length >= 20) return series;
  }
  return dedupeAndSort(candles);
}

export function analyzePriceAction(candles: Candle[]): TechnicalIndicators | null {
  const series = selectAnalysisCandles(candles);
  if (series.length < 12) return null;

  const lookback = series.slice(-30);
  const current = lookback[lookback.length - 1];
  const previous = lookback[lookback.length - 2];
  const priorRange = lookback.slice(0, -1);
  if (!current || !previous || priorRange.length < 8) return null;

  const closes = lookback.map((c) => c.close);
  const highs = priorRange.map((c) => c.high);
  const lows = priorRange.map((c) => c.low);
  const support = Math.min(...lows.slice(-20));
  const resistance = Math.max(...highs.slice(-20));
  const previousResistance = Math.max(...highs.slice(-10));
  const previousSupport = Math.min(...lows.slice(-10));

  const emaFast = ema(closes, 9).at(-1) ?? current.close;
  const emaSlow = ema(closes, 20).at(-1) ?? current.close;

  const bullishBreakout = current.close > previousResistance && current.close > previous.high;
  const bearishBreakdown = current.close < previousSupport && current.close < previous.low;

  const recent = lookback.slice(-6);
  const bullishBodies = recent.filter((c) => c.close > c.open).length;
  const bearishBodies = recent.filter((c) => c.close < c.open).length;
  const netMovePct = ((current.close - recent[0].open) / Math.max(recent[0].open, 1e-9)) * 100;

  let marketTrend: TechnicalIndicators['marketTrend'] = 'NEUTRAL';
  if (bullishBreakout || (current.close > emaFast && emaFast > emaSlow && netMovePct > 0.2)) marketTrend = bullishBreakout ? 'STRONG_BULLISH' : 'BULLISH';
  else if (bearishBreakdown || (current.close < emaFast && emaFast < emaSlow && netMovePct < -0.2)) marketTrend = bearishBreakdown ? 'STRONG_BEARISH' : 'BEARISH';

  let momentum: TechnicalIndicators['momentum'] = 'WEAK';
  const directionalBodies = Math.max(bullishBodies, bearishBodies);
  if (directionalBodies >= 5 || Math.abs(netMovePct) >= 0.7) momentum = 'STRONG';
  else if (directionalBodies >= 4 || Math.abs(netMovePct) >= 0.25) momentum = 'MODERATE';

  const ranges = lookback.slice(-14).map((c) => c.high - c.low);
  const avgRange = ranges.reduce((sum, value) => sum + value, 0) / Math.max(ranges.length, 1);
  const rangePct = (avgRange / Math.max(current.close, 1e-9)) * 100;
  const volatility: TechnicalIndicators['volatility'] = rangePct >= 0.9 ? 'HIGH' : rangePct <= 0.25 ? 'LOW' : 'NORMAL';

  const volumes = lookback.slice(-20).map((c) => c.volume || 0);
  const avgVolume = volumes.reduce((sum, value) => sum + value, 0) / Math.max(volumes.length, 1);
  const currentVolume = current.volume || 0;
  const volumeRatio = avgVolume > 0 ? currentVolume / avgVolume : 1;
  const volumeStrength: TechnicalIndicators['volumeStrength'] = volumeRatio >= 1.35 ? 'HIGH' : volumeRatio <= 0.7 ? 'LOW' : 'AVERAGE';

  let marketStructure: TechnicalIndicators['marketStructure'] = 'RANGE_BOUND';
  if (bullishBreakout || bearishBreakdown) marketStructure = 'BREAKOUT';
  else if (emaFast > emaSlow && current.close > emaFast) marketStructure = 'TRENDING_UP';
  else if (emaFast < emaSlow && current.close < emaFast) marketStructure = 'TRENDING_DOWN';

  let score = 0;
  if (marketTrend === 'STRONG_BULLISH') score += 3;
  else if (marketTrend === 'BULLISH') score += 2;
  else if (marketTrend === 'STRONG_BEARISH') score -= 3;
  else if (marketTrend === 'BEARISH') score -= 2;

  if (bullishBreakout) score += 3;
  if (bearishBreakdown) score -= 3;
  if (bullishBodies >= 4) score += 1;
  if (bearishBodies >= 4) score -= 1;
  if (volumeStrength === 'HIGH' && score > 0) score += 1;
  if (volumeStrength === 'HIGH' && score < 0) score -= 1;

  const finalBias: TechnicalIndicators['finalBias'] = score >= 4 ? 'BUY' : score <= -4 ? 'SELL' : 'WAIT';
  const confidence = finalBias === 'WAIT'
    ? clamp(45 + Math.abs(score) * 6, 45, 68)
    : clamp(58 + Math.abs(score) * 5 + (volumeStrength === 'HIGH' ? 5 : 0), 60, 95);

  return {
    rsi: round(calculateRsi(closes), 1),
    macd: calculateMacd(closes),
    emaTrend: emaFast > emaSlow ? 'ABOVE_200_EMA' : emaFast < emaSlow ? 'BELOW_200_EMA' : 'CONSOLIDATING',
    support: round(support, current.close < 10 ? 4 : 2),
    resistance: round(resistance, current.close < 10 ? 4 : 2),
    marketTrend,
    momentum,
    volatility,
    volumeStrength,
    marketStructure,
    confidence: Math.round(confidence),
    finalBias,
  };
}
