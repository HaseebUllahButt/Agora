import React from 'react'
import ReactMarkdown from 'react-markdown'

export default function ReportDisplay({ report }) {
  if (!report) return null

  const markdown = report?.report?.report_markdown || ''
  const recs     = report?.recommendations?.recommendations || ''
  const consultancy = report?.consultancy_advice?.consultancy_advice || ''
  const budget   = report?.budget_summary || {}
  const txCount  = report?.transaction_count || 0
  const arcCost = Number(budget.total_spent || 0)
  const ethCost = txCount * 2.95
  const savings = Math.max(0, ethCost - arcCost)

  return (
    <div className="report-wrap">
      <div className="panel">
        <div className="panel-header">
          <span>✅</span>
          <span className="panel-title">Pipeline Complete</span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
              {txCount} txns
            </span>
            <span style={{ fontSize: 12, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
              ${arcCost.toFixed(6)} spent
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
          <div className="report-grid">
            <div>
              <div className="report-col-title">Final Report</div>
              <div className="report-content">
                <ReactMarkdown>{markdown || consultancy || '_No report available_'}</ReactMarkdown>
              </div>
            </div>

            <div>
              <div className="report-col-title">Strategic Recommendations</div>
              <div className="report-content">
                <ReactMarkdown>{recs || '_Recommendations unavailable_'}</ReactMarkdown>
              </div>
            </div>
          </div>

          <div className="receipt-wrap">
            <div className="receipt-title">Receipt</div>
            <div className="receipt-grid">
              <div className="receipt-row"><span>Total transactions</span><b>{txCount}</b></div>
              <div className="receipt-row"><span>Total spent</span><b>${arcCost.toFixed(6)}</b></div>
              <div className="receipt-row"><span>Cost on Ethereum</span><b className="num-red">${ethCost.toFixed(2)}</b></div>
              <div className="receipt-row"><span>Cost on Arc</span><b>${arcCost.toFixed(6)}</b></div>
              <div className="receipt-row"><span>Savings</span><b>${savings.toFixed(6)}</b></div>
              <div className="receipt-row"><span>Budget remaining</span><b>${Number(budget.remaining || 0).toFixed(6)}</b></div>
            </div>

            <div className="receipt-actions">
              <button type="button" className="submit-btn receipt-btn" onClick={() => window.location.reload()}>Run Another Task</button>
              <button type="button" className="submit-btn receipt-btn secondary" onClick={() => window.print()}>Export Report as PDF</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
