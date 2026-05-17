/**
 * WebSocket Client Manager
 *
 * Handles WebSocket connections for real-time updates.
 * Supports automatic reconnection, heartbeat, and multiple channels.
 *
 * Auth model:
 *  - Regular browser flow: the backend sets the `ssp_access_token` httpOnly
 *    cookie, which the browser sends automatically on the WS upgrade request.
 *    No JS-side token handling needed.
 *  - Shopify embedded / App Bridge flow: the bearer is held in JS memory by
 *    `lib/auth/token.ts`. It is attached as `?token=<jwt>` on the handshake URL
 *    and re-resolved on every (re)connect, so token rotation is picked up.
 */

import { getBearerToken } from '@/lib/auth/token';

type MessageHandler = (data: unknown) => void;
type ConnectionHandler = () => void;

interface WebSocketClientOptions {
  /**
   * The WS URL to connect to. May be a string (resolved once at construction)
   * or a thunk (resolved on every connect — use this when the auth bearer or
   * any other URL component can change between reconnects, e.g. App Bridge
   * session token rotation).
   */
  url: string | (() => string);
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string | (() => string);
  private reconnectInterval: number;
  private maxReconnectAttempts: number;
  private heartbeatInterval: number;
  private reconnectAttempts = 0;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private isIntentionallyClosed = false;

  // Event handlers
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private onConnectHandlers: Set<ConnectionHandler> = new Set();
  private onDisconnectHandlers: Set<ConnectionHandler> = new Set();

  constructor(options: WebSocketClientOptions) {
    this.url = options.url;
    this.reconnectInterval = options.reconnectInterval ?? 3000;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
    this.heartbeatInterval = options.heartbeatInterval ?? 30000;
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('[WS] Already connected');
      return;
    }

    this.isIntentionallyClosed = false;

    try {
      const resolvedUrl = typeof this.url === 'function' ? this.url() : this.url;
      this.ws = new WebSocket(resolvedUrl);
      this.setupEventListeners();
    } catch (error) {
      console.error('[WS] Connection error:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.isIntentionallyClosed = true;
    this.stopHeartbeat();
    this.clearReconnectTimer();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnected');
      this.ws = null;
    }
  }

  /**
   * Send a message to the server
   */
  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('[WS] Cannot send - not connected');
    }
  }

  /**
   * Subscribe to a specific message type
   */
  on(type: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(type)?.delete(handler);
    };
  }

  /**
   * Subscribe to connection events
   */
  onConnect(handler: ConnectionHandler): () => void {
    this.onConnectHandlers.add(handler);
    return () => this.onConnectHandlers.delete(handler);
  }

  /**
   * Subscribe to disconnection events
   */
  onDisconnect(handler: ConnectionHandler): () => void {
    this.onDisconnectHandlers.add(handler);
    return () => this.onDisconnectHandlers.delete(handler);
  }

  /**
   * Check if connected
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Private methods
  // ─────────────────────────────────────────────────────────────────────────

  private setupEventListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.onConnectHandlers.forEach((handler) => handler());
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.onDisconnectHandlers.forEach((handler) => handler());

      if (!this.isIntentionallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('[WS] Error:', error);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (error) {
        console.error('[WS] Failed to parse message:', error);
      }
    };
  }

  private handleMessage(data: Record<string, unknown>): void {
    const type = data.type as string;

    // Handle pong (heartbeat response)
    if (type === 'pong') {
      return;
    }

    // Notify type-specific handlers
    if (type && this.messageHandlers.has(type)) {
      this.messageHandlers.get(type)!.forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          console.error('[WS] Handler error:', error);
        }
      });
    }

    // Notify wildcard handlers
    if (this.messageHandlers.has('*')) {
      this.messageHandlers.get('*')!.forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          console.error('[WS] Wildcard handler error:', error);
        }
      });
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping' });
    }, this.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached');
      return;
    }

    this.clearReconnectTimer();

    const delay = this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts);
    this.reconnectAttempts++;
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// URL helpers
// ─────────────────────────────────────────────────────────────────────────────

function getWebSocketBaseUrl(): string {
  if (typeof window === 'undefined') {
    return '';
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Convert http(s) to ws(s)
  return apiUrl.replace(/^http/, 'ws');
}

/**
 * Build the full WS URL for a channel.
 *
 * - Path: backend mounts the WS router under `/api/v1` (see backend/main.py).
 * - Auth:
 *     • Shopify embedded / App Bridge → bearer is in JS memory; attach as `?token=`.
 *     • Regular browser flow → rely on the `ssp_access_token` httpOnly cookie,
 *       which the browser sends automatically on the upgrade request.
 *
 * Re-evaluated on every (re)connect via the thunk passed into WebSocketClient.
 */
function buildChannelUrl(channel: string): string {
  const baseUrl = getWebSocketBaseUrl();
  const path = `/api/v1/ws/${channel}`;
  const bearer = getBearerToken();
  return bearer
    ? `${baseUrl}${path}?token=${encodeURIComponent(bearer)}`
    : `${baseUrl}${path}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Factory functions for creating channel-specific clients
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Create alerts WebSocket client
 */
export function createAlertsClient(): WebSocketClient {
  return new WebSocketClient({
    url: () => buildChannelUrl('alerts'),
  });
}

/**
 * Create prices WebSocket client
 */
export function createPricesClient(): WebSocketClient {
  return new WebSocketClient({
    url: () => buildChannelUrl('prices'),
  });
}

/**
 * Create sentiment WebSocket client for a specific product
 */
export function createSentimentClient(productId: string): WebSocketClient {
  return new WebSocketClient({
    url: () => buildChannelUrl(`sentiment/${productId}`),
  });
}



