import { useState } from 'react'

const SIZES   = ['Startup', 'SMB', 'Enterprise']
const STAGES  = ['Pre-seed', 'Seed', 'Series A', 'Growth']

export default function TaskSubmit({ onSubmit, running }) {
  const [topic,    setTopic]    = useState('')
  const [budget,   setBudget]   = useState('0.10')
  const [size,     setSize]     = useState('Startup')
  const [stage,    setStage]    = useState('Seed')
  const [strength, setStrength] = useState('')
  const [weakness, setWeakness] = useState('')
  const [market,   setMarket]   = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!topic.trim()) return

    onSubmit({
      topic:   topic.trim(),
      budget:  parseFloat(budget) || 0.10,
      task_type: 'competitive_intelligence',
      company_context: {
        company_size:  size.toLowerCase(),
        stage:         stage.toLowerCase().replace(' ', '-'),
        main_strength: strength || 'engineering',
        main_weakness: weakness || 'distribution',
        budget:        parseFloat(budget) > 0.2 ? 'moderate' : 'limited',
        target_market: market || 'SMBs',
      }
    })
  }

  return (
    <form className="task-form" onSubmit={handleSubmit}>

      {/* Topic — full width */}
      <div className="form-group">
        <label className="form-label">Research Topic</label>
        <input
          id="topic-input"
          className="form-input"
          placeholder="e.g. Stripe competitor analysis, OpenAI pricing, Notion vs Linear"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          disabled={running}
          required
        />
      </div>

      {/* Budget */}
      <div className="form-group">
        <label className="form-label">Budget (USDC)</label>
        <div className="budget-row">
          <input
            id="budget-input"
            className="form-input"
            type="number"
            min="0.05"
            max="5"
            step="0.01"
            value={budget}
            onChange={e => setBudget(e.target.value)}
            disabled={running}
            style={{ maxWidth: 140 }}
          />
          <span className="budget-hint">
            ${budget} ≈ {Math.floor(parseFloat(budget || 0) / 0.004)} agent calls
            · same on Ethereum ≈ ${(parseFloat(budget || 0) * 2.95 / 0.004).toFixed(0)} in gas
          </span>
        </div>
      </div>

      {/* Company context row 1 */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Company Size</label>
          <select
            id="company-size-select"
            className="form-select"
            value={size}
            onChange={e => setSize(e.target.value)}
            disabled={running}
          >
            {SIZES.map(s => <option key={s}>{s}</option>)}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Growth Stage</label>
          <select
            id="stage-select"
            className="form-select"
            value={stage}
            onChange={e => setStage(e.target.value)}
            disabled={running}
          >
            {STAGES.map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {/* Company context row 2 */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Main Strength</label>
          <input
            id="strength-input"
            className="form-input"
            placeholder="e.g. developer experience"
            value={strength}
            onChange={e => setStrength(e.target.value)}
            disabled={running}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Main Weakness</label>
          <input
            id="weakness-input"
            className="form-input"
            placeholder="e.g. brand recognition"
            value={weakness}
            onChange={e => setWeakness(e.target.value)}
            disabled={running}
          />
        </div>
      </div>

      {/* Target market */}
      <div className="form-group">
        <label className="form-label">Target Market</label>
        <input
          id="market-input"
          className="form-input"
          placeholder="e.g. SMBs, developers, enterprise teams"
          value={market}
          onChange={e => setMarket(e.target.value)}
          disabled={running}
        />
      </div>

      <button
        id="submit-btn"
        type="submit"
        className={`submit-btn ${running ? 'running' : ''}`}
        disabled={running || !topic.trim()}
      >
        {running ? (
          <span style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'center' }}>
            <span className="spinner" />
            Agents working…
          </span>
        ) : (
          '🚀 Run Research Pipeline'
        )}
      </button>

    </form>
  )
}
