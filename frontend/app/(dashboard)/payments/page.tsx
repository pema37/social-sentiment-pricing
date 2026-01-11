'use client';

import { useState } from 'react';
import { useChainId } from 'wagmi';
import { SectionHeader } from '@/components/ui/SectionHeader';
import {
  BsvWalletCard,
  CurrentPlan,
  SubscriptionPlans,
  PaymentHistory,
} from '@/components/features/payments';
import { EthWalletCard } from '@/components/features/payments/EthWalletCard';
import { getMneeContractAddress, getNetworkName } from '@/lib/web3/config';

type PaymentNetwork = 'ethereum' | 'bsv';

export default function PaymentsPage() {
  const [activeNetwork, setActiveNetwork] = useState<PaymentNetwork>('ethereum');
  const chainId = useChainId();
  
  // Get network-aware contract address
  const mneeContract = getMneeContractAddress(chainId);
  const networkName = getNetworkName(chainId);

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Payments & Subscription"
        description="Manage your wallet and subscription plan. Pay with MNEE stablecoin."
      />

      {/* Network Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4" aria-label="Payment networks">
          <button
            onClick={() => setActiveNetwork('ethereum')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeNetwork === 'ethereum'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <span className="flex items-center gap-2">
              <EthereumIcon />
              Ethereum (MNEE ERC-20)
            </span>
          </button>
          <button
            onClick={() => setActiveNetwork('bsv')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeNetwork === 'bsv'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <span className="flex items-center gap-2">
              <BsvIcon />
              BSV (MNEE)
            </span>
          </button>
        </nav>
      </div>

      {/* Network Info Banner */}
      {activeNetwork === 'ethereum' && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <p className="text-sm text-purple-800">
            <strong>MNEE ERC-20</strong> — Pay using MNEE tokens on Ethereum mainnet. 
            Connect your MetaMask or WalletConnect-compatible wallet.
          </p>
        </div>
      )}
      
      {activeNetwork === 'bsv' && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <p className="text-sm text-orange-800">
            <strong>MNEE on BSV</strong> — Pay using MNEE stablecoin on the BSV network. 
            Lower fees, faster transactions.
          </p>
        </div>
      )}

      {/* Wallet and Current Plan - Side by Side on Desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {activeNetwork === 'ethereum' ? <EthWalletCard /> : <BsvWalletCard />}
        <CurrentPlan />
      </div>

      {/* Subscription Plans */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Subscription Plans</h2>
        <SubscriptionPlans />
      </div>

      {/* Payment History */}
      <PaymentHistory />

      {/* Info Section */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900 mb-2">About MNEE Payments</h3>
        <div className="text-sm text-blue-800 space-y-2">
          <p>
            <strong>MNEE</strong> is a stablecoin where 1 MNEE = $1 USD, available on both Ethereum and BSV networks.
          </p>
          {activeNetwork === 'ethereum' ? (
            <p>
              On Ethereum, MNEE is an ERC-20 token. Connect your wallet (MetaMask, Rainbow, etc.) to pay for subscriptions.
              Contract ({networkName}): <code className="bg-blue-100 px-1 rounded text-xs">{mneeContract}</code>
            </p>
          ) : (
            <p>On BSV, use wallets like{' '} 
              <a            
                href="https://handcash.io"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:no-underline"
              >
                HandCash
              </a>{' '}
              or{' '}
              <a
                href="https://relayx.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:no-underline"
              >
                RelayX
              </a>
              . Minimal fees and fast transactions.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function EthereumIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 256 417" preserveAspectRatio="xMidYMid">
      <path fill="#343434" d="m127.961 0-2.795 9.5v275.668l2.795 2.79 127.962-75.638z" />
      <path fill="#8C8C8C" d="M127.962 0 0 212.32l127.962 75.639V154.158z" />
      <path fill="#3C3C3B" d="m127.961 312.187-1.575 1.92v98.199l1.575 4.6L256 236.587z" />
      <path fill="#8C8C8C" d="M127.962 416.905v-104.72L0 236.585z" />
      <path fill="#141414" d="m127.961 287.958 127.96-75.637-127.96-58.162z" />
      <path fill="#393939" d="m0 212.32 127.96 75.638v-133.8z" />
    </svg>
  );
}

function BsvIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="16" fill="#EAB300" />
      <path
        d="M22.5 16.5c0 3.5-2.5 6-6.5 6h-5v-12h5c4 0 6.5 2.5 6.5 6z"
        fill="white"
        stroke="white"
        strokeWidth="1.5"
      />
    </svg>
  );
}
