/**
 * Web3 Module Exports
 */

// Configuration
export { 
  wagmiConfig, 
  MNEE_CONTRACT_ADDRESS, 
  MNEE_TOKEN, 
  ERC20_ABI 
} from './config'

// Provider
export { Web3Provider } from './Web3Provider'

// Hooks
export { useMNEE } from './useMNEE'
export type { UseMNEEReturn } from './useMNEE'

// Etherscan
export {
  fetchMNEETransactions,
  formatAddress,
  formatTimestamp,
  getEtherscanTxUrl
} from './etherscan'
export type { MNEETransaction } from './etherscan'
