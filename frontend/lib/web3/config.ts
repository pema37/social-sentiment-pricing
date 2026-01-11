/**
 * Web3 Configuration for MNEE Integration
 * 
 * This configures wagmi for connecting to Ethereum mainnet/Sepolia
 * and interacting with the MNEE stablecoin contract.
 */

import { http, createConfig } from 'wagmi'
import { mainnet, sepolia } from 'wagmi/chains'
import { injected, walletConnect } from 'wagmi/connectors'

// MNEE Contract Addresses by Chain ID
export const MNEE_CONTRACT_ADDRESSES: Record<number, `0x${string}`> = {
  // Ethereum Mainnet (Chain ID: 1)
  [mainnet.id]: '0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF',
  // Sepolia Testnet (Chain ID: 11155111)
  [sepolia.id]: '0x0e19B3fDa7336373DFeaCB6F945a72d39bFe2dB9',
}

// Default contract address (Sepolia for demo)
export const MNEE_CONTRACT_ADDRESS = MNEE_CONTRACT_ADDRESSES[sepolia.id]

// Get contract address for a specific chain
export function getMneeContractAddress(chainId: number | undefined): `0x${string}` {
  if (!chainId) return MNEE_CONTRACT_ADDRESS
  return MNEE_CONTRACT_ADDRESSES[chainId] || MNEE_CONTRACT_ADDRESS
}

// Get Etherscan URL for a specific chain
export function getEtherscanUrl(chainId: number | undefined): string {
  switch (chainId) {
    case sepolia.id: return 'https://sepolia.etherscan.io'
    case mainnet.id: return 'https://etherscan.io'
    default: return 'https://sepolia.etherscan.io'
  }
}

// Get network name for display
export function getNetworkName(chainId: number | undefined): string {
  switch (chainId) {
    case mainnet.id: return 'Ethereum Mainnet'
    case sepolia.id: return 'Sepolia Testnet'
    default: return 'Unknown Network'
  }
}

// Check if network is supported
export function isSupportedNetwork(chainId: number | undefined): boolean {
  if (!chainId) return false
  return chainId in MNEE_CONTRACT_ADDRESSES
}

// MNEE Token Details
export const MNEE_TOKEN = {
  symbol: 'MNEE',
  decimals: 18,
  name: 'MNEE Stablecoin',
} as const

// WalletConnect Project ID (get yours at https://cloud.walletconnect.com)
const WALLETCONNECT_PROJECT_ID = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || 'demo'

// Wagmi Configuration
export const wagmiConfig = createConfig({
  chains: [mainnet, sepolia],
  connectors: [
    injected(),
    walletConnect({ 
      projectId: WALLETCONNECT_PROJECT_ID,
      metadata: {
        name: 'ActualPrice',
        description: 'AI-Powered Dynamic Pricing with MNEE Payments',
        url: 'https://getactualprice.com',
        icons: ['https://getactualprice.com/logo.png'],
      },
    }),
  ],
  transports: {
    [mainnet.id]: http(),
    [sepolia.id]: http('https://eth-sepolia.g.alchemy.com/v2/i1syJSaaz92esG2J-4NG0'),
  },
})

// ERC-20 ABI for MNEE token interactions
export const ERC20_ABI = [
  {
    name: 'balanceOf',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'account', type: 'address' }],
    outputs: [{ name: 'balance', type: 'uint256' }],
  },
  {
    name: 'decimals',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'uint8' }],
  },
  {
    name: 'symbol',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'string' }],
  },
  {
    name: 'transfer',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'to', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
  {
    name: 'approve',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'spender', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
] as const


