// frontend/lib/ws/index.ts
/**
 * WebSocket module exports
 */

export { WebSocketClient, createAlertsClient, createPricesClient, createSentimentClient } from './client';
export { useRealtimeAlerts, useRealtimePrices, useRealtimeSentiment } from './hooks';


