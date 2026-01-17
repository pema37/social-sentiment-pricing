// Notification bell component for header with real-time WebSocket support
'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { Bell, Wifi, WifiOff } from 'lucide-react';
import { useUnreadAlertCount, useAlerts } from '@/lib/hooks/use-alerts';
import { useRealtimeAlerts } from '@/lib/ws';
import { useToast } from '@/lib/hooks/use-toast';
import { AlertItem } from './AlertItem';

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const toast = useToast();
  
  // Existing query-based data
  const { data: unreadData, refetch: refetchUnread } = useUnreadAlertCount();
  const { data: alertsData, isLoading, refetch: refetchAlerts } = useAlerts({ 
    limit: 5, 
    status: 'pending' 
  });
  
  // Real-time WebSocket alerts
  const { 
    isConnected, 
    latestAlert, 
    alertCount: newAlertCount,
    clearAlertCount 
  } = useRealtimeAlerts({
    enabled: true,
    onNewAlert: (alert) => {
      // Show toast notification for new alerts
      toast.info({
        title: alert.title || 'New Alert',
        message: alert.message || 'You have a new notification',
      });
      
      // Refetch to update the list
      refetchUnread();
      refetchAlerts();
    },
  });

  // Calculate total unread (API count + new real-time alerts)
  const baseUnreadCount = unreadData?.unread_count ?? 0;
  const totalUnread = baseUnreadCount + newAlertCount;

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Clear new alert count when dropdown is opened
  useEffect(() => {
    if (isOpen && newAlertCount > 0) {
      clearAlertCount();
    }
  }, [isOpen, newAlertCount, clearAlertCount]);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        aria-label={`Notifications${totalUnread > 0 ? ` (${totalUnread} unread)` : ''}`}
      >
        <Bell className="w-5 h-5" />
        
        {/* Unread badge */}
        {totalUnread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-4.5 h-4.5 px-1 text-xs font-bold text-white bg-red-500 rounded-full animate-pulse">
            {totalUnread > 99 ? '99+' : totalUnread}
          </span>
        )}
        
        {/* Connection indicator (small dot) */}
        <span 
          className={`absolute bottom-0.5 right-0.5 w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-gray-300'
          }`}
          title={isConnected ? 'Real-time connected' : 'Connecting...'}
        />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-gray-900">Notifications</h3>
              {/* Real-time status indicator */}
              <span 
                className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                  isConnected 
                    ? 'bg-green-100 text-green-700' 
                    : 'bg-gray-100 text-gray-500'
                }`}
                title={isConnected ? 'Real-time updates active' : 'Connecting to real-time...'}
              >
                {isConnected ? (
                  <>
                    <Wifi className="w-3 h-3" />
                    <span className="hidden sm:inline">Live</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-3 h-3" />
                    <span className="hidden sm:inline">Offline</span>
                  </>
                )}
              </span>
            </div>
            {totalUnread > 0 && (
              <span className="text-xs text-gray-500">{totalUnread} unread</span>
            )}
          </div>

          {/* Latest real-time alert highlight */}
          {latestAlert && (
            <div className="px-4 py-2 bg-blue-50 border-b border-blue-100">
              <p className="text-xs text-blue-600 font-medium">Latest:</p>
              <p className="text-sm text-blue-800 truncate">
                {latestAlert.title || latestAlert.message}
              </p>
            </div>
          )}

          {/* Alerts list */}
          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-center text-gray-500">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-400 mx-auto mb-2" />
                Loading...
              </div>
            ) : alertsData?.items && alertsData.items.length > 0 ? (
              alertsData.items.map((alert) => (
                <AlertItem key={alert.id} alert={alert} />
              ))
            ) : (
              <div className="p-6 text-center">
                <Bell className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-gray-500">No pending alerts</p>
                <p className="text-xs text-gray-400 mt-1">
                  {isConnected 
                    ? "You'll be notified in real-time" 
                    : 'Connecting to real-time updates...'}
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-100 p-2">
            <Link
              href="/alerts"
              onClick={() => setIsOpen(false)}
              className="block w-full px-4 py-2 text-sm text-center text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
            >
              View all alerts
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}


