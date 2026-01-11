// Contract addresses for different networks
export const MNEE_CONTRACT_ADDRESSES: Record<number, string> = {
  // Ethereum Mainnet (Chain ID: 1)
  1: "0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF",
  // Sepolia Testnet (Chain ID: 11155111)
  11155111: "0x0e19B3fDa7336373DFeaCB6F945a72d39bFe2dB9",
};

// Default to mainnet if network not found
export const DEFAULT_CHAIN_ID = 1;

export function getMneeContractAddress(chainId: number | undefined): string {
  if (!chainId) return MNEE_CONTRACT_ADDRESSES[DEFAULT_CHAIN_ID];
  return MNEE_CONTRACT_ADDRESSES[chainId] || MNEE_CONTRACT_ADDRESSES[DEFAULT_CHAIN_ID];
}

export function isSupportedNetwork(chainId: number | undefined): boolean {
  if (!chainId) return false;
  return chainId in MNEE_CONTRACT_ADDRESSES;
}

export function getNetworkName(chainId: number | undefined): string {
  switch (chainId) {
    case 1: return "Ethereum Mainnet";
    case 11155111: return "Sepolia Testnet";
    default: return "Unknown Network";
  }
}
