/**
 * Transaction History Component
 * 
 * Displays recent MNEE transactions for the connected wallet.
* */

'use client'

import { useState, useEffect } from 'react'
import { useAccount } from 'wagmi'
import { 
  Clock, 
  ArrowUpRight, 
  ArrowDownLeft, 
  ExternalLink,
  RefreshCw,
  Loader2
} from 'lucide-react'
import {
  fetchMNEETransactions,
  formatAddress,
  formatTimestamp,
  getEtherscanTxUrl,
  type MNEETransaction
} from '@/lib/web3/etherscan'

export function TransactionHistory() {
  const { address, isConnected } = useAccount()
  const [transactions, setTransactions] = useState<MNEETransaction[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTransactions = async () => {
    if (!address) return

    setIsLoading(true)
    setError(null)

    try {
      const txs = await fetchMNEETransactions(address)
      setTransactions(txs)
    } catch (err) {
      setError('Failed to load transactions')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  // Load transactions when wallet connects
  useEffect(() => {
    if (isConnected && address) {
      loadTransactions()
    } else {
      setTransactions([])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, address])

  if (!isConnected) {
    return (
      <div className="bg-gray-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">
          MNEE Transactions
        </h3>
        <div className="flex flex-col items-center justify-center py-8 text-gray-400">
          <Clock className="w-12 h-12 mb-3 opacity-50" />
          <p>Connect wallet to view transactions</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">
          MNEE Transactions
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={loadTransactions}
            disabled={isLoading}
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
            title="Refresh"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
          </button>
          <a
            href={`https://etherscan.io/token/0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF?a=${address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
          >
            View all <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {isLoading && transactions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-gray-400">
          <Loader2 className="w-8 h-8 mb-3 animate-spin" />
          <p>Loading transactions...</p>
        </div>
      ) : transactions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-gray-400">
          <Clock className="w-12 h-12 mb-3 opacity-50" />
          <p className="font-medium">No MNEE transactions yet</p>
          <p className="text-sm mt-1">Your transactions will appear here</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-80 overflow-y-auto">
          {transactions.map((tx) => (
            <a
              key={tx.hash}
              href={getEtherscanTxUrl(tx.hash)}
              target="_blank"
              rel="noopener noreferrer"
              className="block p-3 bg-gray-700/50 hover:bg-gray-700 rounded-lg transition-colors group"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-full ${
                      tx.type === 'sent'
                        ? 'bg-red-900/30 text-red-400'
                        : 'bg-emerald-900/30 text-emerald-400'
                    }`}
                  >
                    {tx.type === 'sent' ? (
                      <ArrowUpRight className="w-4 h-4" />
                    ) : (
                      <ArrowDownLeft className="w-4 h-4" />
                    )}
                  </div>
                  <div>
                    <p className="text-white font-medium">
                      {tx.type === 'sent' ? 'Sent' : 'Received'}
                    </p>
                    <p className="text-gray-400 text-sm">
                      {tx.type === 'sent' ? 'To: ' : 'From: '}
                      {formatAddress(tx.type === 'sent' ? tx.to : tx.from)}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p
                    className={`font-medium ${
                      tx.type === 'sent' ? 'text-red-400' : 'text-emerald-400'
                    }`}
                  >
                    {tx.type === 'sent' ? '-' : '+'}
                    {tx.valueFormatted} MNEE
                  </p>
                  <p className="text-gray-500 text-sm">
                    {formatTimestamp(tx.timestamp)}
                  </p>
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                <span>TX: {formatAddress(tx.hash)}</span>
                <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

export default TransactionHistory
