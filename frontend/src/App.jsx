import { useState, useEffect } from 'react'
import './App.css'

// Mock provider data
const INITIAL_PROVIDERS = {
  compute: [
    { id: 'groq', name: 'Groq', category: 'compute', description: 'Llama 3.1 70B - Fast inference', basePrice: 0.0002, dynamicPrice: 0.00023, qualityScore: 4.8, latency: 240, uptime: 99.9, activeRequests: 143 },
    { id: 'claude', name: 'Claude API', category: 'compute', description: 'Claude 3.5 Sonnet - High quality', basePrice: 0.0005, dynamicPrice: 0.00048, qualityScore: 4.9, latency: 420, uptime: 99.95, activeRequests: 87 },
    { id: 'gemini', name: 'Google Gemini', category: 'compute', description: 'Gemini 2.0 Flash - Balanced', basePrice: 0.0003, dynamicPrice: 0.00032, qualityScore: 4.7, latency: 380, uptime: 99.8, activeRequests: 120 }
  ],
  data: [
    { id: 'eth-price', name: 'ETH Price Feed', category: 'data', description: 'Real-time Ethereum pricing', basePrice: 0.00008, dynamicPrice: 0.00009, qualityScore: 4.95, latency: 45, uptime: 99.99, activeRequests: 267 },
    { id: 'weather', name: 'Weather Sensor', category: 'data', description: 'Real-time temperature data', basePrice: 0.00005, dynamicPrice: 0.00005, qualityScore: 4.6, latency: 120, uptime: 99.5, activeRequests: 45 },
    { id: 'traffic', name: 'Traffic Monitor', category: 'data', description: 'Urban traffic flow data', basePrice: 0.0001, dynamicPrice: 0.00011, qualityScore: 4.4, latency: 250, uptime: 99.2, activeRequests: 98 }
  ],
  capability: [
    { id: 'web-search', name: 'Web Search', category: 'capability', description: 'Credentialed web search + ranking', basePrice: 0.0003, dynamicPrice: 0.00035, qualityScore: 4.7, latency: 890, uptime: 99.7, activeRequests: 154 },
    { id: 'validator', name: 'Fact Validator', category: 'capability', description: 'Third-party claim verification', basePrice: 0.0008, dynamicPrice: 0.00084, qualityScore: 4.85, latency: 1200, uptime: 99.95, activeRequests: 67 },
    { id: 'sandbox', name: 'Code Sandbox', category: 'capability', description: 'Secure Python code execution', basePrice: 0.001, dynamicPrice: 0.00098, qualityScore: 4.6, latency: 1450, uptime: 99.6, activeRequests: 58 }
  ]
}

export default function App() {
  const [category, setCategory] = useState('compute')
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('price')
  const [providers, setProviders] = useState([])

  // Initialize
  useEffect(() => {
    const all = [...INITIAL_PROVIDERS.compute, ...INITIAL_PROVIDERS.data, ...INITIAL_PROVIDERS.capability]
    setProviders(all)
  }, [])

  // Update prices every 3 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setProviders(prevProviders =>
        prevProviders.map(p => ({
          ...p,
          dynamicPrice: Math.round((p.basePrice * (0.9 + Math.random() * 0.2)) * 1000000) / 1000000,
          activeRequests: Math.max(20, p.activeRequests + Math.floor((Math.random() - 0.5) * 30))
        }))
      )
    }, 3000)
    return () => clearInterval(interval)
  }, [])



  // Filter and sort
  const filtered = providers
    .filter(p => p.category === category)
    .filter(p => 
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.description.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .sort((a, b) => {
      switch (sortBy) {
        case 'price': return a.dynamicPrice - b.dynamicPrice
        case 'quality': return b.qualityScore - a.qualityScore
        case 'latency': return a.latency - b.latency
        default: return 0
      }
    })

  const stats = {
    total: providers.length,
    active: providers.filter(p => p.uptime > 99).length,
    avgQuality: (providers.reduce((s, p) => s + p.qualityScore, 0) / providers.length).toFixed(1)
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-container">
          <div>
            <h1>AGORA</h1>
            <p className="subtitle">Agent-to-Agent Marketplace for Arc USDC</p>
          </div>
          <div className="header-stats">
            <div className="stat">
              <div className="stat-value">{stats.total}</div>
              <div className="stat-label">Providers</div>
            </div>
            <div className="stat">
              <div className="stat-value">{stats.active}</div>
              <div className="stat-label">Active</div>
            </div>
            <div className="stat">
              <div className="stat-value">{stats.avgQuality}★</div>
              <div className="stat-label">Avg Quality</div>
            </div>
          </div>
        </div>
      </header>

      <div className="container">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-section">
            <h3>Category</h3>
            {['compute', 'data', 'capability'].map(cat => (
              <button
                key={cat}
                className={`category-button ${category === cat ? 'active' : ''}`}
                onClick={() => setCategory(cat)}
              >
                {cat.toUpperCase()}
              </button>
            ))}
          </div>

          <hr />

          <div className="sidebar-section">
            <h3>Sort</h3>
            {[
              { label: 'Price (Low)', value: 'price' },
              { label: 'Quality', value: 'quality' },
              { label: 'Latency', value: 'latency' }
            ].map(opt => (
              <label key={opt.value} className="radio-label">
                <input 
                  type="radio" 
                  name="sort" 
                  value={opt.value} 
                  checked={sortBy === opt.value}
                  onChange={(e) => setSortBy(e.target.value)}
                />
                {opt.label}
              </label>
            ))}
          </div>
        </aside>

        {/* Main */}
        <main className="main">
          {/* Search */}
          <div className="search-box">
            <input
              type="text"
              placeholder="Search providers..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {/* Provider Grid */}
          <section className="grid-section">
            <h2>Available Providers ({filtered.length})</h2>
            <div className="provider-grid">
              {filtered.map(p => (
                <div key={p.id} className="provider-card">
                  <div className="card-header">
                    <h3>{p.name}</h3>
                    <span className="quality-badge">{p.qualityScore.toFixed(1)}★</span>
                  </div>
                  <p className="card-description">{p.description}</p>
                  <div className="card-metrics">
                    <div className="metric">
                      <span className="metric-label">Price</span>
                      <span className="metric-value">${p.dynamicPrice.toFixed(6)}</span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">Latency</span>
                      <span className="metric-value">{p.latency}ms</span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">Uptime</span>
                      <span className="metric-value">{p.uptime}%</span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">Requests</span>
                      <span className="metric-value">{p.activeRequests}</span>
                    </div>
                  </div>
                  <button className="select-button">Select Provider</button>
                </div>
              ))}
            </div>
          </section>


        </main>
      </div>

      {/* Footer */}
      <footer className="footer">
        <p>Arc Testnet • x402 Payments • Circle Nanopayments • Sub-cent Transactions</p>
      </footer>
    </div>
  )
}
