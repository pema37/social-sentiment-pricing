// frontend/components/features/payments/PaymentHistory.tsx

'use client';

import { Receipt, ExternalLink, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { usePaymentHistory } from '@/lib/hooks/use-payments';
import { formatMneeAmount } from '@/lib/api/payments';
import type { PaymentStatus } from '@/types/payment';

const STATUS_CONFIG: Record<PaymentStatus, { icon: React.ReactNode; color: string; label: string }> = {
  pending: {
    icon: <Clock className="h-4 w-4" />,
    color: 'bg-yellow-100 text-yellow-700',
    label: 'Pending',
  },
  processing: {
    icon: <Clock className="h-4 w-4 animate-spin" />,
    color: 'bg-blue-100 text-blue-700',
    label: 'Processing',
  },
  confirmed: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: 'bg-green-100 text-green-700',
    label: 'Confirmed',
  },
  failed: {
    icon: <XCircle className="h-4 w-4" />,
    color: 'bg-red-100 text-red-700',
    label: 'Failed',
  },
  expired: {
    icon: <AlertCircle className="h-4 w-4" />,
    color: 'bg-gray-100 text-gray-700',
    label: 'Expired',
  },
  refunded: {
    icon: <Receipt className="h-4 w-4" />,
    color: 'bg-purple-100 text-purple-700',
    label: 'Refunded',
  },
};

export function PaymentHistory() {
  const { data, isLoading } = usePaymentHistory(10);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateTxid = (txid: string) => {
    if (txid.length <= 16) return txid;
    return `${txid.slice(0, 8)}...${txid.slice(-8)}`;
  };

  if (isLoading) {
    return (
      <Card className="p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-200 rounded"></div>
          ))}
        </div>
      </Card>
    );
  }

  const payments = data?.payments || [];

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <Receipt className="h-5 w-5 text-blue-600" />
        <h3 className="text-lg font-semibold">Payment History</h3>
      </div>

      {payments.length === 0 ? (
        <div className="text-center py-8">
          <Receipt className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No payment history yet</p>
          <p className="text-sm text-gray-400">
            Your payments will appear here once you subscribe to a plan.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {payments.map((payment) => {
            const statusConfig = STATUS_CONFIG[payment.status];
            
            return (
              <div
                key={payment.id}
                className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`flex items-center gap-1 text-sm px-2 py-1 rounded ${statusConfig.color}`}>
                        {statusConfig.icon}
                        {statusConfig.label}
                      </span>
                      <span className="text-sm text-gray-500 capitalize">
                        {payment.payment_type.replace('_', ' ')}
                      </span>
                    </div>
                    
                    {payment.description && (
                      <p className="text-sm text-gray-600">{payment.description}</p>
                    )}
                    
                    <p className="text-xs text-gray-400">
                      {formatDate(payment.created_at)}
                    </p>
                  </div>

                  <div className="text-right">
                    <p className="font-bold text-lg">
                      {formatMneeAmount(payment.amount)}
                    </p>
                    <p className="text-sm text-gray-500">
                      ≈ ${payment.amount} USD
                    </p>
                  </div>
                </div>

                {payment.txid && (
                  <div className="mt-3 pt-3 border-t">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500">Transaction:</span>
                      <a
                        href={`https://whatsonchain.com/tx/${payment.txid}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-blue-600 hover:underline font-mono"
                      >
                        {truncateTxid(payment.txid)}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                )}

                {payment.memo && (
                  <div className="mt-2 text-xs text-gray-400">
                    Memo: {payment.memo}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {data && data.total > payments.length && (
        <div className="mt-4 text-center">
          <button className="text-sm text-blue-600 hover:underline">
            Load more ({data.total - payments.length} remaining)
          </button>
        </div>
      )}
    </Card>
  );
}
