/**
 * Pay with MNEE Component
 * 
 * Payment button that handles MNEE stablecoin transfers.
 * Supports single payments and split payments.
**/

'use client'

import { useState, useCallback, useEffect } from 'react'
import { useAccount } from 'wagmi'
import { useMNEE } from '@/lib/web3'

interface PaymentRecipient {
  address: string
  percentage: number
  label: string
}

interface PayWithMNEEProps {
  amount: string | number
  recipients: string | PaymentRecipient[]
  onSuccess?: (txHash: string) => void
  onError?: (error: Error) => void
  orderId?: string
  buttonText?: string
  disabled?: boolean
  className?: string
}

export function PayWithMNEE({
  amount,
  recipients,
  onSuccess,
  onError,
  orderId,
  buttonText,
  disabled = false,
  className = '',
}: PayWithMNEEProps) {
  const { isConnected } = useAccount()
  const { 
    balance, 
    transfer, 
    isTransferring, 
    transferHash, 
    isTransferConfirmed,
    transferError,
  } = useMNEE()
  
  const [showConfirm, setShowConfirm] = useState(false)
  const [callbackFired, setCallbackFired] = useState(false)
  
  const amountStr = typeof amount === 'number' ? amount.toString() : amount
  const amountNum = parseFloat(amountStr)
  const hasEnoughBalance = parseFloat(balance) >= amountNum
  
  // Determine payment state
  const getPaymentState = useCallback(() => {
    if (transferError) return 'error'
    if (isTransferConfirmed && transferHash) return 'success'
    if (isTransferring) return 'processing'
    return 'idle'
  }, [transferError, isTransferConfirmed, transferHash, isTransferring])
  
  const paymentStep = getPaymentState()
  
  // Fire callbacks only once via useEffect (not in render body)
  useEffect(() => {
    if (paymentStep === 'success' && transferHash && onSuccess && !callbackFired) {
      setCallbackFired(true)
      onSuccess(transferHash)
    }
    if (paymentStep === 'error' && transferError && onError && !callbackFired) {
      setCallbackFired(true)
      onError(transferError)
    }
  }, [paymentStep, transferHash, transferError, onSuccess, onError, callbackFired])
  
  const handlePay = () => {
    if (!isConnected || !hasEnoughBalance) return
    
    if (typeof recipients === 'string') {
      transfer(recipients, amountStr)
    } else {
      const primaryRecipient = recipients.find(r => r.label === 'Merchant') || recipients[0]
      transfer(primaryRecipient.address, amountStr)
    }
    
    setShowConfirm(false)
  }
  
  if (!isConnected) {
    return (
      <button
        disabled
        className={`w-full py-3 px-6 bg-gray-700 text-gray-400 rounded-lg cursor-not-allowed ${className}`}
      >
        Connect Wallet to Pay
      </button>
    )
  }
  
  if (paymentStep === 'success') {
    return (
      <div className={`w-full py-3 px-6 bg-emerald-600 text-white rounded-lg text-center ${className}`}>
        <div className="flex items-center justify-center gap-2">
          <CheckIcon className="w-5 h-5" />
          <span>Payment Successful!</span>
        </div>
        {transferHash && (
          <a 
            href={`https://etherscan.io/tx/${transferHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-emerald-200 hover:text-white underline mt-1 block"
          >
            View on Etherscan
          </a>
        )}
      </div>
    )
  }
  
  if (paymentStep === 'error') {
    return (
      <div className={`w-full ${className}`}>
        <div className="py-3 px-6 bg-red-600/20 border border-red-600 text-red-400 rounded-lg text-center mb-2">
          Payment failed. Please try again.
        </div>
        <button
          onClick={() => window.location.reload()}
          className="w-full py-3 px-6 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
        >
          Try Again
        </button>
      </div>
    )
  }
  
  if (showConfirm) {
    return (
      <div className={`w-full space-y-4 ${className}`}>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h4 className="text-white font-medium mb-3">Confirm Payment</h4>
          
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Amount:</span>
              <span className="text-white font-medium">{amountNum.toFixed(2)} MNEE</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">USD Value:</span>
              <span className="text-white">${amountNum.toFixed(2)}</span>
            </div>
            {orderId && (
              <div className="flex justify-between">
                <span className="text-gray-400">Order ID:</span>
                <span className="text-white font-mono text-xs">{orderId}</span>
              </div>
            )}
          </div>
          
          {Array.isArray(recipients) && (
            <div className="mt-4 pt-4 border-t border-gray-700">
              <p className="text-gray-400 text-xs mb-2">Payment Split:</p>
              {recipients.map((r, i) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-gray-400">{r.label} ({r.percentage}%):</span>
                  <span className="text-white">
                    {(amountNum * r.percentage / 100).toFixed(2)} MNEE
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        
        <div className="flex gap-3">
          <button
            onClick={() => setShowConfirm(false)}
            className="flex-1 py-3 px-6 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handlePay}
            disabled={isTransferring}
            className="flex-1 py-3 px-6 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isTransferring ? (
              <span className="flex items-center justify-center gap-2">
                <LoadingSpinner className="w-4 h-4" />
                Processing...
              </span>
            ) : (
              'Confirm Payment'
            )}
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <button
      onClick={() => setShowConfirm(true)}
      disabled={disabled || !hasEnoughBalance || isTransferring}
      className={`
        w-full py-3 px-6 rounded-lg font-medium transition-all
        ${hasEnoughBalance 
          ? 'bg-emerald-600 hover:bg-emerald-700 text-white' 
          : 'bg-gray-700 text-gray-400 cursor-not-allowed'
        }
        disabled:opacity-50 disabled:cursor-not-allowed
        ${className}
      `}
    >
      <div className="flex items-center justify-center gap-2">
        <MNEEIcon className="w-5 h-5" />
        <span>
          {buttonText || `Pay ${amountNum.toFixed(2)} MNEE`}
        </span>
      </div>
      {!hasEnoughBalance && (
        <p className="text-xs text-red-400 mt-1">
          Insufficient balance (have {parseFloat(balance).toFixed(2)} MNEE)
        </p>
      )}
    </button>
  )
}

function MNEEIcon({ className }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center bg-emerald-500 rounded-full ${className}`}>
      <span className="text-white font-bold text-[10px]">M</span>
    </div>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  )
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

export default PayWithMNEE
