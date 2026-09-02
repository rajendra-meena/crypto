import { ClosedTrade, PaperPosition } from '@/types/trading';

export interface PersistedPaperState {
  engine_running: boolean;
  positions: PaperPosition[];
  closed_trades: ClosedTrade[];
  executed_signal_ids: string[];
}

const apiBaseUrl = (process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`Paper persistence request failed: ${response.status} ${path}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

export async function loadPaperState(): Promise<PersistedPaperState> {
  return request('/api/paper/state');
}

export async function saveEngineState(running: boolean): Promise<void> {
  await request('/api/paper/engine', {
    method: 'PUT',
    body: JSON.stringify({ running }),
  });
}

export async function savePaperPosition(position: PaperPosition): Promise<void> {
  await request(`/api/paper/positions/${encodeURIComponent(position.id)}`, {
    method: 'PUT',
    body: JSON.stringify({ position }),
  });
}

export async function deletePaperPosition(positionId: string): Promise<void> {
  await request(`/api/paper/positions/${encodeURIComponent(positionId)}`, {
    method: 'DELETE',
  });
}

export async function saveClosedTrade(trade: ClosedTrade): Promise<void> {
  await request(`/api/paper/closed-trades/${encodeURIComponent(trade.id)}`, {
    method: 'PUT',
    body: JSON.stringify({ trade }),
  });
}

export async function markSignalExecuted(signalId: string, symbol: string): Promise<void> {
  await request(`/api/paper/executed-signals/${encodeURIComponent(signalId)}`, {
    method: 'PUT',
    body: JSON.stringify({ signal_id: signalId, symbol }),
  });
}
