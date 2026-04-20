import { useEffect, useRef } from 'react'
import './TransactionFeed.css'

export default function TransactionFeed({ transactions }) {
  const feedRef = useRef(null)

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0
    }
  }, [transactions])

  const getCategoryColor = (category) => {
    const colors = {
      compute: '#00f0ff',
      data: '#00ff41',
      capability: '#ff6b35'
    }
    return colors[category] || '#00f0ff'
  }

  return (
    <div className="transaction-feed">
      <div className="feed-header">
        <h3>LIVE TRANSACTIONS</h3>
        <span className="feed-count">{transactions.length} recent</span>
      </div>

      <div className="feed-scroll" ref={feedRef}>
        {transactions.length === 0 ? (
          <div className="feed-empty">
            <p>Waiting for transactions...</p>
          </div>
        ) : (
          <div className="feed-items">
            {transactions.map((tx, idx) => (
              <div key={tx.id} className="feed-item" style={{ animationDelay: `${idx * 30}ms` }}>
                <div className="tx-header">
                  <div className="tx-provider">
                    <span 
                      className="cat-dot" 
                      style={{ backgroundColor: getCategoryColor(tx.category) }}
                    ></span>
                    <span className="tx-name">{tx.provider}</span>
                  </div>
                  <span className="tx-amount">${tx.amount.toFixed(6)}</span>
                </div>
                <div className="tx-footer">
                  <span className="tx-hash">
                    {tx.txHash}
                  </span>
                  <span className="tx-status status-confirmed">✓ confirmed</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="feed-stats">
        <div className="feed-stat">
          <span className="stat-label">Total Txns</span>
          <span className="stat-val">{transactions.length}</span>
        </div>
        <div className="feed-stat">
          <span className="stat-label">Total Volume</span>
          <span className="stat-val">
            ${(transactions.reduce((sum, t) => sum + t.amount, 0)).toFixed(4)}
          </span>
        </div>
        <div className="feed-stat">
          <span className="stat-label">Avg Tx</span>
          <span className="stat-val">
            ${(transactions.length > 0 ? transactions.reduce((sum, t) => sum + t.amount, 0) / transactions.length : 0).toFixed(6)}
          </span>
        </div>
      </div>
    </div>
  )
}
