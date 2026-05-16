'use client';

/**
 * MNEE Token Hook
 * 
 * Custom hook for interacting with the MNEE stablecoin:
 * - Get balance (network-aware)
 * - Transfer tokens
 * - Approve spending
 */

import { useAccount, useReadContract, useWriteContract, useWaitForTransactionReceipt, useChainId } from 'wagmi'
import { formatUnits, parseUnits, isAddress } from 'viem'
import { getMneeContractAddress, MNEE_TOKEN, ERC20_ABI } from './config'

export interface UseMNEEReturn {
  address: `0x${string}` | undefined
  isConnected: boolean
  balance: string
  balanceRaw: bigint
  isLoadingBalance: boolean
  refetchBalance: () => void
  transfer: (to: string, amount: string) => void
  isTransferring: boolean
  transferHash: `0x${string}` | undefined
  isTransferConfirmed: boolean
  transferError: Error | null
  approve: (spender: string, amount: string) => void
  isApproving: boolean
  approveHash: `0x${string}` | undefined
  isApproveConfirmed: boolean
  approveError: Error | null
  contractAddress: `0x${string}`
  chainId: number | undefined
}

export function useMNEE(): UseMNEEReturn {
  const { address, isConnected } = useAccount()
  const chainId = useChainId()
  
  // Get the contract address for the current network
  const contractAddress = getMneeContractAddress(chainId)
  
  // Read MNEE balance
  const { 
    data: balanceRaw, 
    isLoading: isLoadingBalance,
    refetch: refetchBalance,
  } = useReadContract({
    address: contractAddress,
    abi: ERC20_ABI,
    functionName: 'balanceOf',
    args: address ? [address] : undefined,
    query: {
      enabled: !!address,
    },
  })
  
  // Transfer MNEE
  const {
    writeContract: writeTransfer,
    data: transferHash,
    isPending: isTransferring,
    error: transferError,
  } = useWriteContract()
  
  const { isSuccess: isTransferConfirmed } = useWaitForTransactionReceipt({
    hash: transferHash,
  })
  
  // Approve MNEE spending
  const {
    writeContract: writeApprove,
    data: approveHash,
    isPending: isApproving,
    error: approveError,
  } = useWriteContract()
  
  const { isSuccess: isApproveConfirmed } = useWaitForTransactionReceipt({
    hash: approveHash,
  })
  
  // Transfer function
  const transfer = (to: string, amount: string) => {
    if (!isAddress(to)) {
      throw new Error('Invalid recipient address')
    }
    if (!amount || isNaN(Number(amount)) || Number(amount) <= 0) {
      throw new Error('Invalid transfer amount')
    }

    const amountInWei = parseUnits(amount, MNEE_TOKEN.decimals);

    writeTransfer({
      address: contractAddress,
      abi: ERC20_ABI,
      functionName: 'transfer',
      args: [to as `0x${string}`, amountInWei],
    });
  }

  // Approve function
  const approve = (spender: string, amount: string) => {
    if (!isAddress(spender)) {
      throw new Error('Invalid spender address')
    }
    if (!amount || isNaN(Number(amount)) || Number(amount) <= 0) {
      throw new Error('Invalid approve amount')
    }

    const amountInWei = parseUnits(amount, MNEE_TOKEN.decimals)
    writeApprove({
      address: contractAddress,
      abi: ERC20_ABI,
      functionName: 'approve',
      args: [spender as `0x${string}`, amountInWei],
    })
  }
  
  // Format balance for display
  const balance = balanceRaw 
    ? formatUnits(balanceRaw as bigint, MNEE_TOKEN.decimals)
    : '0'
  
  return {
    address,
    isConnected,
    balance,
    balanceRaw: (balanceRaw as bigint) || BigInt(0),
    isLoadingBalance,
    refetchBalance,
    transfer,
    isTransferring,
    transferHash,
    isTransferConfirmed,
    transferError: transferError as Error | null,
    approve,
    isApproving,
    approveHash,
    isApproveConfirmed,
    approveError: approveError as Error | null,
    contractAddress,
    chainId,
  }
}

export default useMNEE
