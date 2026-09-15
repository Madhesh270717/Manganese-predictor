import { NavLink, Outlet } from 'react-router-dom'
import './Layout.css'

const links = [
  { to: '/overview', label: 'Overview' },
  { to: '/reserve-map', label: 'Reserve Map' },
  { to: '/production', label: 'Production' },
  { to: '/risk-analysis', label: 'Risk Analysis' },
  { to: '/schedule', label: 'Schedule' },
  { to: '/recommendations', label: 'Recommendations' },
  { to: '/assistant', label: 'Assistant' },
  { to: '/metrics', label: 'Metrics' },
]

export default function Layout() {
  return (
    <div className="layout">
      <header className="topbar">
        <span className="brand">Spotter AI</span>
        <nav className="nav">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
