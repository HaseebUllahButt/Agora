import React, { useState, useEffect, useRef } from 'react'
import AgentCard from './components/AgentCard'
import TransactionFeed from './components/TransactionFeed'
import AuditLog from './components/AuditLog'
import TaskSubmit from './components/TaskSubmit'
import ReportDisplay from './components/ReportDisplay'
import MarginCalculator from './components/MarginCalculator'

const AGENTS = [
  { key: 'web_search', name: 'Web Search Agent',  icon: '🔍', port: 8001, price: '$0.0005' },
  { key: 'extractor',  name: 'Extractor Agent',   icon: '⚗️',  port: 8002, price: '$0.0005' },
  { key: 'summarizer', name: 'Summarizer Agent',  icon: '📝', port: 8003, price: '$0.001'  },
  { key: 'analyst',    name: 'Analyst Agent',     icon: '🧠', port: 8004, price: '$0.002'  },
  { key: 'formatter',  name: 'Formatter Agent',   icon: '✨', port: 8005, price: '$0.0005' },
]

const API_BASE = 'http://localhost:8000'
const WS_URL   = 'ws://localhost:8000/ws'

export default function App() {
  const [agentStates, setAgentStates]     = useState({})
  const [transactions, setTransactions]   = useState([])
  const [auditEntries, setAuditEntries]   = useState([])
  const [report, setReport]               = useState(null)
  const [txCount, setTxCount]             = useState(0)
  const [totalSpent, setTotalSpent]       = useState(0)
  const [alerts, setAlerts]               = useState([])
  const [running, setRunning]             = useState(false)
  const [wsConnected, setWsConnected]     = useState(false)
  const ws = useRef(null)
  const wsRetryDelay = useRef(2000)
  const wsRetryTimer = useRef(null)

  // ── WebSocket connection ───────────────────────────────────────────────────
  useEffect(() => {
    const connect = () => {
      try {
        ws.current = new WebSocket(WS_URL)

        ws.current.onopen = () => {
          setWsConnected(true)
          wsRetryDelay.current = 2000
          // Keep-alive ping every 30s
          const ping = setInterval(() => {
            if (ws.current?.readyState === 1) ws.current.send('ping')
          }, 30000)
          ws.current._ping = ping
        }

        ws.current.onclose = () => {
          setWsConnected(false)
          clearInterval(ws.current?._ping)
          clearTimeout(wsRetryTimer.current)
          wsRetryTimer.current = setTimeout(connect, wsRetryDelay.current)
          wsRetryDelay.current = Math.min(wsRetryDelay.current * 2, 15000)
        }

        ws.current.onerror = () => {
          ws.current?.close()
        }

        ws.current.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            handleWsEvent(msg)
          } catch (_) {}
        }
      } catch (_) {}
    }

    connect()
    return () => {
      clearTimeout(wsRetryTimer.current)
      clearInterval(ws.current?._ping)
      ws.current?.close()
    }
  }, [])

  const handleWsEvent = (msg) => {
    const now = new Date().toLocaleTimeString()

    switch (msg.event) {
      case 'pipeline_started':
        setAuditEntries(prev => [{
          ts: now,
          msg: `Pipeline started: ${msg.topic} | Budget: $${msg.budget} | ${msg.planned_loops} loops`,
          type: 'info'
        }, ...prev])
        break

      case 'loop_start':
        setAuditEntries(prev => [{
          ts: now,
          msg: `Loop ${msg.loop}: "${msg.query}"`,
          type: 'default'
        }, ...prev])
        break

      case 'payment_initiated':
        setAgentStates(prev => ({
          ...prev,
          [msg.agent]: { status: 'WORKING', amount: msg.amount }
        }))
        setAuditEntries(prev => [{
          ts: now,
          msg: `Paying ${msg.agent} $${msg.amount} USDC (Nanopayment)`,
          type: 'payment'
        }, ...prev])
        break

      case 'payment_confirmed':
        setAgentStates(prev => ({
          ...prev,
          [msg.agent]: { status: 'PAID', txHash: msg.tx_hash, amount: msg.amount }
        }))
        setTransactions(prev => [{
          agent: msg.agent,
          amount: msg.amount,
          txHash: msg.tx_hash,
          explorerUrl: msg.explorer_url,
          remaining: msg.remaining_budget,
          ts: now
        }, ...prev])
        setTxCount(prev => prev + 1)
        setTotalSpent(prev => +(prev + msg.amount).toFixed(6))
        setAuditEntries(prev => [{
          ts: now,
          msg: `✓ Confirmed: ${msg.tx_hash?.slice(0, 14)}... | Remaining: $${msg.remaining_budget?.toFixed(4)}`,
          type: 'payment'
        }, ...prev])
        break

      case 'fraud_detected':
        setAgentStates(prev => ({
          ...prev,
          [msg.agent]: { status: 'FRAUD', reason: msg.reason }
        }))
        setAlerts(prev => [{
          type: 'fraud',
          message: `🚨 FRAUD DETECTED: ${msg.agent}`,
          reason: msg.reason,
          id: Date.now()
        }, ...prev])
        setAuditEntries(prev => [{
          ts: now,
          msg: `FRAUD DETECTED — ${msg.agent}: ${msg.reason?.slice(0, 80)}`,
          type: 'fraud'
        }, ...prev])
        break

      case 'pipeline_complete':
        setRunning(false)
        setAlerts(prev => [{
          type: 'success',
          message: `✅ Pipeline complete — ${msg.transaction_count} Nanopayments | $${msg.total_spent?.toFixed(4)} spent`,
          id: Date.now()
        }, ...prev])
        setAuditEntries(prev => [{
          ts: now,
          msg: `Pipeline complete: ${msg.transaction_count} txns | $${msg.total_spent?.toFixed(4)} spent | $${msg.remaining?.toFixed(4)} remaining`,
          type: 'info'
        }, ...prev])
        break
    }
  }

  // ── Task submission ────────────────────────────────────────────────────────
  const handleTaskSubmit = async (taskData) => {
    // Reset all state
    setTransactions([])
    setAgentStates({})
    setAlerts([])
    setReport(null)
    setTxCount(0)
    setTotalSpent(0)
    setAuditEntries([])
    setRunning(true)

    // Reset agent states to IDLE
    const idle = {}
    AGENTS.forEach(a => { idle[a.name] = { status: 'IDLE' } })
    setAgentStates(idle)

    try {
      const res = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(taskData)
      })
      const result = await res.json()
      setReport(result)

      // Add any audit entries from the final result
      if (result.audit_log) {
        const entries = result.audit_log.map(e => ({
          ts: e.timestamp?.slice(11, 19) || '',
          msg: e.message,
          type: e.message?.toUpperCase().includes('FRAUD') ? 'fraud'
              : e.message?.includes('confirmed') || e.message?.includes('Paying') ? 'payment'
              : 'default'
        }))
        setAuditEntries(entries)
      }
    } catch (err) {
      setAlerts(prev => [{
        type: 'fraud',
        message: `API Error: ${err.message}`,
        id: Date.now()
      }, ...prev])
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="app">

      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="header">
        <div className="header-left">
          <h1>Agora</h1>
          <p className="tagline">Competitive Intelligence at $0.05 · Autonomous Research Protocol on Arc</p>
        </div>
        <div className="header-stats">
          <div className="stat-pill">
            <span className={`dot ${wsConnected ? 'dot-green' : 'dot-yellow'}`} />
            {wsConnected ? 'Live' : 'Connecting...'}
          </div>
          <div className="stat-pill">
            <span className="dot dot-blue" />
            {txCount} txns on-chain
          </div>
          <div className="stat-pill">
            <span className="dot dot-yellow" />
            ${totalSpent.toFixed(4)} USDC spent
          </div>
          <a
            href="https://testnet.arcscan.app"
            target="_blank"
            rel="noreferrer"
            className="explorer-link"
          >
            Arc Explorer →
          </a>
        </div>
      </div>

      {/* ── Tags ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <span className="tag tag-arc">⛓ Arc Testnet</span>
        <span className="tag tag-usdc">💵 USDC</span>
        <span className="tag tag-circle">⭕ Circle Nanopayments</span>
        <span className="tag tag-arc">x402 Standard</span>
      </div>

      {/* ── Alerts ────────────────────────────────────────────────────── */}
      {alerts.length > 0 && (
        <div className="alerts">
          {alerts.slice(0, 4).map((a) => (
            <div key={a.id} className={`alert alert-${a.type === 'fraud' ? 'fraud' : a.type === 'success' ? 'success' : 'info'}`}>
              {a.message}
              {a.reason && <div className="alert-reason">{a.reason?.slice(0, 120)}</div>}
            </div>
          ))}
        </div>
      )}

      {/* ── Task Submit ───────────────────────────────────────────────── */}
      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panel-header">
          <span>🎯</span>
          <span className="panel-title">New Research Task</span>
        </div>
        <div className="panel-body">
          <TaskSubmit onSubmit={handleTaskSubmit} running={running} />
        </div>
      </div>

      {/* ── Agent Cards ───────────────────────────────────────────────── */}
      <div className="agent-grid">
        {AGENTS.map(agent => (
          <AgentCard
            key={agent.key}
            agent={agent}
            state={agentStates[agent.name] || { status: 'IDLE' }}
          />
        ))}
      </div>

      {/* ── Margin Calculator ─────────────────────────────────────────── */}
      <MarginCalculator txCount={txCount} totalSpent={totalSpent} />

      {/* ── Bottom panels ─────────────────────────────────────────────── */}
      <div className="bottom-grid">
        <div className="panel">
          <div className="panel-header">
            <span>⚡</span>
            <span className="panel-title">Live Nanopayments</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              {txCount} settled on Arc
            </span>
          </div>
          <div className="panel-body">
            <TransactionFeed transactions={transactions} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span>📋</span>
            <span className="panel-title">Audit Log</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              chain of thought
            </span>
          </div>
          <div className="panel-body">
            <AuditLog entries={auditEntries} />
          </div>
        </div>
      </div>

      {/* ── Report ────────────────────────────────────────────────────── */}
      {report && <ReportDisplay report={report} />}

    </div>
  )
}
