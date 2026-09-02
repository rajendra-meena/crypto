import {
  SymbolKey,
  TickerData,
  Candle,
  TechnicalIndicators,
  AlgoSignal,
  MarketTick as BackendMarketTick,
} from '@/types/trading';

// Frontend -> Backend WebSocket connection states
export type BackendConnectionState = 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';

// Backend -> Delta Exchange connection states
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

interface MarketSnapshot {
  symbol: string;
  current_price: number;
  candles: Candle[];
  connection_state: DeltaConnectionState;
  last_update: number;
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

  // Connection state tracking
  private backendState: BackendConnectionState = 'DISCONNECTED';
  private deltaState: DeltaConnectionState = 'DISCONNECTED';

  // Callbacks
  private onTick?: TickCallback;
  private onCandle?: CandleCallback;
  private onSnapshot?: SnapshotCallback;
  private onConnectionStateChange?: ConnectionStateCallback;
  private onError?: ErrorCallback;

  // Local state
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

  // Fetch health from backend REST endpoint
  async fetchHealth(): Promise<void> {
    try {
      const response = await fetch(`${this.apiBaseUrl}/health`, { cache: 'no-store' });
      if (!response.ok) return;
      const health: HealthResponse = await response.json();
      this._updateDeltaState(health.delta_connection_state);
      
      // Update per-symbol delta connection states
      if (health.live_symbols) {
        health.live_symbols.forEach((sym: string) => {
          const state = this.symbolStates.get(sym);
          if (state) state.deltaConnectionState = 'CONNECTED';
        });
      }
      if (health.stale_symbols) {
        health.stale_symbols.forEach((sym: string) => {
          const state = this.symbolStates.get(sym);
          if (state) state.deltaConnectionState = 'STALE';
        });
      }
      if (health.no_data_symbols) {
        health.no_data_symbols.forEach((sym: string) => {
          const state = this.symbolStates.get(sym);
          if (state) state.deltaConnectionState = 'DISCONNECTED';
        });
      }
    } catch (err) {
      console.warn('[BackendMarketService] Health fetch failed:', err);
    }
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        console.log('[Frontend WS] Already connected');
        resolve();
        return;
      }

      if (this.isConnecting) {
        console.log('[Frontend WS] Already connecting, waiting...');
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
        console.log('[Frontend WS] Creating WebSocket to:', this.url);
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('[Frontend WS] OPEN - WebSocket connected');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.reconnectDelay = 1000;
          this._updateBackendState('CONNECTED');
          
          // Re-subscribe to symbols
          if (this.subscribedSymbols.size > 0) {
            this._send({
              type: 'subscribe',
              symbols: Array.from(this.subscribedSymbols),
            });
          }
          
          // Fetch initial health
          this.fetchHealth();
          
          // Start periodic health polling
          this._startHealthPolling();
          
          resolve();
        };

        this.ws.onmessage = (event) => {
          console.log('[Frontend WS] Message received:', event.data.substring(0, 200));
          this._handleMessage(event.data);
        };

        this.ws.onclose = (event) => {
          console.log('[Frontend WS] CLOSE code:', event.code, 'reason:', event.reason);
          this.isConnecting = false;
          this._updateBackendState('DISCONNECTED');
          this._updateDeltaState('DISCONNECTED');
          this._stopHealthPolling();
          this._attemptReconnect();
        };

        this.ws.onerror = (error) => {
          console.error('[Frontend WS] ERROR:', error);
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
    this.healthPollInterval = setInterval(() => {
      this.fetchHealth();
    }, 5000); // Poll every 5 seconds
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
      console.error('[BackendMarketService] Max reconnect attempts reached');
      this._updateBackendState('DISCONNECTED');
      this.onError?.('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    this._updateBackendState('RECONNECTING');
    
    console.log(`[BackendMarketService] Reconnecting... (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      this.connect().catch(() => {
        // Reconnect will be attempted again in onclose
      });
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
    const newSymbols = symbols.filter(s => !this.subscribedSymbols.has(s));
    if (newSymbols.length === 0) return;

    newSymbols.forEach(s => this.subscribedSymbols.add(s));

    if (this.ws?.readyState === WebSocket.OPEN) {
      this._send({
        type: 'subscribe',
        symbols: newSymbols,
      });
    }
  }

  unsubscribe(symbols: string[]) {
    symbols.forEach(s => this.subscribedSymbols.delete(s));

    if (this.ws?.readyState === WebSocket.OPEN) {
      this._send({
        type: 'unsubscribe',
        symbols,
      });
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
      console.log('[Frontend WS] Handling message type:', message.type);
      
      switch (message.type) {
        case 'market_tick':
          console.log('[Frontend WS] Handling market_tick for:', message.payload?.symbol);
          this._handleTick(message.payload);
          break;
        case 'candle_update':
          console.log('[Frontend WS] Handling candle_update for:', message.payload?.symbol, 'timeframe:', message.payload?.timeframe);
          this._handleCandle(message.payload);
          break;
        case 'market_snapshot':
          console.log('[Frontend WS] Handling market_snapshot for:', message.payload?.symbol);
          this._handleSnapshot(message.payload);
          break;
        case 'connection_status':
          console.log('[Frontend WS] Handling connection_status:', message.payload?.state);
          this._updateDeltaState(message.payload.state);
          break;
        case 'error':
          console.error('[Frontend WS] ERROR from backend:', message.payload?.message);
          this.onError?.(message.payload.message);
          break;
        default:
          console.log('[Frontend WS] Unknown message type:', message.type);
      }
    } catch (err) {
      console.error('[Frontend WS] Failed to parse message:', err);
    }
  }

  private _updateBackendState(state: BackendConnectionState) {
    if (this.backendState === state) return;
    console.log('[Frontend WS] Backend state changed:', this.backendState, '->', state);
    this.backendState = state;
    this._notifyConnectionStateChange();
  }

  private _updateDeltaState(state: DeltaConnectionState) {
    if (this.deltaState === state) return;
    console.log('[Frontend WS] Delta state changed:', this.deltaState, '->', state);
    this.deltaState = state;
    this._notifyConnectionStateChange();
  }

  private _notifyConnectionStateChange() {
    console.log('[Frontend WS] Notifying connection state change:', { backend: this.backendState, delta: this.deltaState });
    this.onConnectionStateChange?.({
      backend: this.backendState,
      delta: this.deltaState,
    });
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

  private _handleCandle(payload: Candle) {
    const { symbol } = payload;
    
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
    
    // Update or add candle
    const existingIndex = state.candles.findIndex(c => 
      c.timeframe === payload.timeframe && c.time === payload.time
    );
    
    if (existingIndex >= 0) {
      state.candles[existingIndex] = payload;
    } else {
      state.candles.push(payload);
      // Keep only recent candles
      if (state.candles.length > 500) {
        state.candles = state.candles.slice(-500);
      }
    }
    
    this.onCandle?.(payload);
  }

  private _handleSnapshot(payload: MarketSnapshot) {
    const { symbol, current_price, candles, connection_state, last_update } = payload;
    
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
    
    this.onSnapshot?.(payload);
  }

  private _updateConnectionState(state: BackendConnectionState | DeltaConnectionState) {
    // Legacy - kept for backward compatibility
    this._updateDeltaState(state as DeltaConnectionState);
  }

  // Getters for current state
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
    return {
      backend: this.backendState,
      delta: this.deltaState,
    };
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Singleton instance
let instance: BackendMarketService | null = null;

export function getBackendMarketService(): BackendMarketService {
  if (!instance) {
    instance = new BackendMarketService();
  }
  return instance;
}
