import { useEffect, useState } from 'react'
import { apiGet } from '../services/api.js'
import Card from '../components/Card.jsx'
import { Skeleton, ErrorState } from '../components/Feedback.jsx'
import './Metrics.css'

// Success Metrics — PRD Section 45.
// Real computed values from the Phase 12/13/15 evaluation reports plus the
// Phase 16 shortfall-classification rule and the Phase 20 demo impact.
// Explicitly labeled prototype/demo values, not real-world performance claims.

function MetricRow({ label, value, sub }) {
  return (
    <div className="metric-row">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value ?? '—'}</span>
      {sub && <span className="metric-sub">{sub}</span>}
    </div>
  )
}

function MetricBlock({ title, children, note }) {
  return (
    <Card title={title} className="metric-block">
      {children}
      {note && <p className="metric-note">{note}</p>}
    </Card>
  )
}

export default function Metrics() {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  useEffect(() => {
    apiGet('/api/v1/metrics/summary')
      .then((data) => setState({ loading: false, error: null, data }))
      .catch((err) => setState({ loading: false, error: err.message, data: null }))
  }, [])

  if (state.loading) {
    return (
      <div className="metrics">
        <h1>Success Metrics</h1>
        <Skeleton rows={8} />
      </div>
    )
  }
  if (state.error) {
    return (
      <div className="metrics">
        <h1>Success Metrics</h1>
        <ErrorState message={`Backend unreachable: ${state.error}`} onRetry={() => window.location.reload()} />
      </div>
    )
  }

  const m = state.data
  const res = m.reserve_model || {}
  const prod = m.production_prediction || {}
  const resc = m.resource_estimation || {}
  const sf = m.shortfall_classification || {}
  const sched = m.scheduling_impact || {}

  return (
    <div className="metrics">
      <header className="metrics-header">
        <h1>Success Metrics</h1>
        <span className="metrics-sub">Actual computed values — PRD Section 45</span>
      </header>

      <div className="metrics-disclaimer">{m.disclaimer}</div>

      <div className="metrics-grid">
        <MetricBlock title="Reserve Model (Phase 12)">
          <MetricRow label="Precision" value={res.precision?.toFixed(3)} />
          <MetricRow label="Recall" value={res.recall?.toFixed(3)} />
          <MetricRow label="ROC-AUC" value={res.roc_auc?.toFixed(3)} />
        </MetricBlock>

        <MetricBlock title="Resource Estimation (Phase 13)" note="B3 vs PRD illustrative reference (1.2M m³ / 4.2 Mt)">
          <MetricRow label="Estimated ore" value={`${(resc.estimated_tonnage / 1e6).toFixed(2)} Mt`} />
          <MetricRow label="Volume" value={`${(resc.estimated_volume_m3 / 1e6).toFixed(2)} M m³`} />
          <MetricRow label="Grade" value={`${resc.avg_mn_grade}% Mn`} />
          <MetricRow label="Volume error vs PRD" value={resc.volume_percentage_error != null ? `${resc.volume_percentage_error}%` : null} />
          <MetricRow label="Tonnage error vs PRD" value={resc.tonnage_percentage_error != null ? `${resc.tonnage_percentage_error}%` : null} />
          <MetricRow label="Confidence" value={resc.confidence_level} />
        </MetricBlock>

        <MetricBlock title="Production Prediction (Phase 15)" note={`Held-out ${prod.test_rows} rows, time-aware split`}>
          <MetricRow label="MAE" value={prod.mae != null ? `${prod.mae.toFixed(1)} t/day` : null} />
          <MetricRow label="RMSE" value={prod.rmse != null ? `${prod.rmse.toFixed(1)} t/day` : null} />
          <MetricRow label="MAPE" value={prod.mape != null ? `${prod.mape.toFixed(1)}%` : null} />
        </MetricBlock>

        <MetricBlock title="Shortfall Classification (Phase 16)" note={sf.note}>
          <MetricRow label="Accuracy" value={sf.accuracy?.toFixed(3)} />
          <MetricRow label="Precision" value={sf.precision?.toFixed(3)} />
          <MetricRow label="Recall" value={sf.recall?.toFixed(3)} />
          <MetricRow label="F1" value={sf.f1?.toFixed(3)} />
          <div className="dist-bars">
            {Object.entries(sf.distribution || {}).map(([level, d]) => (
              <div key={level} className="dist-row">
                <span className="dist-label">{level}</span>
                <div className="dist-track">
                  <div className={`dist-fill dist-${level.toLowerCase()}`} style={{ width: `${d.share}%` }} />
                </div>
                <span className="dist-share">{d.share}%</span>
              </div>
            ))}
          </div>
        </MetricBlock>

        <MetricBlock
          title="Scheduling Impact (Phase 20 demo)"
          note={`Recommendation: ${sched.recommendation?.equipment_id} ${sched.recommendation?.from_zone} → ${sched.recommendation?.to_zone}`}
        >
          <MetricRow label="Production before" value={sched.production_before_t != null ? `${sched.production_before_t.toLocaleString()} t` : null} />
          <MetricRow label="Production after" value={sched.production_after_t != null ? `${sched.production_after_t.toLocaleString()} t` : null} />
          <MetricRow label="Recovered" value={sched.production_recovered_t != null ? `${sched.production_recovered_t.toLocaleString()} t` : null} />
          <MetricRow label="Shortfall reduction" value={sched.shortfall_reduction_pct != null ? `${sched.shortfall_reduction_pct}%` : null} />
        </MetricBlock>
      </div>
    </div>
  )
}
