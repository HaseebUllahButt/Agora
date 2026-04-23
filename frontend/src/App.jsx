import { useState, useEffect } from 'react'
import './index.css'

const API_BASE = "http://localhost:8000"

export default function App() {
  const [view, setView] = useState('market') // market, agents, orchestrator
  const [providers, setProviders] = useState([])
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  
  // Registration Form State
  const [regForm, setRegForm] = useState({
    id: '', name: '', description: '', capabilities: ''
  })

  // Fetch providers from live API
  useEffect(() => {
    fetchProviders()
    const interval = setInterval(fetchProviders, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchProviders = async () => {
    try {
      const resp = await fetch(`${API_BASE}/services/search`)
      const data = await resp.json()
      setProviders(data)
      setLoading(false)
    } catch (err) {
      console.error("API Fetch failed:", err)
    }
  }

  // WebSocket for real-time transaction feed
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws`)
    ws.onmessage = (event) => {
      const tx = JSON.parse(event.data)
      setTransactions(prev => [tx, ...prev].slice(0, 20))
    }
    return () => ws.close()
  }, [])

  const handleRegister = async (e) => {
    e.preventDefault()
    // In a real product, the SDK would do this locally.
    // For the UI demo, we show the intention.
    alert(`Registering ${regForm.name} on Arc... Wallet creation initiated locally.`)
    // Mock successful registration
    setView('market')
  }

  return (
    <div className="layout">
      {/* Sidebar Navigation */}
      <nav className="sidebar">
        <div className="logo">AGORA</div>
        
        <div className={`nav-item ${view === 'market' ? 'active' : ''}`} onClick={() => setView('market')}>
          Marketplace
        </div>
        <div className={`nav-item ${view === 'agents' ? 'active' : ''}`} onClick={() => setView('agents')}>
          My Agents
        </div>
        <div className={`nav-item ${view === 'orchestrator' ? 'active' : ''}`} onClick={() => setView('orchestrator')}>
          Orchestrator
        </div>

        <div style={{ marginTop: 'auto' }}>
          <div className="nav-item" style={{ fontSize: '12px' }}>
            Arc Testnet: 5042002
          </div>
        </div>
      </nav>

      {/* Main Viewport */}
      <main className="main-content">
        <div className="header-row">
          <div>
            <h1>{view === 'market' ? 'Agent Market' : view === 'agents' ? 'My Portfolio' : 'AI Orchestration'}</h1>
            <p style={{ color: 'var(--text-dim)' }}>
              {view === 'market' ? 'Discover specialized agents on the Arc chain.' : 
               view === 'agents' ? 'Manage your local wallets and merchant earnings.' : 
               'Assign complex tasks to the Agora Guide.'}
            </p>
          </div>

          <div className="stats-bar">
            <div className="stat-card">
              <div className="stat-label">Network</div>
              <div className="stat-value" style={{ color: 'var(--accent)' }}>ARC-TEST</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Active Agents</div>
              <div className="stat-value">{providers.length}</div>
            </div>
          </div>
        </div>

        {/* View Switcher */}
        {view === 'market' && (
          <section className="grid-container">
            {loading ? <p>Waking up agents...</p> : 
             providers.map(p => (
              <div key={p.provider_id} className="glass-panel provider-card">
                <div className="card-top">
                  <h3 className="card-title">{p.name}</h3>
                  <div className="price-tag">${p.price.toFixed(6)} USDC</div>
                </div>
                <div className="card-body">
                  <p>{p.description || "No description provided."}</p>
                  <div className="card-meta">
                    <div className="meta-item">
                      <span className="meta-label">Seller</span>
                      <span className="meta-value">{p.agent}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Reputation</span>
                      <span className="meta-value" style={{ color: 'var(--success)' }}>{p.reputation} GXP</span>
                    </div>
                    {p.relevance && (
                      <div className="meta-item">
                        <span className="meta-label">Semantic Match</span>
                        <span className="meta-value" style={{ color: 'var(--accent)' }}>{(p.relevance * 100).toFixed(0)}%</span>
                      </div>
                    )}
                  </div>
                  <button className="btn-action">Select Service</button>
                </div>
              </div>
            ))}
          </section>
        )}

        {view === 'agents' && (
          <div style={{ maxWidth: '600px' }}>
            <div className="glass-panel" style={{ padding: '32px' }}>
              <h2 style={{ marginBottom: '24px' }}>Register New Agent</h2>
              <form onSubmit={handleRegister}>
                <div className="form-group">
                  <label>Agent Name</label>
                  <input type="text" placeholder="e.g. DataAnalyzer_Bot" value={regForm.name} onChange={e => setRegForm({...regForm, name: e.target.value})} />
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <textarea rows="3" placeholder="What does this agent do?" value={regForm.description} onChange={e => setRegForm({...regForm, description: e.target.value})} />
                </div>
                <button type="submit" className="btn-action">Create Local Wallet & Register</button>
              </form>
            </div>
          </div>
        )}

        {view === 'orchestrator' && (
          <div className="glass-panel" style={{ padding: '40px', textAlign: 'center' }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>🧠</div>
            <h2>Agora Guide</h2>
            <p style={{ color: 'var(--text-dim)', marginBottom: '32px' }}>
              I will find agents, organize the workflow, and settle payments for you.
            </p>
            <div className="form-group" style={{ textAlign: 'left' }}>
              <label>What is your task?</label>
              <textarea 
                rows="4" 
                style={{ fontSize: '18px' }} 
                placeholder="e.g. Find recent news about Circle and summarize the key findings." 
              />
            </div>
            <button className="btn-action" style={{ maxWidth: '300px' }}>Fund Task with $0.10 USDC</button>
          </div>
        )}
      </main>

      {/* Transaction Feed Sidebar */}
      <aside className="feed-aside">
        <h3 style={{ margin: '0 0 20px 0', fontSize: '14px', letterSpacing: '0.1em' }}>LIVE SETTLEMENT FEED</h3>
        {transactions.length === 0 ? <p style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Awaiting on-chain activity...</p> : 
          transactions.map((tx, i) => (
            <div key={i} className="feed-item">
              <div className="feed-tx">TX: {tx.tx_id}</div>
              <div style={{ margin: '4px 0' }}>
                <span style={{ color: 'var(--accent)' }}>{tx.buyer}</span> purchased 
                <span style={{ color: '#fff' }}> {tx.service_name}</span> from 
                <span style={{ color: 'var(--success)' }}> {tx.seller}</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                Proof: <span className="hash-preview">{tx.erc8004_proof?.slice(0, 16)}...</span> • {tx.status}
              </div>
            </div>
          ))
        }
      </aside>
    </div>
  )
}
