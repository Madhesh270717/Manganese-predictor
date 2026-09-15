import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../services/api.js'
import StatCard from '../components/StatCard.jsx'
import RiskBadge from '../components/RiskBadge.jsx'
import ProgressBar from '../components/ProgressBar.jsx'
import DataConfidence from '../components/DataConfidence.jsx'
import Card from '../components/Card.jsx'
import { Skeleton, ErrorState } from '../components/Feedback.jsx'
import './Overview.css'

// Screen 1 — Overview dashboard (PRD Section 31).
// Live data from: prospectivity (P12), production forecast (P15),
// shortfall risk (P16), equipment (P9).
export default function Overview() {
  const navigate = useNavigate()
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(async () => {
    setState({ loading: true, error: null, data: null })
    try {
      const [prospectivity, forecast, shortfall, equipment] = await Promise.all([
        apiGet('/api/v1/reserve/prospectivity'),
        apiGet('/api/v1/production/predict/current'),
        apiGet('/api/v1/production/shortfall/current'),
        apiGet('/api/v1/equipment'),
      ])
      setState({ loading: false, error: null, data: { prospectivity, forecast, shortfall, equipment } })
    } catch (err) {
      setState({ loading: false, error: err.message, data: null })
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (state.loading) {
    return (
      <div className="overview">
        <h1>SPOTTER AI</h1>
        <div className="stat-grid">
          {[0, 1, 2, 3].map((i) => (
            <div className="stat-skeleton" key={i}>
              <Skeleton rows={2} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (state.error) {
    return (
      <div className="overview">
        <h1>SPOTTER AI</h1>
        <ErrorState
          message={`Backend unreachable: ${state.error}. Start the API server and retry.`}
          onRetry={load}
        />
      </div>
    )
  }

  const { prospectivity, forecast, shortfall, equipment } = state.data

  // Aggregate best-zone prospectivity.
  const bestZone = prospectivity.zones[0]
  const avgAvailability =
    equipment.equipment.reduce((sum, u) => sum + (u.availability ?? 0), 0) /
    (equipment.equipment.length || 1)

  return (
    <div className="overview">
      <header className="overview-header">
        <h1>SPOTTER AI</h1>
        <span className="mine-name">MOIL Balaghat — illustrative AOI</span>
      </header>

      <div className="stat-grid">
        <StatCard
          label="Reserve Prospectivity"
          value={`${bestZone.prospectivity_score}%`}
          sub={`Best zone ${bestZone.zone_id} · ${bestZone.classification}`}
          tone={bestZone.classification === 'HIGH' ? 'good' : 'warn'}
          linkTo="/reserve-map"
        />
        <StatCard
          label="Production Forecast"
          value={`${(forecast.predicted_tonnes / 1000).toFixed(1)} KT`}
          sub={`Target ${(forecast.target_tonnes / 1000).toFixed(1)} KT`}
          linkTo="/production"
        />
        <StatCard
          label="Shortfall Risk"
          value={shortfall.risk_level}
          sub={`${shortfall.shortfall_tonnes.toLocaleString()} t (${shortfall.shortfall_percentage}%)`}
          tone={shortfall.risk_level === 'HIGH' ? 'danger' : shortfall.risk_level === 'MEDIUM' ? 'warn' : 'good'}
          linkTo="/risk-analysis"
        />
        <StatCard
          label="Equipment Availability"
          value={`${Math.round(avgAvailability * 100)}%`}
          sub={`${equipment.count} units`}
          tone={avgAvailability > 0.8 ? 'good' : avgAvailability > 0.6 ? 'warn' : 'danger'}
          linkTo="/schedule"
        />
      </div>

      <div className="overview-lower">
        <Card title="Shortfall Risk Detail">
          <ProgressBar
            percentage={shortfall.shortfall_percentage}
            label={`${shortfall.risk_level}`}
          />
          <p className="detail-text">
            Target {shortfall.target.toLocaleString()} t · Predicted{' '}
            {shortfall.predicted.toLocaleString()} t
          </p>
          <button className="link-button" onClick={() => navigate('/risk-analysis')}>
            View risk analysis →
          </button>
        </Card>

        <DataConfidence />
      </div>
    </div>
  )
}
