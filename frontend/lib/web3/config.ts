/**
 * Web3 Configuration for MNEE Integration
 * 
 * This configures wagmi for connecting to Ethereum mainnet
 * and interacting with the MNEE stablecoin contract.
* */

import { http, createConfig } from 'wagmi'
import { mainnet, sepolia } from 'wagmi/chains'
import { injected, walletConnect } from 'wagmi/connectors'

// MNEE Stablecoin Contract Address (Ethereum Mainnet)
export const MNEE_CONTRACT_ADDRESS = '0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF' as const

// MNEE Token Details
export const MNEE_TOKEN = {
  address: MNEE_CONTRACT_ADDRESS,
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
    [sepolia.id]: http(),
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
