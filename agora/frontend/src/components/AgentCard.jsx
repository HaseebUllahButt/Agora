import React from 'react'

const STATUS_CONFIG = {
  IDLE:    { label: 'Idle',    cls: 'status-idle',    icon: '○' },
  WORKING: { label: 'Working', cls: 'status-working', icon: '◉' },
  PAID:    { label: 'Paid',    cls: 'status-paid',    icon: '✓' },
  FRAUD:   { label: 'Fraud',   cls: 'status-fraud',   icon: '✗' },
  TIMEOUT: { label: 'Timeout', cls: 'status-timeout', icon: '!' },
}

export default function AgentCard({ agent, state }) {
  const cfg = STATUS_CONFIG[state.status] || STATUS_CONFIG.IDLE
  const cardCls = `agent-card ${state.status.toLowerCase()}`

  return (
    <div className={cardCls}>
      <div className="agent-icon">{agent.icon}</div>
      <div className="agent-name">{agent.name}</div>

      <div className={`agent-status ${cfg.cls}`}>
        <span>{cfg.icon}</span>
        <span>{cfg.label}</span>
      </div>

      {state.amount && (
        <div className="agent-amount">${state.amount} USDC</div>
      )}

      {state.txHash && (
        <a
          href={`https://testnet.arcscan.app/tx/${state.txHash}`}
          target="_blank"
          rel="noreferrer"
          className="agent-tx"
        >
          {state.txHash.slice(0, 10)}…{state.txHash.slice(-4)}
        </a>
      )}

      {state.reason && (
        <div style={{ fontSize: 9, color: 'var(--red)', marginTop: 4, lineHeight: 1.3 }}>
          {state.reason.slice(0, 55)}
        </div>
      )}

      <div className="agent-price">{agent.price}/call</div>
    </div>
  )
}
