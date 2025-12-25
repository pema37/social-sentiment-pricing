/**
 * Etherscan API Integration for MNEE Transaction History
 * Fetches real token transfer events from blockchain
**/

// MNEE Token Contract Address
const MNEE_CONTRACT = '0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF'

// Etherscan API (free tier - 5 calls/sec)
const ETHERSCAN_API = 'https://api.etherscan.io/api'

export interface MNEETransaction {
  hash: string
  from: string
  to: string
  value: string
  valueFormatted: string
  timestamp: number
  blockNumber: string
  type: 'sent' | 'received'
  status: 'confirmed'
}

export async function fetchMNEETransactions(
  walletAddress: string,
  apiKey?: string
): Promise<MNEETransaction[]> {
  if (!walletAddress) return []

  try {
    const params = new URLSearchParams({
      module: 'account',
      action: 'tokentx',
      contractaddress: MNEE_CONTRACT,
      address: walletAddress,
      page: '1',
      offset: '50',
      sort: 'desc',
    })

    // Add API key if provided (higher rate limits)
    if (apiKey) {
      params.append('apikey', apiKey)
    }

    const response = await fetch(`${ETHERSCAN_API}?${params}`)
    const data = await response.json()

    if (data.status !== '1' || !Array.isArray(data.result)) {
      // No transactions found or error
      return []
    }

    // Transform Etherscan response to our format
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const transactions: MNEETransaction[] = data.result.map((tx: any) => {
      const isSent = tx.from.toLowerCase() === walletAddress.toLowerCase()
      // MNEE has 4 decimals
      const valueFormatted = (parseInt(tx.value) / 10000).toFixed(2)

      return {
        hash: tx.hash,
        from: tx.from,
        to: tx.to,
        value: tx.value,
        valueFormatted,
        timestamp: parseInt(tx.timeStamp) * 1000, // Convert to milliseconds
        blockNumber: tx.blockNumber,
        type: isSent ? 'sent' : 'received',
        status: 'confirmed',
      }
    })

    return transactions
  } catch (error) {
    console.error('Error fetching MNEE transactions:', error)
    return []
  }
}

export function formatAddress(address: string): string {
  if (!address) return ''
  return `${address.slice(0, 6)}...${address.slice(-4)}`
}

export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString()
}

export function getEtherscanTxUrl(hash: string): string {
  return `https://etherscan.io/tx/${hash}`
}
