import ReactMarkdown from 'react-markdown'

export default function ReportDisplay({ report }) {
  if (!report) return null

  const markdown = report?.report?.report_markdown || ''
  const recs     = report?.recommendations?.recommendations || ''
  const budget   = report?.budget_summary || {}
  const txCount  = report?.transaction_count || 0

  return (
    <div className="report-wrap">
      <div className="panel">
        <div className="panel-header">
          <span>📊</span>
          <span className="panel-title">Research Report</span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
              {txCount} Nanopayments
            </span>
            <span style={{ fontSize: 12, color: 'var(--yellow)', fontFamily: 'var(--font-mono)' }}>
              ${budget.total_spent?.toFixed(4)} spent
            </span>
            <a
              href="https://testnet.arcscan.app"
              target="_blank"
              rel="noreferrer"
              className="explorer-link"
            >
              View on Arc →
            </a>
          </div>
        </div>
        <div className="panel-body">
          {markdown ? (
            <div className="report-content">
              <ReactMarkdown>{markdown}</ReactMarkdown>
            </div>
          ) : recs ? (
            <div className="report-content">
              <ReactMarkdown>{recs}</ReactMarkdown>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📄</div>
              <div>Report is being generated…</div>
            </div>
          )}

          {/* Budget summary */}
          {budget.total_spent > 0 && (
            <div style={{
              marginTop: 20,
              padding: '12px 16px',
              background: 'rgba(99,130,255,0.05)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--text-secondary)',
              display: 'flex',
              gap: 24,
              flexWrap: 'wrap'
            }}>
              <span>Budget: <b style={{ color: 'var(--text-primary)' }}>${budget.total_budget?.toFixed(4)}</b></span>
              <span>Spent: <b style={{ color: 'var(--yellow)' }}>${budget.total_spent?.toFixed(4)}</b></span>
              <span>Remaining: <b style={{ color: 'var(--green)' }}>${budget.remaining?.toFixed(4)}</b></span>
              <span>Transactions: <b style={{ color: 'var(--accent)' }}>{txCount}</b></span>
              <span>Utilisation: <b style={{ color: 'var(--accent-2)' }}>{budget.utilization_pct}%</b></span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
