import { BackendAnalysis, AlgoSignal, RiskSnapshot, TerminalSettings, TradingApiState } from '@/types/trading';

const API_BASE = (process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 8000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
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
  } finally {
    window.clearTimeout(timer);
  }
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
  await request(`/api/trading/positions/${encodeURIComponent(positionId)}/close`, { method: 'POST' });
}

export function getSymbolAnalysis(symbol: string): Promise<BackendAnalysis> {
  return request<BackendAnalysis>(`/api/trading/analysis/${encodeURIComponent(symbol)}`);
}

export function getTradingDiagnostics(): Promise<{
  strategy: string;
  engine_running: boolean;
  risk: RiskSnapshot;
  analyses: BackendAnalysis[];
  signals: AlgoSignal[];
}> {
  return request('/api/trading/diagnostics');
}

export function scanTradingNow(): Promise<{
  scanned: boolean;
  lastScan: number;
  analyses: BackendAnalysis[];
  signals: AlgoSignal[];
}> {
  return request('/api/trading/scan', { method: 'POST' });
}
