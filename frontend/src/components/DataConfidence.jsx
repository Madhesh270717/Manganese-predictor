import { useEffect, useState } from 'react'
import { apiGet } from '../services/api.js'
import RiskBadge from './RiskBadge.jsx'
import './DataConfidence.css'

// Persistent cross-cutting widget (PRD Section 39): shows the dataset →
// confidence level mapping from Phase 3's registry. Reused by later screens.
export default function DataConfidence() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiGet('/api/v1/data-confidence')
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="confidence-widget confidence-error">Confidence unavailable</div>
  if (!data) return <div className="confidence-widget">Loading confidence…</div>

  return (
    <div className="confidence-widget">
      <span className="confidence-title">Data Confidence</span>
      <ul className="confidence-list">
        {data.datasets.map((d) => (
          <li key={d.dataset} className="confidence-row">
            <span className="confidence-name">{d.dataset}</span>
            <RiskBadge level={d.confidence_level} />
          </li>
        ))}
      </ul>
    </div>
  )
}
