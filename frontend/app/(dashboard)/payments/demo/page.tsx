/**
 * MNEE Payments Demo Page
 * 
 * Test page for wallet connection and MNEE payments.
 * Access at: /payments/demo
**/
'use client'

import { useState, useEffect } from 'react'  
import { useAccount } from 'wagmi'
import { 
  ConnectWallet, 
  MNEEBalanceCard,
  PayWithMNEE,
  TransactionHistory 
} from '@/components/features/payments'

export default function PaymentsDemoPage() {
  const { isConnected, address } = useAccount()
  const [testAmount, setTestAmount] = useState('10.00')
  
  // ADD: Manual wallet state for Safari users
  const [manualAddress, setManualAddress] = useState<string | null>(null)
  
  // ADD: Load manual address from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('mnee_manual_wallet')
    if (saved) setManualAddress(saved)
  }, [])
  
  // ADD: Effective connection state (wagmi OR manual)
  const effectiveAddress = isConnected ? address : manualAddress
  const effectiveConnected = isConnected || !!manualAddress
  const isManualOnly = !isConnected && !!manualAddress
  
  const splitRecipients = [
    { address: '0x1234567890123456789012345678901234567890', percentage: 80, label: 'Merchant' },
    { address: '0x2345678901234567890123456789012345678901', percentage: 15, label: 'Affiliate' },
    { address: '0x3456789012345678901234567890123456789012', percentage: 5, label: 'Platform' },
  ]
  
  return (
    <div className="min-h-screen bg-gray-900 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-white mb-2">
            ActualPrice + MNEE Payments
          </h1>
          <p className="text-gray-400">
            Test the MNEE stablecoin payment integration
          </p>
        </div>
        
        {/* Connect Wallet Section */}
        <div className="bg-gray-800 rounded-xl p-6 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white mb-1">
                Wallet Connection
              </h2>
              <p className="text-gray-400 text-sm">
                {/* CHANGED: Use effectiveConnected and effectiveAddress */}
                {effectiveConnected 
                  ? `Connected: ${effectiveAddress?.slice(0, 6)}...${effectiveAddress?.slice(-4)}${isManualOnly ? ' (view only)' : ''}` 
                  : 'Connect your wallet to get started'
                }
              </p>
            </div>
            {/* CHANGED: Add callbacks for manual connection */}
            <ConnectWallet 
              onManualConnect={(addr) => setManualAddress(addr)}
              onManualDisconnect={() => setManualAddress(null)}
            />
          </div>
        </div>
        
        {/* Main Content Grid */}
        <div className="grid md:grid-cols-2 gap-8">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Balance Card */}
            <MNEEBalanceCard />
            
            {/* Payment Test */}
            <div className="bg-gray-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-white mb-4">
                Test Payment
              </h3>
              
              <div className="mb-4">
                <label className="block text-gray-400 text-sm mb-2">
                  Amount (MNEE)
                </label>
                <input
                  type="number"
                  value={testAmount}
                  onChange={(e) => setTestAmount(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-emerald-500"
                  placeholder="10.00"
                  step="0.01"
                  min="0"
                />
                <p className="text-gray-500 text-xs mt-1">
                  1 MNEE = $1 USD
                </p>
              </div>
              
              <PayWithMNEE
                amount={testAmount}
                recipients="0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
                onSuccess={(hash) => {
                  console.log('Payment successful:', hash)
                  alert(`Payment successful! TX: ${hash}`)
                }}
                onError={(error) => {
                  console.error('Payment failed:', error)
                }}
                orderId="DEMO-001"
              />
            </div>
            
            {/* Split Payment Demo */}
            <div className="bg-gray-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-white mb-2">
                Split Payment Demo
              </h3>
              <p className="text-gray-400 text-sm mb-4">
                Automatic revenue splitting via smart contract
              </p>
              
              <div className="space-y-2 mb-4">
                {splitRecipients.map((r, i) => (
                  <div 
                    key={i}
                    className="flex items-center justify-between p-2 bg-gray-700/50 rounded"
                  >
                    <span className="text-gray-300">{r.label}</span>
                    <span className="text-emerald-400 font-medium">
                      {r.percentage}% → ${(parseFloat(testAmount) * r.percentage / 100).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
              
              <PayWithMNEE
                amount={testAmount}
                recipients={splitRecipients}
                buttonText="Pay with Split"
                onSuccess={(hash) => console.log('Split payment:', hash)}
              />
            </div>
          </div>
          
          {/* Right Column */}
          <div>
            <TransactionHistory />
          </div>
        </div>
        
        {/* Info Section */}
        <div className="mt-12 bg-emerald-900/20 border border-emerald-800 rounded-xl p-6">
          <h3 className="text-emerald-400 font-semibold mb-2">
            💡 About MNEE Stablecoin
          </h3>
          <ul className="text-gray-300 text-sm space-y-1">
            <li>• MNEE is a USD-backed stablecoin on Ethereum</li>
            <li>• 1 MNEE = $1 USD, always stable</li>
            <li>• Near-instant settlement (2 seconds vs 2-3 days)</li>
            <li>• Near-zero transaction fees</li>
            <li>• Smart contracts enable automatic payment splitting</li>
          </ul>
          <p className="text-gray-400 text-xs mt-4">
            Contract: 0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF
          </p>
        </div>
      </div>
    </div>
  )
}
