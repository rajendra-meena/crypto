import { Candle, TechnicalIndicators } from '@/types/trading';

/**
 * @deprecated Trading analysis is backend-authoritative.
 *
 * The browser must never generate executable crypto signals. This compatibility
 * function intentionally returns null so any forgotten legacy caller fails safe
 * instead of producing a second, conflicting strategy decision.
 */
export function analyzePriceAction(_candles: Candle[]): TechnicalIndicators | null {
  return null;
}
