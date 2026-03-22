/**
 * Web3 Module Exports
 * 
 * Central export point for all MNEE/Web3 functionality
**/

// Configuration
export {
  wagmiConfig,
  MNEE_CONTRACT_ADDRESS,
  MNEE_TOKEN,
  ERC20_ABI,
  getEtherscanUrl,
} from './config'

// Provider
export { Web3Provider } from './Web3Provider'

// Hooks
export { useMNEE } from './useMNEE'
export type { UseMNEEReturn } from './useMNEE'
