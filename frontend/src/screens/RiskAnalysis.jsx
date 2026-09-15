import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../services/api.js'
import Card from '../components/Card.jsx'
import RiskBadge from '../components/RiskBadge.jsx'
import ProgressBar from '../components/ProgressBar.jsx'
import { Skeleton, ErrorState } from '../components/Feedback.jsx'
import './RiskAnalysis.css'

// Screen 4 — Risk Analysis (PRD Sections 15–16, 33–34).
// Shortfall risk (P16) + SHAP contributor breakdown (P17) + the Phase 19
// risk triggers driving reallocation.

export default function RiskAnalysis() {
  const navigate = useNavigate()
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = () => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    Promise.all([
      apiGet('/api/v1/production/shortfall/current'),
      apiGet('/api/v1/production/shortfall/current/explain'),
      apiGet('/api/v1/optimization/risks'),
      apiGet('/api/v1/weather/risk-alert'),
    ])
      .then(([shortfall, explain, risks, weatherAlerts]) =>
        setState({ loading: false, error: null, data: { shortfall, explain, risks, weatherAlerts } })
      )
      .catch((err) => setState({ loading: false, error: err.message, data: null }))
  }

  useEffect(() => {
    load()
  }, [])

  if (state.loading) {
    return (
      <div className="risk-analysis">
        <h1>Risk Analysis</h1>
        <Skeleton rows={6} />
      </div>
    )
  }
  if (state.error) {
    return (
      <div className="risk-analysis">
        <h1>Risk Analysis</h1>
        <ErrorState message={`Backend unreachable: ${state.error}`} onRetry={load} />
      </div>
    )
  }

  const { shortfall, explain, risks, weatherAlerts } = state.data

  return (
    <div className="risk-analysis">
      <header className="risk-header">
        <h1>Risk Analysis</h1>
        <span className="risk-sub">Shortfall risk (P16) · cause attribution (P17) · reallocation triggers (P19)</span>
      </header>

      <div className="stat-grid">
        <div className="stat-box">
          <span className="stat-box-label">Predicted</span>
          <span className="stat-box-value">{shortfall.predicted.toLocaleString()} t</span>
        </div>
        <div className="stat-box">
          <span className="stat-box-label">Shortfall</span>
          <span className="stat-box-value">{Math.abs(shortfall.shortfall_tonnes).toLocaleString()} t</span>
          <span className="stat-box-sub">{shortfall.shortfall_percentage}% vs target</span>
        </div>
        <div className="stat-box">
          <span className="stat-box-label">Risk Level</span>
          <span className="stat-box-value">
            <RiskBadge level={shortfall.risk_level} />
          </span>
        </div>
      </div>

      <div className="risk-lower">
        <Card title="Shortfall Risk — PRD Section 15">
          <ProgressBar
            percentage={shortfall.shortfall_percentage}
            label={`${shortfall.risk_level} (${shortfall.shortfall_percentage}%)`}
          />
          <p className="detail-text">
            Target {shortfall.target.toLocaleString()} t · Predicted {shortfall.predicted.toLocaleString()} t
          </p>
        </Card>

        <Card title="Cause Attribution — SHAP (Phase 17)">
          <div className="contributor-list">
            {explain.contributors.map((c) => (
              <div key={c.category} className="contributor-row">
                <span className="contributor-label">{c.label}</span>
                <div className="contributor-track">
                  <div
                    className={`contributor-fill cat-${c.category}`}
                    style={{ width: `${c.contribution_percentage}%` }}
                  />
                </div>
                <span className="contributor-pct">{c.contribution_percentage}%</span>
              </div>
            ))}
          </div>
          <p className="detail-text">
            {explain.shortfall_tonnes.toLocaleString()} t shortfall explained · top driver: {explain.top_contributor}
          </p>
        </Card>
      </div>

      <Card title="Reallocation Risk Triggers (Phase 19)" className="triggers-card">
        {risks.triggers.length === 0 ? (
          <p className="detail-text">No active risk triggers — the schedule is stable.</p>
        ) : (
          <table className="trigger-table">
            <thead>
              <tr>
                <th>Equipment</th>
                <th>Zone</th>
                <th>Reason</th>
                <th>Severity</th>
              </tr>
            </thead>
            <tbody>
              {risks.triggers.map((t, i) => (
                <tr key={i}>
                  <td>{t.equipment_id}</td>
                  <td>{t.current_zone_id}</td>
                  <td className="trigger-reason">{t.risk_reason}</td>
                  <td><RiskBadge level={t.severity} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {weatherAlerts.alerts.length > 0 && (
        <Card title="Weather Risk Alerts (Phase 8)" className="triggers-card">
          <table className="trigger-table">
            <thead>
              <tr>
                <th>Zone</th>
                <th>Date</th>
                <th>Rainfall 1d</th>
                <th>Rainfall 7d</th>
                <th>Trigger</th>
              </tr>
            </thead>
            <tbody>
              {weatherAlerts.alerts.map((a, i) => (
                <tr key={i}>
                  <td>{a.zone_id}</td>
                  <td>{a.date}</td>
                  <td>{a.rainfall_1d} mm</td>
                  <td>{a.rainfall_7d} mm</td>
                  <td>{a.trigger}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <div className="cta-row">
        <button className="cta-button" onClick={() => navigate('/recommendations')}>
          View Recommended Actions →
        </button>
      </div>
    </div>
  )
}
