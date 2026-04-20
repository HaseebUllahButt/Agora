import { useState, useEffect, useRef } from 'react'
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
  { key: 'consultancy', name: 'Consultancy Agent', icon: '💼', port: 8006, price: '$0.0015' },
]

const API_BASE = 'http://localhost:8000'
const WS_URL   = 'ws://localhost:8000/ws'

export default function App() {
  const [agentStates, setAgentStates]     = useState({})
  const [transactions, setTransactions]   = useState([])
  const [auditEntries, setAuditEntries]   = useState([])
  const [report, setReport]               = useState(null)
  const [topic, setTopic]                 = useState('')
  const [txCount, setTxCount]             = useState(0)
  const [totalSpent, setTotalSpent]       = useState(0)
  const [alerts, setAlerts]               = useState([])
  const [running, setRunning]             = useState(false)
  const [wsConnected, setWsConnected]     = useState(false)
  const [plannedLoops, setPlannedLoops]   = useState(0)
  const [currentLoop, setCurrentLoop]     = useState(0)
  const [fraudBanner, setFraudBanner]     = useState(null)
  const ws = useRef(null)
  const wsRetryDelay = useRef(2000)
  const wsRetryTimer = useRef(null)
  const fraudTimer = useRef(null)

  const progressPct = plannedLoops > 0 ? Math.min(100, Math.round((currentLoop / plannedLoops) * 100)) : 0
  const mode = report ? 'complete' : running ? 'running' : 'landing'

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
      clearTimeout(fraudTimer.current)
      clearInterval(ws.current?._ping)
      ws.current?.close()
    }
  }, [])

  const handleWsEvent = (msg) => {
    const now = new Date().toLocaleTimeString()

    switch (msg.event) {
      case 'pipeline_started':
        setTopic(msg.topic || '')
        setPlannedLoops(msg.planned_loops || 0)
        setCurrentLoop(0)
        setAuditEntries(prev => [{
          ts: now,
          msg: `Pipeline started: ${msg.topic} | Budget: $${msg.budget} | ${msg.planned_loops} loops`,
          type: 'info'
        }, ...prev])
        break

      case 'loop_start':
        setCurrentLoop(msg.loop || 0)
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
        setFraudBanner({
          agent: msg.agent,
          reason: msg.reason,
          ts: Date.now()
        })
        clearTimeout(fraudTimer.current)
        fraudTimer.current = setTimeout(() => setFraudBanner(null), 4000)
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
        setCurrentLoop(plannedLoops || currentLoop)
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
    setTopic(taskData.topic || '')
    setTxCount(0)
    setTotalSpent(0)
    setAuditEntries([])
    setPlannedLoops(0)
    setCurrentLoop(0)
    setFraudBanner(null)
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

      if (!res.ok || result?.error) {
        setRunning(false)
        setAlerts(prev => [{
          type: 'fraud',
          message: `Pipeline failed: ${result?.error || `HTTP ${res.status}`}`,
          id: Date.now()
        }, ...prev])

        if (result?.audit_log) {
          const entries = result.audit_log.map(e => ({
            ts: e.timestamp?.slice(11, 19) || '',
            msg: e.message,
            type: e.message?.toUpperCase().includes('FRAUD') ? 'fraud'
                : e.message?.includes('confirmed') || e.message?.includes('Paying') ? 'payment'
                : 'default'
          }))
          setAuditEntries(entries)
        }
        return
      }

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

      <div className="header">
        <div className="header-left">
          <h1>Agora</h1>
          <p className="tagline">Autonomous Research Protocol on Arc</p>
        </div>
        <div className="header-stats">
          <div className="stat-pill">
            <span className="dot dot-blue" />
            TESTNET
          </div>
          <div className="stat-pill">
            <span className={`dot ${wsConnected ? 'dot-green' : 'dot-yellow'}`} />
            {wsConnected ? 'LIVE' : 'CONNECTING'}
          </div>
          <div className="stat-pill">
            {txCount} TXNS
          </div>
          <div className="stat-pill stat-money">
            ${totalSpent.toFixed(6)} SPENT
          </div>
          <a
            href="https://testnet.arcscan.app"
            target="_blank"
            rel="noreferrer"
            className="explorer-link"
          >
            ARC EXPLORER ↗
          </a>
        </div>
      </div>

      <div className="tags-row">
        <span className="tag tag-arc">⛓ Arc Testnet</span>
        <span className="tag tag-usdc">💵 USDC</span>
        <span className="tag tag-circle">⭕ Circle Nanopayments</span>
        <span className="tag tag-arc">x402 Standard</span>
      </div>

      {fraudBanner && (
        <div className="fraud-banner">
          <div className="fraud-banner-title">⚠ FRAUD DETECTED · RECOVERING</div>
          <div className="fraud-banner-line">INVALID OUTPUT from {fraudBanner.agent}</div>
          <div className="fraud-banner-line">Reason: {fraudBanner.reason}</div>
          <div className="fraud-banner-line">Action: Task redistributed — agent wallet flagged</div>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="alerts">
          {alerts.slice(0, 2).map((a) => (
            <div key={a.id} className={`alert alert-${a.type === 'fraud' ? 'fraud' : a.type === 'success' ? 'success' : 'info'}`}>
              {a.message}
              {a.reason && <div className="alert-reason">{a.reason?.slice(0, 120)}</div>}
            </div>
          ))}
        </div>
      )}

      {mode === 'landing' && (
        <div className="panel landing-panel">
          <div className="panel-header">
            <span>🎯</span>
            <span className="panel-title">What do you want to research?</span>
          </div>
          <div className="panel-body">
            <TaskSubmit onSubmit={handleTaskSubmit} running={running} />
          </div>
        </div>
      )}

      {mode === 'running' && (
        <>
          <div className="running-shell">
            <div className="running-left panel">
              <div className="panel-header">
                <span>🤖</span>
                <span className="panel-title">Agent Economy</span>
              </div>
              <div className="panel-body">
                <div className="agent-grid">
                  {AGENTS.map(agent => (
                    <AgentCard
                      key={agent.key}
                      agent={agent}
                      state={agentStates[agent.name] || { status: 'IDLE' }}
                    />
                  ))}
                </div>

                <div className="progress-wrap">
                  <div className="progress-head">
                    <span>Progress</span>
                    <span>{progressPct}%</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${progressPct}%` }} />
                  </div>
                  <div className="progress-meta">Loop {currentLoop || 0} of {plannedLoops || '—'} · {topic || 'Task running'}</div>
                </div>
              </div>
            </div>

            <div className="running-right">
              <div className="panel">
                <div className="panel-header">
                  <span>⚡</span>
                  <span className="panel-title">Transaction Feed</span>
                </div>
                <div className="panel-body">
                  <TransactionFeed transactions={transactions} />
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <span>📋</span>
                  <span className="panel-title">Audit Log</span>
                </div>
                <div className="panel-body">
                  <AuditLog entries={auditEntries} />
                </div>
              </div>
            </div>
          </div>

          <MarginCalculator txCount={txCount} totalSpent={totalSpent} />
        </>
      )}

      {mode === 'complete' && (
        <>
          <MarginCalculator txCount={txCount} totalSpent={totalSpent} />
          <ReportDisplay report={report} />
        </>
      )}

    </div>
  )
}
