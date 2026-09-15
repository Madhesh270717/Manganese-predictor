import './Placeholder.css'

export default function Placeholder({ name, description }) {
  return (
    <section className="placeholder">
      <h1>{name}</h1>
      <p className="description">{description}</p>
      <p className="hint">Module implementation lands in a later phase.</p>
    </section>
  )
}
