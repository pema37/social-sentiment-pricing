/**
 * Transaction History Component
 * 
 * Displays recent MNEE transactions for the connected wallet.
* */

'use client'

import { useMemo } from 'react'
import { useAccount, useChainId } from 'wagmi'
import { MNEE_CONTRACT_ADDRESS, getEtherscanUrl } from '@/lib/web3'

interface Transaction {
  hash: string
  from: string
  to: string
  value: string
  timestamp: number
}

interface TransactionHistoryProps {
  className?: string
  limit?: number
}

export function TransactionHistory({ className = '', limit = 10 }: TransactionHistoryProps) {
  const { address, isConnected } = useAccount()
  const chainId = useChainId()
  const etherscanUrl = getEtherscanUrl(chainId)
  
  // For production: fetch from Etherscan API
  // https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={MNEE_CONTRACT_ADDRESS}&address={address}
  const transactions = useMemo<Transaction[]>(() => {
    if (!isConnected || !address) return []
    return []
  }, [isConnected, address])
  
  if (!isConnected) {
    return (
      <div className={`bg-gray-800 rounded-xl p-6 ${className}`}>
        <h3 className="text-lg font-semibold text-white mb-4">Transaction History</h3>
        <p className="text-gray-400 text-center py-8">
          Connect your wallet to view transactions
        </p>
      </div>
    )
  }
  
  return (
    <div className={`bg-gray-800 rounded-xl p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">MNEE Transactions</h3>
        <a 
          href={`${etherscanUrl}/token/${MNEE_CONTRACT_ADDRESS}?a=${address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-emerald-500 hover:text-emerald-400"
        >
          View all →
        </a>
      </div>
      
      {transactions.length === 0 ? (
        <div className="text-center py-8">
          <div className="w-16 h-16 mx-auto mb-4 bg-gray-700 rounded-full flex items-center justify-center">
            <HistoryIcon className="w-8 h-8 text-gray-500" />
          </div>
          <p className="text-gray-400">No MNEE transactions yet</p>
          <p className="text-gray-500 text-sm mt-1">
            Your transactions will appear here
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {transactions.slice(0, limit).map((tx) => (
            <TransactionRow key={tx.hash} transaction={tx} userAddress={address!} etherscanUrl={etherscanUrl} />
          ))}
        </div>
      )}
    </div>
  )
}

function TransactionRow({
  transaction,
  userAddress,
  etherscanUrl,
}: {
  transaction: Transaction
  userAddress: string
  etherscanUrl: string
}) {
  const isSent = transaction.from.toLowerCase() === userAddress.toLowerCase()
  const amount = parseFloat(transaction.value)
  
  return (
    <a
      href={`${etherscanUrl}/tx/${transaction.hash}`}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-4 p-3 bg-gray-700/30 hover:bg-gray-700/50 rounded-lg transition-colors"
    >
      <div className={`
        w-10 h-10 rounded-full flex items-center justify-center
        ${isSent ? 'bg-red-500/20' : 'bg-emerald-500/20'}
      `}>
        {isSent ? (
          <ArrowUpIcon className="w-5 h-5 text-red-400" />
        ) : (
          <ArrowDownIcon className="w-5 h-5 text-emerald-400" />
        )}
      </div>
      
      <div className="flex-1 min-w-0">
        <p className="text-white font-medium">
          {isSent ? 'Sent' : 'Received'}
        </p>
        <p className="text-gray-400 text-sm truncate">
          {isSent ? `To: ${truncateAddress(transaction.to)}` : `From: ${truncateAddress(transaction.from)}`}
        </p>
      </div>
      
      <div className="text-right">
        <p className={`font-medium ${isSent ? 'text-red-400' : 'text-emerald-400'}`}>
          {isSent ? '-' : '+'}{amount.toFixed(2)} MNEE
        </p>
        <p className="text-gray-500 text-xs">
          ${amount.toFixed(2)}
        </p>
      </div>
    </a>
  )
}

export function RecentTransactions({ className = '' }: { className?: string }) {
  return <TransactionHistory className={className} limit={5} />
}

function truncateAddress(address: string): string {
  return `${address.slice(0, 6)}...${address.slice(-4)}`
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18" />
    </svg>
  )
}

function ArrowDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
    </svg>
  )
}

export default TransactionHistory
