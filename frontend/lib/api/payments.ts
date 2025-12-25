// frontend/lib/api/payments.ts

/**
 * Payment API Client
 * 
 * Handles all MNEE payment-related API calls to our backend.
 */

import { api } from './client';
import type {
  WalletInfo,
  WalletUpdateRequest,
  BalanceInfo,
  PlansResponse,
  Subscription,
  SubscribeRequest,
  PaymentRequest,
  Payment,
  PaymentHistoryResponse,
} from '@/types/payment';

// =============================================================================
// Wallet Endpoints
// =============================================================================

/**
 * Get current user's wallet info and balance
 */
export async function getWallet(): Promise<WalletInfo> {
  return api.get<WalletInfo>('/api/v1/payments/wallet');
}

/**
 * Update user's BSV wallet address
 */
export async function updateWallet(data: WalletUpdateRequest): Promise<WalletInfo> {
  return api.put<WalletInfo>('/api/v1/payments/wallet', data);
}

/**
 * Remove user's wallet address
 */
export async function removeWallet(): Promise<void> {
  return api.delete<void>('/api/v1/payments/wallet');
}

/**
 * Check balance for any BSV address
 */
export async function checkBalance(address: string): Promise<BalanceInfo> {
  return api.get<BalanceInfo>(`/api/v1/payments/balance/${address}`);
}

// =============================================================================
// Subscription Endpoints
// =============================================================================

/**
 * Get all available subscription plans
 */
export async function getPlans(): Promise<PlansResponse> {
  return api.get<PlansResponse>('/api/v1/payments/plans');
}

/**
 * Get current user's subscription
 */
export async function getSubscription(): Promise<Subscription> {
  return api.get<Subscription>('/api/v1/payments/subscription');
}

/**
 * Subscribe to a plan (creates payment request)
 */
export async function subscribe(data: SubscribeRequest): Promise<PaymentRequest> {
  return api.post<PaymentRequest>('/api/v1/payments/subscribe', data);
}

// =============================================================================
// Payment Endpoints
// =============================================================================

/**
 * Get payment status by ID
 */
export async function getPayment(paymentId: string): Promise<Payment> {
  return api.get<Payment>(`/api/v1/payments/payments/${paymentId}`);
}

/**
 * Get payment history
 */
export async function getPaymentHistory(
  limit: number = 20,
  offset: number = 0
): Promise<PaymentHistoryResponse> {
  return api.get<PaymentHistoryResponse>('/api/v1/payments/history', { limit, offset });
}

// =============================================================================
// Validation Helpers
// =============================================================================

/**
 * Validate BSV address format (client-side)
 */
export function isValidBsvAddress(address: string): boolean {
  // BSV addresses start with 1 or 3, are 25-34 characters
  if (!address) return false;
  
  // Reject Ethereum addresses
  if (address.startsWith('0x')) return false;
  
  // Check BSV format
  if (!address.startsWith('1') && !address.startsWith('3')) return false;
  
  // Check length
  if (address.length < 25 || address.length > 34) return false;
  
  // Base58 characters (no 0, O, I, l)
  const base58Regex = /^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$/;
  return base58Regex.test(address);
}

/**
 * Format MNEE amount for display
 */
export function formatMneeAmount(amount: string | number): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return `${num.toFixed(2)} MNEE`;
}

/**
 * Format USD equivalent
 */
export function formatUsdAmount(amount: string | number): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return `$${num.toFixed(2)} USD`;
}
