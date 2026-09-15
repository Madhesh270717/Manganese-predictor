import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet, apiPost } from '../services/api.js'
import Card from '../components/Card.jsx'
import RiskBadge from '../components/RiskBadge.jsx'
import { Skeleton, ErrorState } from '../components/Feedback.jsx'
import './Recommendations.css'

// Screen 6 — Recommendations (PRD Sections 20–21, 36).
// Phase 20 reallocation recommendations: the EX-04 A1→C3 demo path with
// expected impact from real model calls, ranking detail, before/after
// schedule comparison, and accept/reset for the repeatable demo.

export default function Recommendations() {
  const navigate = useNavigate()
  const [state, setState] = useState({ loading: true, error: null, data: null })
  const [demoState, setDemoState] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  const load = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    Promise.all([
      apiGet('/api/v1/recommendations'),
      apiGet('/api/v1/production/shortfall/current'),
      apiGet('/api/v1/demo/state'),
    ])
      .then(([recommendations, shortfall, demo]) => {
        setState({ loading: false, error: null, data: { recommendations, shortfall } })
        setDemoState(demo)
      })
      .catch((err) => setState({ loading: false, error: err.message, data: null }))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const accept = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const result = await apiPost('/api/v1/demo/accept')
      setDemoState(result)
      setMessage({ kind: 'ok', text: `Recommendation approved: ${result.accepted?.equipment_id} ${result.accepted?.from_zone} → ${result.accepted?.to_zone}` })
    } catch (err) {
      setMessage({ kind: 'err', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const result = await apiPost('/api/v1/demo/reset')
      setDemoState(result)
      setMessage({ kind: 'ok', text: 'Demo reset — back to pre-accept state.' })
    } catch (err) {
      setMessage({ kind: 'err', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  if (state.loading) {
    return (
      <div className="recommendations">
        <h1>Recommendations</h1>
        <Skeleton rows={6} />
      </div>
    )
  }
  if (state.error) {
    return (
      <div className="recommendations">
        <h1>Recommendations</h1>
        <ErrorState message={`Backend unreachable: ${state.error}`} onRetry={load} />
      </div>
    )
  }

  const { recommendations, shortfall } = state.data
  const recs = recommendations.recommendations || []
  const accepted = demoState?.accepted

  return (
    <div className="recommendations">
      <header className="rec-header">
        <h1>Recommendations</h1>
        <span className="rec-sub">Optimization Engine (Phase 20) · pending approval (human-in-the-loop)</span>
      </header>

      {message && (
        <div className={`rec-message ${message.kind}`}>{message.text}</div>
      )}

      {recs.length === 0 ? (
        <Card title="No Active Recommendations">
          <p className="detail-text">
            No risk triggers are currently active. Run the weather demo trigger
            (Phase 8) to re-create the A1 rainfall spike and regenerate
            recommendations.
          </p>
        </Card>
      ) : (
        recs.map((rec) => {
          const impact = rec.expected_impact || {}
          return (
            <Card key={rec.equipment_id} title={`${rec.alert} — ${rec.equipment_id}`} className="rec-card">
              <div className="rec-action-line">
                <span className="rec-move">
                  MOVE <strong>{rec.equipment_id}</strong> from{' '}
                  <strong>{rec.from_zone}</strong> → <strong>{rec.to_zone}</strong>
                </span>
                <RiskBadge level={rec.status === 'approved' ? 'LOW' : 'MEDIUM'} />
              </div>
              <p className="rec-reason">{rec.reason}</p>

              <div className="rec-impact">
                <div className="impact-box">
                  <span className="impact-label">Production</span>
                  <span className="impact-value">
                    {Math.round(impact.production_before).toLocaleString()} →{' '}
                    {Math.round(impact.production_after).toLocaleString()} t
                  </span>
                  <span className="impact-delta good">
                    +{Math.round(impact.production_after - impact.production_before).toLocaleString()} t recovered
                  </span>
                </div>
                <div className="impact-box">
                  <span className="impact-label">Shortfall</span>
                  <span className="impact-value">
                    {Math.round(impact.shortfall_before).toLocaleString()} →{' '}
                    {Math.round(impact.shortfall_after).toLocaleString()} t
                  </span>
                  <span className="impact-delta good">
                    {Math.round(((impact.shortfall_before - impact.shortfall_after) / impact.shortfall_before) * 100)}% reduction
                  </span>
                </div>
                <div className="impact-box">
                  <span className="impact-label">Shortfall %</span>
                  <span className="impact-value">
                    {impact.shortfall_percentage_before}% → {impact.shortfall_percentage_after}%
                  </span>
                  <span className="impact-delta">{rec.status}</span>
                </div>
              </div>

              <div className="rec-ranking">
                <h4>Candidate ranking (Phase 19)</h4>
                <table className="rec-table">
                  <thead>
                    <tr>
                      <th>Zone</th>
                      <th>Total</th>
                      <th>Risk</th>
                      <th>Dist</th>
                      <th>Equip</th>
                      <th>Prosp</th>
                      <th>Shortfall Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(rec.ranking || []).map((r, i) => (
                      <tr key={r.candidate_zone_id} className={i === 0 ? 'top-rank' : ''}>
                        <td>{r.candidate_zone_id}</td>
                        <td>{r.total_score}</td>
                        <td>{r.criteria.production_risk}</td>
                        <td>{r.criteria.distance}</td>
                        <td>{r.criteria.equipment}</td>
                        <td>{r.criteria.prospectivity}</td>
                        <td>{r.criteria.shortfall_delta}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="rec-actions">
                {accepted ? (
                  <>
                    <span className="accepted-badge">✓ Approved — {accepted.from_zone} → {accepted.to_zone}</span>
                    <button className="cta-button secondary" onClick={reset} disabled={busy}>
                      Reset Demo
                    </button>
                  </>
                ) : (
                  <button className="cta-button" onClick={accept} disabled={busy}>
                    {busy ? 'Processing…' : 'Accept & Apply'}
                  </button>
                )}
              </div>
            </Card>
          )
        })
      )}

      <Card title="Current Schedule Shortfall (Phase 16)">
        <p className="detail-text">
          Target {shortfall.target.toLocaleString()} t · Predicted {shortfall.predicted.toLocaleString()} t ·{' '}
          Shortfall {Math.abs(shortfall.shortfall_tonnes).toLocaleString()} t ({shortfall.shortfall_percentage}%) ·{' '}
          Risk <RiskBadge level={shortfall.risk_level} />
        </p>
      </Card>

      <div className="cta-row">
        <button className="cta-button" onClick={() => navigate('/assistant')}>
          Ask Spotter AI About This →
        </button>
      </div>
    </div>
  )
}
