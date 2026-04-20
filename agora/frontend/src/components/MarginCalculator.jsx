import React from 'react'

// ETH mainnet average ERC-20 transfer gas cost (USD)
const ETH_GAS_PER_TX = 2.95

export default function MarginCalculator({ txCount, totalSpent }) {
  const arcCost  = totalSpent
  const ethCost  = txCount * ETH_GAS_PER_TX
  const saved    = Math.max(0, ethCost - arcCost)
  const pctSaved = ethCost > 0 ? ((saved / ethCost) * 100).toFixed(2) : '0.00'
  const margin = ethCost > 0 ? (100 - ((arcCost / ethCost) * 100)).toFixed(2) : '0.00'

  return (
    <div className="margin-calc">
      <h3>
        MARGIN CALCULATOR
      </h3>

      <div className="margin-big-grid">
        <div className="margin-big margin-big-eth">
          <div className="margin-big-label">Ethereum Cost</div>
          <div className="margin-big-value">${ethCost.toFixed(2)}</div>
        </div>
        <div className="margin-big margin-big-arc">
          <div className="margin-big-label">Arc Cost</div>
          <div className="margin-big-value">${arcCost.toFixed(6)}</div>
        </div>
      </div>

      <div className="margin-row">
        <span className="margin-label">You saved</span>
        <span className="margin-value saved">${saved.toFixed(6)}</span>
      </div>

      <div className="margin-row">
        <span className="margin-label">Arc margin</span>
        <span className="margin-value pct">{margin}%</span>
      </div>

      <div className="margin-row">
        <span className="margin-label">Reduction</span>
        <span className="margin-value arc">{pctSaved}%</span>
      </div>

      <div className="margin-hero">
        <div className="margin-hero-num">{txCount} txns · live updated</div>
        <div className="margin-hero-label">
          Same workload on Ethereum: ${ethCost.toFixed(2)} vs Arc: ${arcCost.toFixed(6)}
        </div>
      </div>
    </div>
  )
}
