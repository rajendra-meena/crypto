import {
  Candle,
  MarketTick as BackendMarketTick,
} from '@/types/trading';

export type BackendConnectionState = 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';
export type DeltaConnectionState = 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'STALE' | 'DISCONNECTED';

export interface ConnectionStates {
  backend: BackendConnectionState;
  delta: DeltaConnectionState;
}

interface WSMessage {
  type: string;
  payload: any;
  timestamp: number;
}

interface BackendCandle {
  symbol: string;
  timeframe: string;
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_complete?: boolean;
}

interface MarketSnapshot {
  symbol: string;
  current_price: number;
  candles: Candle[];
  connection_state: DeltaConnectionState;
  last_update: number;
}

interface BackendMarketSnapshot extends Omit<MarketSnapshot, 'candles'> {
  candles: BackendCandle[];
}

interface HealthResponse {
  status: string;
  delta_connection_state: DeltaConnectionState;
  market_feed: string;
  connected_symbols: string[];
  live_symbols: string[];
  stale_symbols: string[];
  no_data_symbols: string[];
  unavailable_symbols: string[];
  last_tick_timestamp: number;
  uptime_seconds: number;
}

type TickCallback = (tick: BackendMarketTick) => void;
type CandleCallback = (candle: Candle) => void;
type SnapshotCallback = (snapshot: MarketSnapshot) => void;
type ConnectionStateCallback = (states: ConnectionStates) => void;
type ErrorCallback = (error: string) => void;

export class BackendMarketService {
  private ws: WebSocket | null = null;
  private url: string;
  private apiBaseUrl: string;
  private subscribedSymbols: Set<string> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private isConnecting = false;
  private shouldReconnect = true;

  private backendState: BackendConnectionState = 'DISCONNECTED';
  private deltaState: DeltaConnectionState = 'DISCONNECTED';

  private onTick?: TickCallback;
  private onCandle?: CandleCallback;
  private onSnapshot?: SnapshotCallback;
  private onConnectionStateChange?: ConnectionStateCallback;
  private onError?: ErrorCallback;

  private symbolStates: Map<string, {
    currentPrice: number;
    candles: Candle[];
    lastTickTime: number;
    deltaConnectionState: DeltaConnectionState;
  }> = new Map();

  constructor() {
    this.apiBaseUrl = (process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');
    this.url = process.env.NEXT_PUBLIC_BACKEND_WS_URL || 'ws://localhost:8000/ws/market';
  }

  setCallbacks(callbacks: {
    onTick?: TickCallback;
    onCandle?: CandleCallback;
    onSnapshot?: SnapshotCallback;
    onConnectionStateChange?: ConnectionStateCallback;
    onError?: ErrorCallback;
  }) {
    this.onTick = callbacks.onTick;
    this.onCandle = callbacks.onCandle;
    this.onSnapshot = callbacks.onSnapshot;
    this.onConnectionStateChange = callbacks.onConnectionStateChange;
    this.onError = callbacks.onError;
  }

  private _normalizeCandle(payload: BackendCandle): Candle {
    return {
      symbol: payload.symbol as Candle['symbol'],
      timeframe: payload.timeframe,
      time: payload.timestamp,
      open: payload.open,
      high: payload.high,
      low: payload.low,
      close: payload.close,
      volume: payload.volume,
      is_complete: payload.is_complete,
    };
  }

  async fetchHealth(): Promise<void> {
    try {
      const response = await fetch(`${this.apiBaseUrl}/health`, { cache: 'no-store' });
      if (!response.ok) return;
      const health: HealthResponse = await response.json();
      this._updateDeltaState(health.delta_connection_state);

      health.live_symbols?.forEach((sym) => {
        const state = this.symbolStates.get(sym);
        if (state) state.deltaConnectionState = 'CONNECTED';
      });
      health.stale_symbols?.forEach((sym) => {
        const state = this.symbolStates.get(sym);
        if (state) state.deltaConnectionState = 'STALE';
      });
      health.no_data_symbols?.forEach((sym) => {
        const state = this.symbolStates.get(sym);
        if (state) state.deltaConnectionState = 'DISCONNECTED';
      });
    } catch (err) {
      console.warn('[BackendMarketService] Health fetch failed:', err);
    }
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      if (this.isConnecting) {
        const checkConnection = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            clearInterval(checkConnection);
            resolve();
          }
        }, 100);
        return;
      }

      this.isConnecting = true;
      this.shouldReconnect = true;
      this._updateBackendState('CONNECTING');

      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.reconnectDelay = 1000;
          this._updateBackendState('CONNECTED');

          if (this.subscribedSymbols.size > 0) {
            this._send({
              type: 'subscribe',
              symbols: Array.from(this.subscribedSymbols),
            });
          }

          this.fetchHealth();
          this._startHealthPolling();
          resolve();
        };

        this.ws.onmessage = (event) => {
          this._handleMessage(event.data);
        };

        this.ws.onclose = () => {
          this.isConnecting = false;
          this._updateBackendState('DISCONNECTED');
          this._updateDeltaState('DISCONNECTED');
          this._stopHealthPolling();
          this._attemptReconnect();
        };

        this.ws.onerror = () => {
          this.isConnecting = false;
          this._updateBackendState('DISCONNECTED');
          this.onError?.('WebSocket connection error');
        };
      } catch (err) {
        this.isConnecting = false;
        this._updateBackendState('DISCONNECTED');
        reject(err);
      }
    });
  }

  private healthPollInterval: ReturnType<typeof setInterval> | null = null;

  private _startHealthPolling() {
    this._stopHealthPolling();
    this.healthPollInterval = setInterval(() => this.fetchHealth(), 5000);
  }

  private _stopHealthPolling() {
    if (this.healthPollInterval) {
      clearInterval(this.healthPollInterval);
      this.healthPollInterval = null;
    }
  }

  private _attemptReconnect() {
    if (!this.shouldReconnect) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this._updateBackendState('DISCONNECTED');
      this.onError?.('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    this._updateBackendState('RECONNECTING');

    setTimeout(() => {
      this.connect().catch(() => undefined);
    }, this.reconnectDelay);

    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
  }

  disconnect() {
    this.shouldReconnect = false;
    this._stopHealthPolling();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._updateBackendState('DISCONNECTED');
    this._updateDeltaState('DISCONNECTED');
  }

  subscribe(symbols: string[]) {
    const newSymbols = symbols.filter((s) => !this.subscribedSymbols.has(s));
    if (newSymbols.length === 0) return;

    newSymbols.forEach((s) => this.subscribedSymbols.add(s));

    if (this.ws?.readyState === WebSocket.OPEN) {
      this._send({ type: 'subscribe', symbols: newSymbols });
    }
  }

  unsubscribe(symbols: string[]) {
    symbols.forEach((s) => this.subscribedSymbols.delete(s));
    if (this.ws?.readyState === WebSocket.OPEN) {
      this._send({ type: 'unsubscribe', symbols });
    }
  }

  private _send(message: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private _handleMessage(data: string) {
    try {
      const message: WSMessage = JSON.parse(data);
      switch (message.type) {
        case 'market_tick':
          this._handleTick(message.payload as BackendMarketTick);
          break;
        case 'candle_update':
          this._handleCandle(message.payload as BackendCandle);
          break;
        case 'market_snapshot':
          this._handleSnapshot(message.payload as BackendMarketSnapshot);
          break;
        case 'connection_status':
          this._updateDeltaState(message.payload.state);
          break;
        case 'error':
          this.onError?.(message.payload?.message || 'Backend WebSocket error');
          break;
      }
    } catch (err) {
      console.error('[Frontend WS] Failed to parse message:', err);
    }
  }

  private _updateBackendState(state: BackendConnectionState) {
    if (this.backendState === state) return;
    this.backendState = state;
    this._notifyConnectionStateChange();
  }

  private _updateDeltaState(state: DeltaConnectionState) {
    if (this.deltaState === state) return;
    this.deltaState = state;
    this._notifyConnectionStateChange();
  }

  private _notifyConnectionStateChange() {
    this.onConnectionStateChange?.({ backend: this.backendState, delta: this.deltaState });
  }

  private _handleTick(payload: BackendMarketTick) {
    const { symbol, price, timestamp } = payload;
    let state = this.symbolStates.get(symbol);
    if (!state) {
      state = {
        currentPrice: 0,
        candles: [],
        lastTickTime: 0,
        deltaConnectionState: 'CONNECTED',
      };
      this.symbolStates.set(symbol, state);
    }

    state.currentPrice = price;
    state.lastTickTime = timestamp;
    state.deltaConnectionState = 'CONNECTED';
    this.onTick?.(payload);
  }

  private _handleCandle(payload: BackendCandle) {
    const candle = this._normalizeCandle(payload);
    const { symbol } = candle;

    let state = this.symbolStates.get(symbol);
    if (!state) {
      state = {
        currentPrice: 0,
        candles: [],
        lastTickTime: 0,
        deltaConnectionState: 'CONNECTED',
      };
      this.symbolStates.set(symbol, state);
    }

    const existingIndex = state.candles.findIndex(
      (c) => c.timeframe === candle.timeframe && c.time === candle.time
    );

    if (existingIndex >= 0) {
      state.candles[existingIndex] = candle;
    } else {
      state.candles.push(candle);
      if (state.candles.length > 500) {
        state.candles = state.candles.slice(-500);
      }
    }

    this.onCandle?.(candle);
  }

  private _handleSnapshot(payload: BackendMarketSnapshot) {
    const candles = (payload.candles || []).map((c) => this._normalizeCandle(c));
    const snapshot: MarketSnapshot = { ...payload, candles };
    const { symbol, current_price, connection_state, last_update } = snapshot;

    let state = this.symbolStates.get(symbol);
    if (!state) {
      state = {
        currentPrice: 0,
        candles: [],
        lastTickTime: 0,
        deltaConnectionState: 'CONNECTING',
      };
      this.symbolStates.set(symbol, state);
    }

    state.currentPrice = current_price;
    state.candles = candles;
    state.lastTickTime = last_update;
    state.deltaConnectionState = connection_state;

    this.onSnapshot?.(snapshot);
  }

  getSymbolState(symbol: string) {
    return this.symbolStates.get(symbol);
  }

  getCurrentPrice(symbol: string): number {
    return this.symbolStates.get(symbol)?.currentPrice || 0;
  }

  getCandles(symbol: string): Candle[] {
    return this.symbolStates.get(symbol)?.candles || [];
  }

  getDeltaConnectionState(symbol: string): DeltaConnectionState {
    return this.symbolStates.get(symbol)?.deltaConnectionState || 'DISCONNECTED';
  }

  getBackendConnectionState(): BackendConnectionState {
    return this.backendState;
  }

  getDeltaConnectionStateOverall(): DeltaConnectionState {
    return this.deltaState;
  }

  getConnectionStates(): ConnectionStates {
    return { backend: this.backendState, delta: this.deltaState };
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

let instance: BackendMarketService | null = null;

export function getBackendMarketService(): BackendMarketService {
  if (!instance) {
    instance = new BackendMarketService();
  }
  return instance;
}
