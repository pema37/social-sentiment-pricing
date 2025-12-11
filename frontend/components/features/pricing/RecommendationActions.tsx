// Recommendation Actions Component
// Approve/reject buttons with rejection reason modal

'use client';

import { useState, useCallback } from 'react';
import { Check, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

// ============================================
// TYPES
// ============================================

interface RecommendationActionsProps {
  recommendationId: string;
  onApprove: (id: string, notes?: string) => Promise<void>;
  onReject: (id: string, reason: string) => Promise<void>;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

// ============================================
// REJECT MODAL
// ============================================

interface RejectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isLoading: boolean;
}

function RejectModal({ isOpen, onClose, onConfirm, isLoading }: RejectModalProps) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setError('');

      const trimmedReason = reason.trim();
      if (!trimmedReason) {
        setError('Please provide a reason for rejection');
        return;
      }

      if (trimmedReason.length < 10) {
        setError('Reason must be at least 10 characters');
        return;
      }

      onConfirm(trimmedReason);
    },
    [reason, onConfirm]
  );

  const handleClose = useCallback(() => {
    if (!isLoading) {
      setReason('');
      setError('');
      onClose();
    }
  }, [isLoading, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reject-modal-title"
      >
        <h2
          id="reject-modal-title"
          className="text-lg font-semibold text-gray-900 mb-4"
        >
          Reject Recommendation
        </h2>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label
              htmlFor="rejection-reason"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Reason for Rejection
            </label>
            <textarea
              id="rejection-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain why this price recommendation should not be applied..."
              rows={4}
              className={cn(
                'w-full px-3 py-2 border rounded-lg text-sm',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder:text-gray-400',
                error ? 'border-red-300' : 'border-gray-300'
              )}
              disabled={isLoading}
              autoFocus
            />
            {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
          </div>

          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="danger"
              disabled={isLoading || !reason.trim()}
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Rejecting...
                </>
              ) : (
                'Reject'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// MAIN COMPONENT
// ============================================

export function RecommendationActions({
  recommendationId,
  onApprove,
  onReject,
  disabled = false,
  size = 'md',
  className,
}: RecommendationActionsProps) {
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);

  const isLoading = isApproving || isRejecting;

  // Handle approve action
  const handleApprove = useCallback(async () => {
    if (isLoading || disabled) return;

    setIsApproving(true);
    try {
      await onApprove(recommendationId);
    } finally {
      setIsApproving(false);
    }
  }, [recommendationId, onApprove, isLoading, disabled]);

  // Handle reject confirmation
  const handleRejectConfirm = useCallback(
    async (reason: string) => {
      setIsRejecting(true);
      try {
        await onReject(recommendationId, reason);
        setShowRejectModal(false);
      } finally {
        setIsRejecting(false);
      }
    },
    [recommendationId, onReject]
  );

  return (
    <>
      <div className={cn('flex items-center gap-2', className)}>
        {/* Reject Button */}
        <Button
          variant="secondary"
          size={size}
          onClick={() => setShowRejectModal(true)}
          disabled={isLoading || disabled}
        >
          <X className="h-4 w-4 mr-1.5" />
          Reject
        </Button>

        {/* Approve Button */}
        <Button
          variant="primary"
          size={size}
          onClick={handleApprove}
          disabled={isLoading || disabled}
        >
          {isApproving ? (
            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
          ) : (
            <Check className="h-4 w-4 mr-1.5" />
          )}
          {isApproving ? 'Approving...' : 'Approve'}
        </Button>
      </div>

      {/* Rejection Modal */}
      <RejectModal
        isOpen={showRejectModal}
        onClose={() => setShowRejectModal(false)}
        onConfirm={handleRejectConfirm}
        isLoading={isRejecting}
      />
    </>
  );
}
