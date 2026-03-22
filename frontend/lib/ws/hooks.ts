// frontend/lib/ws/hooks.ts
/**
 * WebSocket React Hooks
 * 
 * Provides easy-to-use hooks for real-time updates in React components.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { 
  WebSocketClient, 
  createAlertsClient, 
  createPricesClient,
  createSentimentClient 
} from './client';
import { alertKeys, productKeys, sentimentKeys } from '@/lib/api/query-keys';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface AlertMessage {
  type: 'new_alert';
  data: {
    id: string;
    alert_type: string;
    severity: string;
    title: string;
    message: string;
    product_id?: string;
    created_at: string;
  };
}

interface PriceUpdateMessage {
  type: 'price_update';
  product_id: string;
  data: {
    current_price: number;
    previous_price: number;
    change_percent: number;
  };
}

interface SentimentUpdateMessage {
  type: 'sentiment_update' | 'new_mention';
  product_id: string;
  data: Record<string, unknown>;
}

interface UseWebSocketOptions {
  enabled?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

interface UseWebSocketResult {
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// useRealtimeAlerts Hook
// ─────────────────────────────────────────────────────────────────────────────

interface UseRealtimeAlertsOptions extends UseWebSocketOptions {
  onNewAlert?: (alert: AlertMessage['data']) => void;
}

interface UseRealtimeAlertsResult extends UseWebSocketResult {
  latestAlert: AlertMessage['data'] | null;
  alertCount: number;
  clearAlertCount: () => void;
}

export function useRealtimeAlerts(
  options: UseRealtimeAlertsOptions = {}
): UseRealtimeAlertsResult {
  const { enabled = true, onNewAlert, onConnect, onDisconnect } = options;
  
  const clientRef = useRef<WebSocketClient | null>(null);
  const queryClient = useQueryClient();
  
  const [isConnected, setIsConnected] = useState(false);
  const [latestAlert, setLatestAlert] = useState<AlertMessage['data'] | null>(null);
  const [alertCount, setAlertCount] = useState(0);

  // Initialize client
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    clientRef.current = createAlertsClient();
    
    return () => {
      clientRef.current?.disconnect();
      clientRef.current = null;
    };
  }, []);

  // Setup connection and handlers
  useEffect(() => {
    const client = clientRef.current;
    if (!client || !enabled) return;

    // Connection handlers
    const unsubConnect = client.onConnect(() => {
      setIsConnected(true);
      onConnect?.();
      
      // Subscribe to alerts
      client.send({ type: 'subscribe' });
    });

    const unsubDisconnect = client.onDisconnect(() => {
      setIsConnected(false);
      onDisconnect?.();
    });

    // Message handler for new alerts
    const unsubMessage = client.on('new_alert', (data) => {
      const alertData = (data as AlertMessage).data;
      
      setLatestAlert(alertData);
      setAlertCount((prev) => prev + 1);
      
      // Invalidate alerts query to refresh the list
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
      
      // Call custom handler
      onNewAlert?.(alertData);
    });

    // Connect
    client.connect();

    return () => {
      unsubConnect();
      unsubDisconnect();
      unsubMessage();
    };
  }, [enabled, onConnect, onDisconnect, onNewAlert, queryClient]);

  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  const clearAlertCount = useCallback(() => {
    setAlertCount(0);
  }, []);

  return {
    isConnected,
    connect,
    disconnect,
    latestAlert,
    alertCount,
    clearAlertCount,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// useRealtimePrices Hook
// ─────────────────────────────────────────────────────────────────────────────

interface UseRealtimePricesOptions extends UseWebSocketOptions {
  onPriceUpdate?: (update: PriceUpdateMessage) => void;
}

interface UseRealtimePricesResult extends UseWebSocketResult {
  latestUpdate: PriceUpdateMessage | null;
}

export function useRealtimePrices(
  options: UseRealtimePricesOptions = {}
): UseRealtimePricesResult {
  const { enabled = true, onPriceUpdate, onConnect, onDisconnect } = options;
  
  const clientRef = useRef<WebSocketClient | null>(null);
  const queryClient = useQueryClient();
  
  const [isConnected, setIsConnected] = useState(false);
  const [latestUpdate, setLatestUpdate] = useState<PriceUpdateMessage | null>(null);

  // Initialize client
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    clientRef.current = createPricesClient();
    
    return () => {
      clientRef.current?.disconnect();
      clientRef.current = null;
    };
  }, []);

  // Setup connection and handlers
  useEffect(() => {
    const client = clientRef.current;
    if (!client || !enabled) return;

    const unsubConnect = client.onConnect(() => {
      setIsConnected(true);
      onConnect?.();
      client.send({ type: 'subscribe' });
    });

    const unsubDisconnect = client.onDisconnect(() => {
      setIsConnected(false);
      onDisconnect?.();
    });

    const unsubMessage = client.on('price_update', (data) => {
      const update = data as PriceUpdateMessage;
      
      setLatestUpdate(update);
      
      // Invalidate product queries to refresh prices
      queryClient.invalidateQueries({ queryKey: productKeys.all });
      
      onPriceUpdate?.(update);
    });

    client.connect();

    return () => {
      unsubConnect();
      unsubDisconnect();
      unsubMessage();
    };
  }, [enabled, onConnect, onDisconnect, onPriceUpdate, queryClient]);

  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  return {
    isConnected,
    connect,
    disconnect,
    latestUpdate,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// useRealtimeSentiment Hook
// ─────────────────────────────────────────────────────────────────────────────

interface UseRealtimeSentimentOptions extends UseWebSocketOptions {
  productId: string;
  onSentimentUpdate?: (update: SentimentUpdateMessage) => void;
  onNewMention?: (mention: SentimentUpdateMessage) => void;
}

interface UseRealtimeSentimentResult extends UseWebSocketResult {
  latestUpdate: SentimentUpdateMessage | null;
}

export function useRealtimeSentiment(
  options: UseRealtimeSentimentOptions
): UseRealtimeSentimentResult {
  const { 
    productId, 
    enabled = true, 
    onSentimentUpdate, 
    onNewMention,
    onConnect, 
    onDisconnect 
  } = options;
  
  const clientRef = useRef<WebSocketClient | null>(null);
  const queryClient = useQueryClient();

  const [isConnected, setIsConnected] = useState(false);
  const [latestUpdate, setLatestUpdate] = useState<SentimentUpdateMessage | null>(null);

  // Initialize client, setup handlers, and connect atomically
  // Merged into one effect to prevent race between client creation and handler
  // registration when productId changes under React 18 concurrent mode.
  useEffect(() => {
    if (typeof window === 'undefined' || !productId || !enabled) return;

    const client = createSentimentClient(productId);
    clientRef.current = client;

    const unsubConnect = client.onConnect(() => {
      setIsConnected(true);
      onConnect?.();
    });

    const unsubDisconnect = client.onDisconnect(() => {
      setIsConnected(false);
      onDisconnect?.();
    });

    const unsubSentiment = client.on('sentiment_update', (data) => {
      const update = data as SentimentUpdateMessage;
      setLatestUpdate(update);

      // Invalidate sentiment queries
      queryClient.invalidateQueries({ queryKey: sentimentKeys.all });

      onSentimentUpdate?.(update);
    });

    const unsubMention = client.on('new_mention', (data) => {
      const mention = data as SentimentUpdateMessage;
      setLatestUpdate(mention);

      // Invalidate sentiment queries
      queryClient.invalidateQueries({ queryKey: sentimentKeys.all });

      onNewMention?.(mention);
    });

    client.connect();

    return () => {
      unsubConnect();
      unsubDisconnect();
      unsubSentiment();
      unsubMention();
      client.disconnect();
      clientRef.current = null;
    };
  }, [enabled, productId, onConnect, onDisconnect, onSentimentUpdate, onNewMention, queryClient]);

  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  return {
    isConnected,
    connect,
    disconnect,
    latestUpdate,
  };
}



