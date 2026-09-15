import './Card.css'

// Generic surface container — reused across all screens.
export default function Card({ title, children, className = '', onClick, linkTo }) {
  const content = (
    <>
      {title && <h3 className="card-title">{title}</h3>}
      {children}
    </>
  )
  const props = {
    className: `card ${className}${onClick || linkTo ? ' clickable' : ''}`,
  }
  if (linkTo) props.onClick = () => (window.location.hash = linkTo)
  if (onClick) props.onClick = onClick
  return <div {...props}>{content}</div>
}
