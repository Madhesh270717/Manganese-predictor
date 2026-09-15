import './Feedback.css'

// Skeleton loader blocks — shown while data fetches (never blank screens).
export function Skeleton({ rows = 3 }) {
  return (
    <div className="skeleton-wrap">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-line" style={{ width: `${90 - i * 15}%` }} />
      ))}
    </div>
  )
}

// Clear error state for API failures (backend unreachable, etc.).
export function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state">
      <span className="error-icon">⚠</span>
      <p>{message}</p>
      {onRetry && (
        <button className="retry-button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}
