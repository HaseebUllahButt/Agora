export default function TransactionFeed({ transactions }) {
  if (!transactions.length) {
    return (
      <div className="empty-state">
        <div className="empty-icon">⚡</div>
        <div>Nanopayments appear here in real time</div>
        <div style={{ fontSize: 11, marginTop: 4, color: 'var(--text-dim)' }}>
          Each payment settles on Arc testnet
        </div>
      </div>
    )
  }

  return (
    <div className="tx-list">
      {transactions.map((tx, i) => (
        <div key={i} className="tx-item">
          <span className="tx-amount">+${tx.amount}</span>
          <span className="tx-agent">{tx.agent.replace(' Agent', '')}</span>
          <a
            href={tx.explorerUrl || `https://testnet.arcscan.app/tx/${tx.txHash}`}
            target="_blank"
            rel="noreferrer"
            className="tx-hash"
          >
            {tx.txHash?.slice(0, 8)}…
          </a>
          <span className="tx-time">{tx.ts}</span>
        </div>
      ))}
    </div>
  )
}
