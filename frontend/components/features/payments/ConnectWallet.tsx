/**
 * Connect Wallet Button Component
 * 
 * Uses RainbowKit's ConnectButton with custom styling
 * to match the ActualPrice design system.
* */
'use client'

import { useState, useEffect } from 'react'
import { useAccount, useConnect, useDisconnect } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { Wallet, Edit3, CheckCircle, AlertCircle, Copy, X } from 'lucide-react'

// Validate Ethereum address
function isValidEthAddress(address: string): boolean {
  return /^0x[a-fA-F0-9]{40}$/.test(address)
}

interface ConnectWalletProps {
  onManualConnect?: (address: string) => void
  onManualDisconnect?: () => void
}

export function ConnectWallet({ onManualConnect, onManualDisconnect }: ConnectWalletProps) {
  // Wagmi hooks for extension-based connection
  const { address, isConnected } = useAccount()
  const { connect, isPending } = useConnect()
  const { disconnect } = useDisconnect()
  
  // Manual address state (for Safari users)
  const [manualAddress, setManualAddress] = useState<string | null>(null)
  const [inputAddress, setInputAddress] = useState('')
  const [addressError, setAddressError] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'extension' | 'manual'>('extension')

  // Load manual address from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('mnee_manual_wallet')
    if (saved && isValidEthAddress(saved)) {
      setManualAddress(saved)
      onManualConnect?.(saved)
    }
  }, [])

  // Determine effective connection state
  const effectiveAddress = isConnected ? address : manualAddress
  const effectiveIsConnected = isConnected || !!manualAddress

  const handleExtensionConnect = () => {
    setAddressError('')
    connect(
      { connector: injected() },
      {
        onError: (error) => {
          console.error('Wallet connection error:', error)
          setAddressError('No wallet found. Use manual entry or install MetaMask.')
          setActiveTab('manual')
        }
      }
    )
  }

  const handleManualSubmit = () => {
    setAddressError('')
    
    if (!inputAddress.trim()) {
      setAddressError('Please enter a wallet address')
      return
    }

    if (!isValidEthAddress(inputAddress.trim())) {
      setAddressError('Invalid Ethereum address format (must start with 0x)')
      return
    }

    const addr = inputAddress.trim()
    setManualAddress(addr)
    localStorage.setItem('mnee_manual_wallet', addr)
    onManualConnect?.(addr)
    setIsModalOpen(false)
    setInputAddress('')
  }

  const handleDisconnect = () => {
    if (isConnected) {
      disconnect()
    }
    if (manualAddress) {
      setManualAddress(null)
      localStorage.removeItem('mnee_manual_wallet')
      onManualDisconnect?.()
    }
    setIsModalOpen(false)
  }

  const truncateAddress = (addr: string) => {
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  const copyAddress = async () => {
    if (effectiveAddress) {
      await navigator.clipboard.writeText(effectiveAddress)
    }
  }

  // Connected state - show address with disconnect option
  if (effectiveIsConnected && effectiveAddress) {
    return (
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2 px-3 py-2 bg-emerald-900/30 border border-emerald-700 rounded-lg">
          <CheckCircle className="h-4 w-4 text-emerald-400" />
          <span className="text-sm font-mono text-emerald-300">
            {truncateAddress(effectiveAddress)}
          </span>
          {!isConnected && manualAddress && (
            <span className="text-xs text-gray-500">(manual)</span>
          )}
          <button
            onClick={copyAddress}
            className="p-1 text-gray-400 hover:text-white transition-colors"
            title="Copy address"
          >
            <Copy className="h-3 w-3" />
          </button>
        </div>
        <button
          onClick={handleDisconnect}
          className="p-2 text-gray-400 hover:text-red-400 transition-colors"
          title="Disconnect"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  // Disconnected state - show connect button
  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors"
      >
        <Wallet className="h-4 w-4" />
        Connect Wallet
      </button>

      {/* Connection Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setIsModalOpen(false)}
          />
          
          {/* Modal */}
          <div className="relative z-10 w-full max-w-md mx-4 bg-gray-800 border border-gray-700 rounded-xl shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-white">Get a Wallet</h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 text-gray-400 hover:text-white transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-700">
              <button
                onClick={() => setActiveTab('extension')}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'extension'
                    ? 'text-emerald-400 border-b-2 border-emerald-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Wallet className="h-4 w-4" />
                Browser Extension
              </button>
              <button
                onClick={() => setActiveTab('manual')}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'manual'
                    ? 'text-emerald-400 border-b-2 border-emerald-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Edit3 className="h-4 w-4" />
                Manual Entry
              </button>
            </div>

            {/* Content */}
            <div className="p-6">
              {activeTab === 'extension' ? (
                <div className="space-y-4">
                  <p className="text-sm text-gray-400">
                    Connect using MetaMask or another browser wallet extension.
                    Works best in Chrome, Brave, or Firefox.
                  </p>
                  
                  <button
                    onClick={handleExtensionConnect}
                    disabled={isPending}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
                  >
                    {isPending ? 'Connecting...' : 'Connect Wallet'}
                  </button>

                  {addressError && (
                    <p className="text-sm text-red-400 flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      {addressError}
                    </p>
                  )}

                  <p className="text-xs text-gray-500 text-center">
                    Don't have a wallet?{' '}
                    <a 
                      href="https://metamask.io/download/" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:underline"
                    >
                      Get MetaMask
                    </a>
                  </p>

                  <div className="pt-4 border-t border-gray-700">
                    <p className="text-xs text-gray-500">
                      <strong>Using Safari?</strong> Browser extensions aren't supported.
                      Use the "Manual Entry" tab to paste your address.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-sm text-gray-400">
                    Paste your Ethereum wallet address. This works on all browsers including Safari.
                  </p>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-300">
                      Wallet Address
                    </label>
                    <input
                      type="text"
                      value={inputAddress}
                      onChange={(e) => {
                        setInputAddress(e.target.value)
                        setAddressError('')
                      }}
                      placeholder="0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
                      className={`w-full px-4 py-2 bg-gray-700 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 ${
                        addressError ? 'border-red-500' : 'border-gray-600'
                      }`}
                    />
                    {addressError && (
                      <p className="text-sm text-red-400 flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 shrink-0" />
                        {addressError}
                      </p>
                    )}
                  </div>

                  <button
                    onClick={handleManualSubmit}
                    disabled={!inputAddress.trim()}
                    className="w-full px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
                  >
                    Save Wallet Address
                  </button>

                  <div className="pt-4 border-t border-gray-700">
                    <p className="text-xs text-gray-500 font-medium mb-2">
                      Where to find your address:
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                      <li>• <strong>MetaMask:</strong> Click account name to copy</li>
                      <li>• <strong>Coinbase Wallet:</strong> Settings → Wallet address</li>
                      <li>• <strong>Trust Wallet:</strong> Tap Receive → Copy</li>
                    </ul>
                  </div>

                  <div className="p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg">
                    <p className="text-xs text-yellow-300">
                      <strong>Note:</strong> Manual entry allows viewing balances only. 
                      To send transactions, use a browser with wallet extension support.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default ConnectWallet
