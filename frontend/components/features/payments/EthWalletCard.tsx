// frontend/components/features/payments/EthWalletCard.tsx
'use client';

import { useState, useEffect } from 'react';
import { useAccount, useDisconnect } from 'wagmi';
import { useConnectModal } from '@rainbow-me/rainbowkit';
import { Wallet, ExternalLink, Copy, Check, LogOut, Loader2, Edit2, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useMNEE } from '@/lib/web3/useMNEE';
import { api } from '@/lib/api/client';

// MNEE ERC-20 Contract on Ethereum
const MNEE_CONTRACT = '0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF';

interface WalletResponse {
  eth_wallet_address: string | null;
  bsv_wallet_address: string | null;
}

export function EthWalletCard() {
  const { address: connectedAddress, isConnected } = useAccount();
  const { disconnect } = useDisconnect();
  const { openConnectModal } = useConnectModal();
  const { balance, isLoadingBalance } = useMNEE();
  
  const [copied, setCopied] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [savedAddress, setSavedAddress] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [manualAddress, setManualAddress] = useState('');
  const [addressError, setAddressError] = useState('');

  // Use connected wallet address or saved manual address
  const displayAddress = connectedAddress || savedAddress;
  const isManualMode = !isConnected && !!savedAddress;

  // Load saved wallet on mount
  useEffect(() => {
    const loadSavedWallet = async () => {
      try {
        const response = await api.get<WalletResponse>('/api/v1/users/me/wallet');
        setSavedAddress(response.eth_wallet_address);
      } catch (error) {
        console.error('Failed to load wallet:', error);
      }
    };
    loadSavedWallet();
  }, []);

  // Save wallet when connected via RainbowKit
  useEffect(() => {
    const saveWallet = async () => {
      if (isConnected && connectedAddress && connectedAddress !== savedAddress) {
        setIsSaving(true);
        try {
          await api.put<WalletResponse>('/api/v1/users/me/wallet', {
            eth_wallet_address: connectedAddress,
          });
          setSavedAddress(connectedAddress);
        } catch (error) {
          console.error('Failed to save wallet:', error);
        } finally {
          setIsSaving(false);
        }
      }
    };
    saveWallet();
  }, [isConnected, connectedAddress, savedAddress]);

  const validateEthAddress = (address: string): boolean => {
    return /^0x[a-fA-F0-9]{40}$/.test(address);
  };

  const handleSaveManualAddress = async () => {
    const trimmed = manualAddress.trim();
    
    if (!trimmed) {
      setAddressError('Please enter an address');
      return;
    }
    
    if (!validateEthAddress(trimmed)) {
      setAddressError('Invalid Ethereum address (must start with 0x and be 42 characters)');
      return;
    }

    setIsSaving(true);
    setAddressError('');
    
    try {
      await api.put<WalletResponse>('/api/v1/users/me/wallet', {
        eth_wallet_address: trimmed.toLowerCase(),
      });
      setSavedAddress(trimmed.toLowerCase());
      setIsEditing(false);
      setManualAddress('');
    } catch (error) {
      console.error('Failed to save wallet:', error);
      setAddressError('Failed to save address');
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearAddress = async () => {
    setIsSaving(true);
    try {
      await api.put<WalletResponse>('/api/v1/users/me/wallet', {
        eth_wallet_address: null,
      });
      setSavedAddress(null);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to clear wallet:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopyAddress = () => {
    if (displayAddress) {
      navigator.clipboard.writeText(displayAddress);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const truncateAddress = (addr: string) => {
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  const handleDisconnect = () => {
    disconnect();
  };

  const handleStartEditing = () => {
    setIsEditing(true);
    setManualAddress(savedAddress || '');
    setAddressError('');
  };

  const handleCancelEditing = () => {
    setIsEditing(false);
    setManualAddress('');
    setAddressError('');
  };

  // Safe balance formatting helper
  const formatBalance = (bal: unknown): string => {
    if (bal == null) return '0.00';
    const num = Number(bal);
    if (isNaN(num)) return '0.00';
    return num.toFixed(2);
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Wallet className="w-5 h-5 text-purple-600" />
          Ethereum Wallet
        </h2>
        {(isConnected || isManualMode) && (
          <span className="flex items-center gap-1.5 text-sm text-green-600">
            {isSaving ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Saving...
              </>
            ) : isManualMode ? (
              <>
                <span className="w-2 h-2 bg-yellow-500 rounded-full" />
                View Only
              </>
            ) : (
              <>
                <span className="w-2 h-2 bg-green-500 rounded-full" />
                Connected
              </>
            )}
          </span>
        )}
      </div>

      {/* Editing Mode - Manual Address Entry */}
      {isEditing && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">
              ETH Wallet Address
            </label>
            <input
              type="text"
              value={manualAddress}
              onChange={(e) => {
                setManualAddress(e.target.value);
                setAddressError('');
              }}
              placeholder="0x..."
              className={`w-full px-3 py-2 border rounded-lg text-sm font-mono ${
                addressError ? 'border-red-300' : 'border-gray-300'
              } focus:outline-none focus:ring-2 focus:ring-purple-500`}
            />
            {addressError && (
              <p className="text-red-500 text-xs mt-1">{addressError}</p>
            )}
            <p className="text-xs text-gray-500 mt-1">
              Enter your Ethereum address to view your MNEE balance
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={handleSaveManualAddress}
              isLoading={isSaving}
              disabled={isSaving}
              className="flex-1"
            >
              <Check className="w-4 h-4 mr-1" />
              Save
            </Button>
            <Button
              variant="secondary"
              onClick={handleCancelEditing}
              disabled={isSaving}
            >
              <X className="w-4 h-4 mr-1" />
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* No Wallet Connected - Show Connect Options */}
      {!isEditing && !displayAddress && (
        <div className="text-center py-6">
          <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Wallet className="w-8 h-8 text-purple-600" />
          </div>
          <p className="text-gray-600 mb-4">
            Connect your Ethereum wallet to pay with MNEE ERC-20 tokens.
          </p>
          <div className="space-y-2">
            <Button onClick={openConnectModal} className="w-full">
              Connect Wallet
            </Button>
            <Button variant="secondary" onClick={handleStartEditing} className="w-full">
              <Edit2 className="w-4 h-4 mr-2" />
              Enter Address Manually
            </Button>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            Supports MetaMask, Rainbow, Coinbase Wallet, and more
          </p>
        </div>
      )}

      {/* Wallet Connected or Manual Address Saved */}
      {!isEditing && displayAddress && (
        <div className="space-y-4">
          {/* Address */}
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs text-gray-500">Wallet Address</p>
              {isManualMode && (
                <button
                  onClick={handleStartEditing}
                  className="text-xs text-purple-600 hover:underline"
                >
                  Edit
                </button>
              )}
            </div>
            <div className="flex items-center justify-between">
              <code className="text-sm font-mono">{truncateAddress(displayAddress)}</code>
              <div className="flex gap-1">
                <button
                  onClick={handleCopyAddress}
                  className="p-1.5 hover:bg-gray-200 rounded transition-colors"
                  title="Copy address"
                >
                  {copied ? (
                    <Check className="w-4 h-4 text-green-600" />
                  ) : (
                    <Copy className="w-4 h-4 text-gray-500" />
                  )}
                </button>
                <a
                  href={`https://etherscan.io/address/${displayAddress}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 hover:bg-gray-200 rounded transition-colors"
                  title="View on Etherscan"
                >
                  <ExternalLink className="w-4 h-4 text-gray-500" />
                </a>
              </div>
            </div>
          </div>

          {/* MNEE Balance - Only show for connected wallets (not manual) */}
          {isConnected && (
            <div className="bg-purple-50 rounded-lg p-4">
              <p className="text-xs text-purple-600 mb-1">MNEE Balance</p>
              {isLoadingBalance ? (
                <div className="h-8 w-24 bg-purple-100 animate-pulse rounded" />
              ) : (
                <p className="text-2xl font-bold text-purple-900">
                  {formatBalance(balance)} MNEE
                </p>
              )}
              <p className="text-xs text-purple-600 mt-1">≈ ${formatBalance(balance)} USD</p>
            </div>
          )}

          {/* Manual mode info */}
          {isManualMode && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-xs text-yellow-800">
                <strong>View-only mode:</strong> Connect a wallet to see your balance and make payments.
              </p>
            </div>
          )}

          {/* Contract Info */}
          <div className="text-xs text-gray-500">
            <p>MNEE Contract:</p>
            <a
              href={`https://etherscan.io/token/${MNEE_CONTRACT}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-purple-600 hover:underline break-all"
            >
              {MNEE_CONTRACT}
            </a>
          </div>

          {/* Disconnect / Clear */}
          {isConnected ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDisconnect}
              className="w-full text-gray-500 hover:text-red-600"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Disconnect Wallet
            </Button>
          ) : (
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={openConnectModal}
                className="flex-1"
              >
                Connect Wallet
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearAddress}
                className="text-gray-500 hover:text-red-600"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default EthWalletCard;


