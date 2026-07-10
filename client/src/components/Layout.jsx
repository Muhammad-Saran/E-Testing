import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function Layout() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const isInstructor = user?.role === 'instructor'

  const links = isInstructor
    ? [
        { to: '/instructor', label: 'Dashboard' },
        { to: '/courses', label: 'Courses' },
        { to: '/exams', label: 'Exams' },
      ]
    : [
        { to: '/student', label: 'Dashboard' },
        { to: '/exams', label: 'Exams' },
      ]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">e-Testing</div>
        <nav>
          {links.map((l) => (
            <Link key={l.to} to={l.to} className={pathname === l.to ? 'active' : ''}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-badge">
            <div className="avatar">{(user?.full_name || user?.email || '?')[0].toUpperCase()}</div>
            <div>
              <div className="user-name">{user?.full_name}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
          <button className="btn-ghost" onClick={logout}>Log out</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
