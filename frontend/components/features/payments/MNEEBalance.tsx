/**
 * MNEE Balance Component
 * 
 * Displays the user's MNEE stablecoin balance.
 * 1 MNEE = 1 USD
**/

'use client'

import { useMNEE } from '@/lib/web3'
import { useAccount } from 'wagmi'

interface MNEEBalanceProps {
  className?: string
  showUSD?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export function MNEEBalance({ 
  className = '', 
  showUSD = true,
  size = 'md' 
}: MNEEBalanceProps) {
  const { isConnected } = useAccount()
  const { balance, isLoadingBalance, refetchBalance } = useMNEE()
  
  if (!isConnected) {
    return null
  }
  
  const formattedBalance = parseFloat(balance).toFixed(2)
  
  const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl',
  }
  
  return (
    <button 
      className={`flex items-center gap-2 ${className}`}
      onClick={() => refetchBalance()}
      title="Click to refresh"
    >
      <div className="flex items-center justify-center w-8 h-8 bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-full">
        <span className="text-white font-bold text-xs">M</span>
      </div>
      
      <div className="flex flex-col text-left">
        {isLoadingBalance ? (
          <div className="animate-pulse">
            <div className="h-5 w-20 bg-gray-700 rounded" />
          </div>
        ) : (
          <>
            <span className={`font-semibold text-white ${sizeClasses[size]}`}>
              {formattedBalance} MNEE
            </span>
            {showUSD && (
              <span className="text-xs text-gray-400">
                ≈ ${formattedBalance} USD
              </span>
            )}
          </>
        )}
      </div>
    </button>
  )
}

export function MNEEBalanceCompact({ className = '' }: { className?: string }) {
  const { isConnected } = useAccount()
  const { balance, isLoadingBalance } = useMNEE()
  
  if (!isConnected) {
    return (
      <span className={`text-gray-500 ${className}`}>
        Connect wallet
      </span>
    )
  }
  
  if (isLoadingBalance) {
    return (
      <span className={`animate-pulse text-gray-500 ${className}`}>
        Loading...
      </span>
    )
  }
  
  const formattedBalance = parseFloat(balance).toFixed(2)
  
  return (
    <span className={`font-medium ${className}`}>
      {formattedBalance} MNEE
    </span>
  )
}

export function MNEEBalanceCard() {
  const { isConnected } = useAccount()
  const { balance, isLoadingBalance, refetchBalance } = useMNEE()
  
  const formattedBalance = parseFloat(balance).toFixed(2)
  
  return (
    <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-gray-400 text-sm font-medium">MNEE Balance</h3>
        <button
          onClick={() => refetchBalance()}
          className="text-gray-500 hover:text-gray-300 transition-colors"
          title="Refresh balance"
        >
          <RefreshIcon className="w-4 h-4" />
        </button>
      </div>
      
      {!isConnected ? (
        <div className="text-gray-500">
          Connect wallet to view balance
        </div>
      ) : isLoadingBalance ? (
        <div className="animate-pulse">
          <div className="h-8 w-32 bg-gray-700 rounded mb-2" />
          <div className="h-4 w-20 bg-gray-700 rounded" />
        </div>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">
              {formattedBalance}
            </span>
            <span className="text-lg text-emerald-500 font-medium">MNEE</span>
          </div>
          <div className="text-gray-400 text-sm mt-1">
            ≈ ${formattedBalance} USD
          </div>
        </>
      )}
      
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-700">
        <div className="w-2 h-2 bg-emerald-500 rounded-full" />
        <span className="text-xs text-gray-400">
          1 MNEE = 1 USD (Stablecoin)
        </span>
      </div>
    </div>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  )
}

export default MNEEBalance
