import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts'
import { apiGet } from '../services/api.js'
import StatCard from '../components/StatCard.jsx'
import RiskBadge from '../components/RiskBadge.jsx'
import ProgressBar from '../components/ProgressBar.jsx'
import Card from '../components/Card.jsx'
import { Skeleton, ErrorState } from '../components/Feedback.jsx'
import './Production.css'

// Screen 3 — Production dashboard (PRD Section 33).
// Charting library decision: recharts (React-native declarative API, light).
// Reused for the Risk Analysis and Schedule screens in later phases.

export default function Production() {
  const navigate = useNavigate()
  const [zoneId, setZoneId] = useState(null) // null = mine-wide
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const zoneParam = zoneId ? `?zone_id=${zoneId}` : ''
      const [zones, history, target, forecast, shortfall] = await Promise.all([
        apiGet('/api/v1/zones'),
        apiGet(`/api/v1/production/history${zoneParam}`),
        apiGet('/api/v1/production/current-target'),
        apiGet('/api/v1/production/predict/current'),
        apiGet(`/api/v1/production/shortfall/current${zoneParam}`),
      ])
      setState({
        loading: false,
        error: null,
        data: { zones, history, target, forecast, shortfall },
      })
    } catch (err) {
      setState({ loading: false, error: err.message, data: null })
    }
  }, [zoneId])

  useEffect(() => {
    load()
  }, [load])

  const chartData = useMemo(() => {
    if (!state.data) return []
    const { history, forecast } = state.data
    // Aggregate history by date (mine-wide) or use zone-filtered rows.
    const byDate = new Map()
    for (const row of history.records) {
      const key = row.date
      if (!byDate.has(key)) byDate.set(key, { date: key, planned: 0, actual: 0 })
      const agg = byDate.get(key)
      agg.planned += row.planned_production
      agg.actual += row.actual_production
    }
    const series = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))

    // Highlight the current-period prediction as a distinct marker on the
    // last history date.
    if (series.length > 0 && !zoneId) {
      const last = series[series.length - 1]
      last.predicted = Math.round(forecast.predicted_tonnes)
    }
    return series
  }, [state.data, zoneId])

  if (state.loading || !state.data) {
    return (
      <div className="production">
        <h1>Production Dashboard</h1>
        {state.error ? (
          <ErrorState message={`Backend unreachable: ${state.error}`} onRetry={load} />
        ) : (
          <Skeleton rows={6} />
        )}
      </div>
    )
  }

  const { shortfall, forecast, target, zones } = state.data
  const zoneOptions = zones.features.map((f) => f.properties.zone_id).sort()

  // Per-zone breakdown from Phase 16 zone-level shortfall.
  const perZone = zoneOptions.map((zid) => {
    const row = shortfall.zone_id === zid ? shortfall : null
    return row
  }).filter(Boolean)

  return (
    <div className="production">
      <header className="production-header">
        <h1>Production Dashboard</h1>
        <label className="zone-filter">
          Zone:
          <select
            value={zoneId ?? ''}
            onChange={(e) => setZoneId(e.target.value || null)}
          >
            <option value="">Mine-wide</option>
            {zoneOptions.map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
        </label>
      </header>

      {/* Key metrics — PRD Section 33 layout */}
      <div className="stat-grid">
        <StatCard
          label="Target"
          value={`${(zoneId ? shortfall.target : target.planned_total).toLocaleString()} t`}
          linkTo="/production"
        />
        <StatCard
          label="Predicted"
          value={`${(zoneId ? shortfall.predicted : forecast.predicted_tonnes).toLocaleString()} t`}
          tone="warn"
          linkTo="/production"
        />
        <StatCard
          label="Shortfall"
          value={`${Math.abs(shortfall.shortfall_tonnes).toLocaleString()} t`}
          sub={`${shortfall.shortfall_percentage}%`}
          tone={shortfall.shortfall_percentage > 15 ? 'danger' : 'warn'}
          linkTo="/risk-analysis"
        />
        <StatCard label="Risk" value={shortfall.risk_level} tone={shortfall.risk_level === 'HIGH' ? 'danger' : shortfall.risk_level === 'MEDIUM' ? 'warn' : 'good'} />
      </div>

      {/* Risk bar (PRD Section 15 style) */}
      <Card title="Shortfall Risk">
        <ProgressBar
          percentage={shortfall.shortfall_percentage}
          label={`${shortfall.risk_level} (${shortfall.shortfall_percentage}%)`}
        />
      </Card>

      {/* Production trend chart */}
      <Card title="Production Trend — Planned vs Actual" className="chart-card">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="planned" stroke="#2563eb" name="Planned" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="actual" stroke="#16a34a" name="Actual" dot={false} strokeWidth={2} />
            {chartData.some((d) => d.predicted) && (
              <ReferenceDot
                x={chartData[chartData.length - 1].date}
                y={chartData[chartData.length - 1].predicted}
                r={6}
                fill="#dc2626"
                stroke="#fff"
                label={{ value: 'Predicted', position: 'top', fontSize: 11 }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Per-zone breakdown table */}
      <Card title="Per-Zone Breakdown">
        <table className="zone-table">
          <thead>
            <tr>
              <th>Zone</th>
              <th>Target</th>
              <th>Predicted</th>
              <th>Shortfall</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {zoneOptions.map((zid) => {
              const row = perZone.find((r) => r.zone_id === zid)
              if (!row) return null
              return (
                <tr key={zid} className="zone-row" onClick={() => navigate('/reserve-map')}>
                  <td>{zid}</td>
                  <td>{row.target.toLocaleString()}</td>
                  <td>{row.predicted.toLocaleString()}</td>
                  <td>{Math.abs(row.shortfall_tonnes).toLocaleString()}</td>
                  <td><RiskBadge level={row.risk_level} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="table-hint">Click a row to open that zone on the Reserve Map.</p>
      </Card>

      {/* Navigation to Screen 4 */}
      <div className="cta-row">
        <button className="cta-button" onClick={() => navigate('/risk-analysis')}>
          View Risk Breakdown →
        </button>
      </div>
    </div>
  )
}
