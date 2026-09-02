import { TerminalSettings, TradingApiState } from '@/types/trading';

const API_BASE = (process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`Trading API ${response.status} ${path}${text ? `: ${text}` : ''}`);
  }
  return response.json() as Promise<T>;
}

export function getTradingState(): Promise<TradingApiState> {
  return request<TradingApiState>('/api/trading/state');
}

export async function setTradingEngine(running: boolean): Promise<boolean> {
  const result = await request<{ engine_running: boolean }>('/api/trading/engine', {
    method: 'PUT',
    body: JSON.stringify({ running }),
  });
  return result.engine_running;
}

export async function updateTradingSettings(settings: Partial<TerminalSettings>): Promise<Record<string, unknown>> {
  const result = await request<{ settings: Record<string, unknown> }>('/api/trading/settings', {
    method: 'PUT',
    body: JSON.stringify({ settings }),
  });
  return result.settings;
}

export async function closeTradingPosition(positionId: string): Promise<void> {
  await request(`/api/trading/positions/${encodeURIComponent(positionId)}/close`, {
    method: 'POST',
  });
}

export async function getSymbolAnalysis(symbol: string) {
  return request(`/api/trading/analysis/${encodeURIComponent(symbol)}`);
}
