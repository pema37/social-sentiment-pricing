// frontend/components/features/payments/EthWalletCard.tsx
'use client';

import { useState, useEffect } from 'react';
import { useAccount, useDisconnect } from 'wagmi';
import { useConnectModal } from '@rainbow-me/rainbowkit';
import { Wallet, ExternalLink, Copy, Check, LogOut, Loader2 } from 'lucide-react';
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
  const { address, isConnected } = useAccount();
  const { disconnect } = useDisconnect();
  const { openConnectModal } = useConnectModal();
  const { balance, isLoadingBalance } = useMNEE();
  
  const [copied, setCopied] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [savedAddress, setSavedAddress] = useState<string | null>(null);

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

  // Save wallet when connected
  useEffect(() => {
    const saveWallet = async () => {
      if (isConnected && address && address !== savedAddress) {
        setIsSaving(true);
        try {
          await api.put<WalletResponse>('/api/v1/users/me/wallet', {
            eth_wallet_address: address,
          });
          setSavedAddress(address);
        } catch (error) {
          console.error('Failed to save wallet:', error);
        } finally {
          setIsSaving(false);
        }
      }
    };
    saveWallet();
  }, [isConnected, address, savedAddress]);

  const handleCopyAddress = () => {
    if (address) {
      navigator.clipboard.writeText(address);
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

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Wallet className="w-5 h-5 text-purple-600" />
          Ethereum Wallet
        </h2>
        {isConnected && (
          <span className="flex items-center gap-1.5 text-sm text-green-600">
            {isSaving ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Saving...
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

      {!isConnected ? (
        <div className="text-center py-6">
          <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Wallet className="w-8 h-8 text-purple-600" />
          </div>
          <p className="text-gray-600 mb-4">
            Connect your Ethereum wallet to pay with MNEE ERC-20 tokens.
          </p>
          <Button onClick={openConnectModal}>
            Connect Wallet
          </Button>
          <p className="text-xs text-gray-500 mt-3">
            Supports MetaMask, Rainbow, Coinbase Wallet, and more
          </p>
          {savedAddress && (
            <p className="text-xs text-gray-400 mt-2">
              Previously connected: {truncateAddress(savedAddress)}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Address */}
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Wallet Address</p>
            <div className="flex items-center justify-between">
              <code className="text-sm font-mono">{truncateAddress(address!)}</code>
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
                  href={`https://etherscan.io/address/${address}`}
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

          {/* MNEE Balance */}
          <div className="bg-purple-50 rounded-lg p-4">
            <p className="text-xs text-purple-600 mb-1">MNEE Balance</p>
            {isLoadingBalance ? (
              <div className="h-8 w-24 bg-purple-100 animate-pulse rounded" />
            ) : (
              <p className="text-2xl font-bold text-purple-900">
                {balance ? Number(balance).toFixed(2) : '0.00'} MNEE
              </p>
            )}
            <p className="text-xs text-purple-600 mt-1">≈ ${balance ? Number(balance).toFixed(2) : '0.00'} USD</p>
          </div>

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

          {/* Disconnect */}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDisconnect}
            className="w-full text-gray-500 hover:text-red-600"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Disconnect Wallet
          </Button>
        </div>
      )}
    </Card>
  );
}

export default EthWalletCard;
