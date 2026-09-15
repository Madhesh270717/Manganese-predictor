import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet, apiPost } from '../services/api.js'
import Card from '../components/Card.jsx'
import RiskBadge from '../components/RiskBadge.jsx'
import { Skeleton, ErrorState } from '../components/Feedback.jsx'
import './DynamicSchedule.css'

// Screen 5 — Dynamic Schedule (PRD Sections 18, 35).
// Current equipment→zone→shift schedule (P10), fleet status (P9), and the
// PRD Section 22 constraint validation / Phase 21 recalculation controls.

export default function DynamicSchedule() {
  const navigate = useNavigate()
  const [state, setState] = useState({ loading: true, error: null, data: null })
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState(null)
  const [recalc, setRecalc] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    Promise.all([
      apiGet('/api/v1/schedule/current'),
      apiGet('/api/v1/equipment'),
      apiGet('/api/v1/production/predict/current'),
    ])
      .then(([schedule, equipment, forecast]) =>
        setState({ loading: false, error: null, data: { schedule, equipment, forecast } })
      )
      .catch((err) => setState({ loading: false, error: err.message, data: null }))
  }

  useEffect(() => {
    load()
  }, [])

  const runValidation = async () => {
    setValidating(true)
    setValidation(null)
    try {
      const payload = await apiPost('/api/v1/optimization/validate-schedule', {
        schedule: state.data.schedule.entries,
      })
      setValidation(payload)
    } catch (err) {
      setValidation({ error: err.message })
    } finally {
      setValidating(false)
    }
  }

  const runRecalc = async () => {
    setBusy(true)
    setRecalc(null)
    try {
      const payload = await apiPost('/api/v1/recalculation/trigger')
      setRecalc(payload)
    } catch (err) {
      setRecalc({ error: err.message })
    } finally {
      setBusy(false)
    }
  }

  if (state.loading) {
    return (
      <div className="dynamic-schedule">
        <h1>Dynamic Schedule</h1>
        <Skeleton rows={6} />
      </div>
    )
  }
  if (state.error) {
    return (
      <div className="dynamic-schedule">
        <h1>Dynamic Schedule</h1>
        <ErrorState message={`Backend unreachable: ${state.error}`} onRetry={load} />
      </div>
    )
  }

  const { schedule, equipment, forecast } = state.data

  // Aggregate schedule by equipment (current zone + daily planned output).
  const byEquipment = new Map()
  for (const entry of schedule.entries) {
    const key = entry.equipment_id
    const agg = byEquipment.get(key) || { equipment_id: key, zone_id: entry.zone_id, output: 0 }
    agg.output += entry.expected_output || 0
    byEquipment.set(key, agg)
  }

  return (
    <div className="dynamic-schedule">
      <header className="schedule-header">
        <h1>Dynamic Schedule</h1>
        <span className="schedule-sub">
          Current schedule · Predicted {Math.round(forecast.predicted_tonnes).toLocaleString()} t vs target{' '}
          {Math.round(forecast.target_tonnes).toLocaleString()} t
        </span>
      </header>

      <div className="schedule-actions">
        <button className="cta-button" onClick={runValidation} disabled={validating || state.loading}>
          {validating ? 'Validating…' : 'Validate Schedule (PRD §22)'}
        </button>
        <button className="cta-button secondary" onClick={runRecalc} disabled={busy || state.loading}>
          {busy ? 'Running…' : 'Trigger Recalculation (P21)'}
        </button>
      </div>

      {validation && (
        <Card title="Constraint Validation — PRD Section 22">
          {validation.error ? (
            <p className="detail-text">{validation.error}</p>
          ) : (
            <div className="validation-grid">
              {(validation.constraints || []).map((c, i) => (
                <div key={i} className="validation-item">
                  <span className="validation-name">{c.constraint || c.name || `constraint ${i + 1}`}</span>
                  <RiskBadge level={c.status === 'ok' || c.valid ? 'LOW' : 'HIGH'} />
                </div>
              ))}
              {validation.or_tools && (
                <div className="validation-item">
                  <span className="validation-name">OR-Tools CP-SAT</span>
                  <RiskBadge level={validation.or_tools.feasible ? 'LOW' : 'HIGH'} />
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {recalc && (
        <Card title="Recalculation Cycle (Phase 21)">
          {recalc.error ? (
            <p className="detail-text">{recalc.error}</p>
          ) : (
            <div className="validation-grid">
              <div className="validation-item">
                <span className="validation-name">Outcome</span>
                <strong>{recalc.outcome}</strong>
              </div>
              {recalc.recommendation && (
                <div className="validation-item">
                  <span className="validation-name">Recommendation</span>
                  <strong>
                    {recalc.recommendation.equipment_id}: {recalc.recommendation.from_zone} →{' '}
                    {recalc.recommendation.to_zone}
                  </strong>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      <div className="schedule-lower">
        <Card title="Current Assignments — Equipment → Zone" className="table-card">
          <table className="schedule-table">
            <thead>
              <tr>
                <th>Equipment</th>
                <th>Type</th>
                <th>Zone</th>
                <th>Availability</th>
                <th>Planned output</th>
              </tr>
            </thead>
            <tbody>
              {equipment.equipment.map((u) => {
                const agg = byEquipment.get(u.equipment_id)
                return (
                  <tr key={u.equipment_id} className={u.current_zone_id === 'A1' ? 'at-risk-row' : ''}>
                    <td>{u.equipment_id}</td>
                    <td>{u.equipment_type}</td>
                    <td>{agg?.zone_id || u.current_zone_id}</td>
                    <td>{Math.round((u.availability || 0) * 100)}%</td>
                    <td>{Math.round(agg?.output || 0).toLocaleString()} t</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="table-hint">Red row = equipment in the at-risk zone (A1, Phase 8 rainfall spike).</p>
        </Card>

        <Card title="Next 7 Days — Shift Blocks" className="table-card">
          <div className="shift-scroll">
            <table className="schedule-table compact">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Shift</th>
                  <th>Equipment</th>
                  <th>Zone</th>
                  <th>Expected</th>
                </tr>
              </thead>
              <tbody>
                {schedule.entries
                  .filter((e) => new Date(e.date) >= new Date(Date.now() - 86400000))
                  .slice(0, 42)
                  .map((e, i) => (
                    <tr key={i} className={e.zone_id === 'A1' ? 'at-risk-row' : ''}>
                      <td>{e.date}</td>
                      <td>{e.shift}</td>
                      <td>{e.equipment_id}</td>
                      <td>{e.zone_id}</td>
                      <td>{e.expected_output?.toFixed(0)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="cta-row">
        <button className="cta-button" onClick={() => navigate('/recommendations')}>
          View Recommendations →
        </button>
      </div>
    </div>
  )
}
