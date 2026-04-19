import React from 'react'

// ETH mainnet average ERC-20 transfer gas cost (USD)
const ETH_GAS_PER_TX = 2.95

export default function MarginCalculator({ txCount, totalSpent }) {
  const arcCost  = totalSpent
  const ethCost  = txCount * ETH_GAS_PER_TX
  const saved    = Math.max(0, ethCost - arcCost)
  const pctSaved = ethCost > 0 ? ((saved / ethCost) * 100).toFixed(2) : '0.00'
  const multiple = ethCost > 0 && arcCost > 0
    ? Math.round(ethCost / arcCost).toLocaleString()
    : '—'

  return (
    <div className="margin-calc">
      <h3>
        💸 Cost Comparison — Arc vs Ethereum
      </h3>

      <div className="margin-row">
        <span className="margin-label">Arc Nanopayments cost</span>
        <span className="margin-value arc">${arcCost.toFixed(4)} USDC</span>
      </div>

      <div className="margin-row">
        <span className="margin-label">
          Same {txCount} txns on Ethereum&nbsp;
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>({txCount} × ${ETH_GAS_PER_TX} gas)</span>
        </span>
        <span className="margin-value eth">${ethCost.toFixed(2)} in gas</span>
      </div>

      <div className="margin-row">
        <span className="margin-label">You saved</span>
        <span className="margin-value saved">${saved.toFixed(2)}</span>
      </div>

      <div className="margin-row">
        <span className="margin-label">Cost reduction</span>
        <span className="margin-value pct">{pctSaved}%</span>
      </div>

      <div className="margin-hero">
        <div className="margin-hero-num">
          {txCount === 0 ? '—' : `${multiple}×`}
        </div>
        <div className="margin-hero-label">
          cheaper on Arc · {txCount} Nanopayments settled on-chain · powered by Circle
        </div>
      </div>
    </div>
  )
}
