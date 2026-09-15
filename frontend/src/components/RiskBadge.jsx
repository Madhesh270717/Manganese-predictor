import './RiskBadge.css'

const LEVEL_TO_TONE = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  SYNTHETIC: 'medium',
  Recommended: 'low',
  Conditional: 'medium',
  'Avoid-Postpone': 'high',
}

// Colored pill for LOW/MEDIUM/HIGH and the PRD's classification labels.
export default function RiskBadge({ level, className = '' }) {
  const tone = LEVEL_TO_TONE[level] || 'low'
  return <span className={`risk-badge risk-badge-${tone} ${className}`}>{level}</span>
}
