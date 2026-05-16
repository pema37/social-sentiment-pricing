'use client';

// frontend/components/features/payments/BsvWalletCard.tsx

import { useState } from 'react';
import { Wallet, Check, X, RefreshCw, ExternalLink, Copy } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useWallet, useUpdateWallet, useRemoveWallet } from '@/lib/hooks/use-payments';
import { isValidBsvAddress, formatMneeAmount } from '@/lib/api/payments';
import { useToast } from '@/lib/hooks/use-toast';

export function BsvWalletCard() {
  const { data: wallet, isLoading, refetch } = useWallet();
  const updateWallet = useUpdateWallet();
  const removeWallet = useRemoveWallet();
  const toast = useToast();

  const [isEditing, setIsEditing] = useState(false);
  const [address, setAddress] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleStartEdit = () => {
    setAddress(wallet?.bsv_wallet_address || '');
    setValidationError(null);
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setAddress('');
    setValidationError(null);
    setIsEditing(false);
  };

  const handleAddressChange = (value: string) => {
    setAddress(value);
    
    if (!value) {
      setValidationError(null);
      return;
    }

    // Check for Ethereum address
    if (value.startsWith('0x')) {
      setValidationError('Ethereum addresses (0x...) are not supported. MNEE uses BSV addresses starting with "1" or "3".');
      return;
    }

    // Validate BSV format
    if (!isValidBsvAddress(value)) {
      setValidationError('Invalid BSV address. Must start with "1" or "3" and be 25-34 characters.');
      return;
    }

    setValidationError(null);
  };

  const handleSave = async () => {
    if (!address || validationError) return;

    try {
      await updateWallet.mutateAsync({ bsv_wallet_address: address });
      toast.success({
        title: 'Wallet saved',
        message: 'Your BSV wallet address has been saved.',
      });
      setIsEditing(false);
    } catch {
      // ========== FIX: Removed unused 'error' variable ==========
      toast.error({
        title: 'Error',
        message: 'Failed to save wallet address. Please try again.',
      });
    }
  };

  const handleRemove = async () => {
    try {
      await removeWallet.mutateAsync();
      toast.success({
        title: 'Wallet removed',
        message: 'Your wallet address has been removed.',
      });
    } catch {
      // ========== FIX: Removed unused 'error' variable ==========
      toast.error({
        title: 'Error',
        message: 'Failed to remove wallet. Please try again.',
      });
    }
  };

  const handleCopy = async () => {
    if (wallet?.bsv_wallet_address) {
      try {
        await navigator.clipboard.writeText(wallet.bsv_wallet_address);
        toast.success('Wallet address copied to clipboard');
      } catch {
        toast.error({ title: 'Copy failed', message: 'Could not copy to clipboard' });
      }
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-10 bg-gray-200 rounded w-full"></div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Wallet className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">BSV Wallet</h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {isEditing ? (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              BSV Wallet Address
            </label>
            <Input
              value={address}
              onChange={(e) => handleAddressChange(e.target.value)}
              placeholder="1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
              className={validationError ? 'border-red-500' : ''}
            />
            {validationError && (
              <p className="mt-1 text-sm text-red-600">{validationError}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              Get your address from{' '}
              <a 
                href="https://handcash.io" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                HandCash
              </a>
              {' '}or{' '}
              <a 
                href="https://relayx.com" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                RelayX
              </a>
            </p>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={handleSave}
              disabled={!address || !!validationError || updateWallet.isPending}
              className="flex-1"
              isLoading={updateWallet.isPending}
            >
              <Check className="h-4 w-4 mr-2" />
              Save
            </Button>
            <Button variant="secondary" onClick={handleCancelEdit}>
              <X className="h-4 w-4 mr-2" />
              Cancel
            </Button>
          </div>
        </div>
      ) : wallet?.bsv_wallet_address ? (
        <div className="space-y-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">Address</span>
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" onClick={handleCopy}>
                  <Copy className="h-4 w-4" />
                </Button>
                <a
                  href={`https://whatsonchain.com/address/${wallet.bsv_wallet_address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button variant="ghost" size="sm">
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </a>
              </div>
            </div>
            <p className="font-mono text-sm break-all">
              {wallet.bsv_wallet_address}
            </p>
          </div>

          {wallet.balance !== null && (
            <div className="bg-green-50 rounded-lg p-4">
              <span className="text-sm text-gray-500">MNEE Balance</span>
              <p className="text-2xl font-bold text-green-600">
                {formatMneeAmount(wallet.balance)}
              </p>
              <p className="text-sm text-gray-500">
                ≈ ${wallet.balance} USD
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleStartEdit} className="flex-1">
              Change Address
            </Button>
            <Button
              variant="danger"
              onClick={handleRemove}
              disabled={removeWallet.isPending}
              isLoading={removeWallet.isPending}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="text-center py-6">
          <Wallet className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 mb-4">No wallet connected</p>
          <Button onClick={handleStartEdit}>
            Connect BSV Wallet
          </Button>
        </div>
      )}
    </Card>
  );
}

