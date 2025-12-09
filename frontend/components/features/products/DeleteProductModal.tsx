// components/products/DeleteProductModal.tsx
'use client';

import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useDeleteProduct } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface DeleteProductModalProps {
  productId: string;
  productName: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function DeleteProductModal({
  productId,
  productName,
  isOpen,
  onClose,
  onSuccess,
}: DeleteProductModalProps) {
  const deleteProduct = useDeleteProduct();

  if (!isOpen) return null;

  const handleDelete = () => {
    deleteProduct.mutate(productId, {
      onSuccess: () => {
        onClose();
        onSuccess?.();
      },
    });
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-xl max-w-md w-full shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-100 rounded-full">
              <AlertTriangle className="h-5 w-5 text-red-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Delete Product</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          <p className="text-gray-600">
            Are you sure you want to delete{' '}
            <span className="font-semibold text-gray-900">{productName}</span>?
          </p>
          <p className="mt-2 text-sm text-gray-500">
            This action cannot be undone. All price history and sentiment data
            associated with this product will be permanently removed.
          </p>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-4 border-t bg-gray-50 rounded-b-xl">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={deleteProduct.isPending}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            isLoading={deleteProduct.isPending}
            className="flex-1"
          >
            Delete Product
          </Button>
        </div>
      </div>
    </div>
  );
}

export default DeleteProductModal;
