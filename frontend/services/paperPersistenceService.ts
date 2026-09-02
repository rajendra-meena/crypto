import { ClosedTrade, PaperPosition, TerminalSettings } from '@/types/trading';
import {
  closeTradingPosition,
  getTradingState,
  setTradingEngine,
  updateTradingSettings,
} from '@/services/tradingApiService';

/** @deprecated Use tradingApiService. */
export const loadPaperState = getTradingState;

/** @deprecated Use tradingApiService. */
export async function saveEngineState(running: boolean): Promise<void> {
  await setTradingEngine(running);
}

/** @deprecated Use tradingApiService. */
export async function saveTradingSettings(settings: Partial<TerminalSettings>): Promise<void> {
  await updateTradingSettings(settings);
}

/** @deprecated Use tradingApiService. */
export async function closePaperPosition(positionId: string): Promise<void> {
  await closeTradingPosition(positionId);
}

// Direct browser mutation of positions/trades/signals is intentionally disabled.
export async function savePaperPosition(_position: PaperPosition): Promise<never> {
  throw new Error('Frontend position creation is disabled. Backend algo engine is authoritative.');
}

export async function deletePaperPosition(_positionId: string): Promise<never> {
  throw new Error('Frontend position deletion is disabled. Use the backend close endpoint.');
}

export async function saveClosedTrade(_trade: ClosedTrade): Promise<never> {
  throw new Error('Frontend closed-trade writes are disabled.');
}

export async function markSignalExecuted(_signalId: string, _symbol: string): Promise<never> {
  throw new Error('Frontend signal execution writes are disabled.');
}
