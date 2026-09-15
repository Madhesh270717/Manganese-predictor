import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../services/api.js'
import Card from '../components/Card.jsx'
import RiskBadge from '../components/RiskBadge.jsx'
import { Skeleton, ErrorState } from '../components/Feedback.jsx'
import './ReserveMap.css'

// Screen 2 — Reserve Map (PRD Section 32).
// Interactive prospectivity grid: 20 zone cells colored by the Phase 12
// model's statistical prospectivity; click a cell to open the zone detail
// panel (resource estimate P13, drilling P6, geological/geochemical P5).

const PROSPECTIVITY_COLORS = {
  HIGH: 'rgba(22, 163, 74, 0.55)',
  MEDIUM: 'rgba(217, 119, 6, 0.5)',
  LOW: 'rgba(226, 232, 240, 0.6)',
}

function zoneFromId(id) {
  const match = /^([A-D])([1-5])$/.exec(id || '')
  return match ? { row: match[1], col: parseInt(match[2], 10) } : null
}

export default function ReserveMap() {
  const [state, setState] = useState({ loading: true, error: null, data: null })
  const [selected, setSelected] = useState('B3')
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(null)

  useEffect(() => {
    Promise.all([
      apiGet('/api/v1/zones'),
      apiGet('/api/v1/reserve/prospectivity'),
      apiGet('/api/v1/reserve/resource-estimate'),
      apiGet('/api/v1/mineability'),
    ])
      .then(([zones, prospectivity, estimates, mineability]) => {
        setState({ loading: false, error: null, data: { zones, prospectivity, estimates, mineability } })
      })
      .catch((err) => setState({ loading: false, error: err.message, data: null }))
  }, [])

  useEffect(() => {
    if (!selected) return
    setDetailLoading(true)
    setDetailError(null)
    Promise.all([
      apiGet(`/api/v1/reserve/prospectivity/${selected}`),
      apiGet(`/api/v1/reserve/resource-estimate/${selected}`),
      apiGet(`/api/v1/zones/${selected}/drilling`),
      apiGet(`/api/v1/zones/${selected}/geological`),
    ])
      .then(([prospectivity, estimate, drilling, geological]) =>
        setDetail({ prospectivity, estimate, drilling, geological })
      )
      .catch((err) => setDetailError(err.message))
      .finally(() => setDetailLoading(false))
  }, [selected])

  const grid = useMemo(() => {
    const { zones, prospectivity } = state.data || {}
    if (!zones?.features) return []
    const scores = new Map((prospectivity?.zones || []).map((z) => [z.zone_id, z]))
    const cells = zones.features
      .map((f) => {
        const id = f.properties.zone_id
        const pos = zoneFromId(id)
        return { id, ...pos, score: scores.get(id) }
      })
      .filter((c) => c.row)
    // Lay out rows north->south (A top), cols west->east (1 left).
    cells.sort((a, b) => (a.row === b.row ? a.col - b.col : a.row.localeCompare(b.row)))
    return cells
  }, [state.data])

  if (state.loading) {
    return (
      <div className="reserve-map">
        <h1>Reserve Map</h1>
        <Skeleton rows={6} />
      </div>
    )
  }
  if (state.error) {
    return (
      <div className="reserve-map">
        <h1>Reserve Map</h1>
        <ErrorState message={`Backend unreachable: ${state.error}`} onRetry={() => window.location.reload()} />
      </div>
    )
  }

  const { estimates, mineability } = state.data
  const mineabilityByZone = new Map((mineability?.zones || []).map((z) => [z.zone_id, z]))
  const estimateByZone = new Map((estimates?.estimates || []).map((e) => [e.zone_id, e]))
  const selectedCell = grid.find((c) => c.id === selected)

  return (
    <div className="reserve-map">
      <header className="reserve-map-header">
        <h1>Reserve Map</h1>
        <span className="reserve-map-sub">Statistical prospectivity (Phase 12) — NOT a confirmed reserve (PRD Section 8)</span>
      </header>

      <div className="reserve-layout">
        <Card title="Zone Grid — Prospectivity Model" className="map-card">
          <div className="grid-legend">
            <span><i className="legend-swatch high" /> High (≥70%)</span>
            <span><i className="legend-swatch medium" /> Medium (40–70%)</span>
            <span><i className="legend-swatch low" /> Low (&lt;40%)</span>
          </div>
          <div className="zone-grid">
            {grid.map((cell) => {
              const cls = cell.score?.classification || 'LOW'
              const isSel = cell.id === selected
              return (
                <button
                  key={cell.id}
                  className={`zone-cell ${cls.toLowerCase()} ${isSel ? 'selected' : ''}`}
                  style={{ background: PROSPECTIVITY_COLORS[cls] }}
                  onClick={() => setSelected(cell.id)}
                  title={`Zone ${cell.id} — ${cell.score?.prospectivity_score ?? 'n/a'}%`}
                >
                  <span className="zone-cell-id">{cell.id}</span>
                  <span className="zone-cell-score">
                    {cell.score ? `${cell.score.prospectivity_score}%` : '—'}
                  </span>
                </button>
              )
            })}
          </div>
          <p className="map-hint">Click a zone to inspect its resource estimate, drilling, and geology.</p>
        </Card>

        <div className="reserve-detail">
          <Card title={`Zone ${selected} — Detail`}>
            {detailLoading && <Skeleton rows={5} />}
            {detailError && <ErrorState message={detailError} onRetry={() => setSelected(selected)} />}
            {detail && !detailLoading && (
              <>
                <div className="zone-detail-stats">
                  <div className="detail-stat">
                    <span className="detail-stat-label">Prospectivity</span>
                    <span className="detail-stat-value">
                      {detail.prospectivity.prospectivity_score}%
                    </span>
                    <RiskBadge level={detail.prospectivity.classification} />
                  </div>
                  <div className="detail-stat">
                    <span className="detail-stat-label">Mineability</span>
                    <span className="detail-stat-value">
                      {mineabilityByZone.get(selected)?.mineability_score ?? '—'}
                    </span>
                    {mineabilityByZone.get(selected) && (
                      <RiskBadge level={mineabilityByZone.get(selected).classification} />
                    )}
                  </div>
                </div>

                <div className="detail-block">
                  <h4>Resource Estimate (Phase 13)</h4>
                  {estimateByZone.get(selected)?.insufficient_data ? (
                    <p className="detail-warn">⚠ Limited drilling — no statistical estimate (PRD Section 9).</p>
                  ) : (
                    <table className="detail-table">
                      <tbody>
                        <tr><td>Estimated ore</td><td>{(detail.estimate.estimated_tonnage / 1e6).toFixed(2)} Mt</td></tr>
                        <tr><td>Volume</td><td>{(detail.estimate.estimated_volume_m3 / 1e6).toFixed(2)} M m³</td></tr>
                        <tr><td>Avg Mn grade</td><td>{detail.estimate.avg_mn_grade}%</td></tr>
                        <tr><td>Contained Mn</td><td>{(detail.estimate.estimated_contained_mn / 1e6).toFixed(2)} Mt</td></tr>
                        <tr><td>Confidence</td><td><RiskBadge level={detail.estimate.confidence_level} /></td></tr>
                      </tbody>
                    </table>
                  )}
                </div>

                <div className="detail-block">
                  <h4>Drilling (Phase 6)</h4>
                  <p className="detail-text-small">
                    {detail.drilling.density.label} — {detail.drilling.drill_holes.length} holes
                  </p>
                  <ul className="hole-list">
                    {detail.drilling.drill_holes.slice(0, 6).map((h) => (
                      <li key={h.drill_id}>
                        {h.drill_id} · {h.depth.toFixed(0)} m · {h.mn_grade.toFixed(1)}% Mn
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="detail-block">
                  <h4>Geology (Phase 5)</h4>
                  <p className="detail-text-small">
                    {detail.geological.geological.lithology} —{' '}
                    {detail.geological.geological.geological_unit}
                  </p>
                  <p className="detail-text-small">
                    Geochemical Mn: {detail.geological.geochemical?.mn_concentration ?? '—'}%
                  </p>
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
