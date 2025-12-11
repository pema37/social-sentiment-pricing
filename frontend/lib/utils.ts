// Utility functions used throughout the app

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Merge Tailwind classes safely (handles conflicts like "p-2 p-4" → "p-4")
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Format number as currency (e.g., 1234.56 → "$1,234.56")
export function formatCurrency(amount: number | string, currency = 'USD'): string {
  const numAmount = typeof amount === 'string' ? parseFloat(amount) : amount;
  
  if (isNaN(numAmount)) {
    return '$0.00';
  }
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(numAmount);
}

// Format percentage with sign (e.g., 3.5 → "+3.5%", -2.1 → "-2.1%")
export function formatPercentage(value: number | string, decimals = 1): string {
  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  
  if (isNaN(numValue)) {
    return '0%';
  }
  
  return `${numValue >= 0 ? '+' : ''}${numValue.toFixed(decimals)}%`;
}

// Format date (e.g., "2024-01-15" → "Jan 15, 2024")
export function formatDate(date: string | Date | null | undefined): string {
  if (!date) {
    return 'N/A';
  }
  
  const dateObj = new Date(date);
  
  if (isNaN(dateObj.getTime())) {
    return 'Invalid date';
  }
  
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(dateObj);
}

// Format relative time (e.g., "5m ago", "2h ago", "3d ago")
export function formatRelativeTime(date: string | Date | null | undefined): string {
  if (!date) {
    return 'N/A';
  }
  
  const then = new Date(date);
  
  if (isNaN(then.getTime())) {
    return 'Invalid date';
  }
  
  const now = new Date();
  const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);
  
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  
  return formatDate(date);
}
