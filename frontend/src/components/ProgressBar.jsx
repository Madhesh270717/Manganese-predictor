import './ProgressBar.css'

// Block-style progress bar matching PRD Section 15:
// "████████████████░░░░ MEDIUM"
export default function ProgressBar({ percentage, blocks = 20, maxPct = 15, label }) {
  const filled = Math.min(blocks, Math.round((percentage / maxPct) * blocks))
  const tone = percentage < 5 ? 'low' : percentage <= 15 ? 'medium' : 'high'
  const segments = Array.from({ length: blocks }, (_, i) => (
    <span key={i} className={`bar-block ${i < filled ? `filled-${tone}` : 'empty'}`} />
  ))
  return (
    <div className="progress-bar" title={`${percentage}% shortfall`}>
      <div className="bar-blocks">{segments}</div>
      {label && <span className={`bar-label tone-text-${tone}`}>{label}</span>}
    </div>
  )
}
