import './StatCard.css'

// Label + big number (+ optional sub-line). Generic: any screen can use it.
export default function StatCard({ label, value, sub, tone = 'neutral', linkTo }) {
  const props = {}
  if (linkTo) props.onClick = () => (window.location.hash = linkTo)
  return (
    <div
      className={`stat-card ${linkTo ? 'clickable' : ''} tone-${tone}`}
      {...props}
    >
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}
