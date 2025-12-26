/**
 * MNEE Token Hook
 * 
 * Custom hook for interacting with the MNEE stablecoin:
 * - Get balance
 * - Transfer tokens
 * - Approve spending
* */

'use client'

import { useAccount, useReadContract, useWriteContract, useWaitForTransactionReceipt } from 'wagmi'
import { formatUnits, parseUnits } from 'viem'
import { MNEE_CONTRACT_ADDRESS, MNEE_TOKEN, ERC20_ABI } from './config'

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
}

export function useMNEE(): UseMNEEReturn {
  const { address, isConnected } = useAccount()
  
  // Read MNEE balance
  const { 
    data: balanceRaw, 
    isLoading: isLoadingBalance,
    refetch: refetchBalance,
  } = useReadContract({
    address: MNEE_CONTRACT_ADDRESS,
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
    const amountInWei = parseUnits(amount, MNEE_TOKEN.decimals)
    writeTransfer({
      address: MNEE_CONTRACT_ADDRESS,
      abi: ERC20_ABI,
      functionName: 'transfer',
      args: [to as `0x${string}`, amountInWei],
    })
  }
  
  // Approve function
  const approve = (spender: string, amount: string) => {
    const amountInWei = parseUnits(amount, MNEE_TOKEN.decimals)
    writeApprove({
      address: MNEE_CONTRACT_ADDRESS,
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
  }
}

export default useMNEE
