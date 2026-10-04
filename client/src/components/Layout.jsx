import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3, Bell, BookOpen, ClipboardList, FileText, FlaskConical, GraduationCap, LayoutDashboard,
  Library, LogOut, Menu, Moon, Sparkles, Sun, Trophy, UserRound,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import NotificationBell from './NotificationBell.jsx'
import { Avatar } from './ui.jsx'

const INSTRUCTOR_NAV = [
  { label: 'Overview', items: [{ to: '/instructor', label: 'Dashboard', icon: LayoutDashboard }] },
  {
    label: 'Teaching',
    items: [
      { to: '/courses', label: 'Courses & Students', icon: BookOpen },
      { to: '/questions', label: 'Question Bank', icon: Library },
      { to: '/ai-generate', label: 'AI Generator', icon: Sparkles },
    ],
  },
  {
    label: 'Assessment',
    items: [
      { to: '/exams', label: 'Exams', icon: ClipboardList },
      { to: '/results', label: 'Results & Analytics', icon: BarChart3 },
    ],
  },
  { label: 'Inbox', items: [{ to: '/notifications', label: 'Notifications', icon: Bell }] },
]

const STUDENT_NAV = [
  { label: 'Overview', items: [{ to: '/student', label: 'Dashboard', icon: LayoutDashboard }] },
  {
    label: 'Learning',
    items: [
      { to: '/exams', label: 'My Exams', icon: ClipboardList },
      { to: '/results', label: 'My Results', icon: Trophy },
      { to: '/practice', label: 'AI Practice', icon: FlaskConical },
      { to: '/materials', label: 'Course Material', icon: FileText },
    ],
  },
  { label: 'Inbox', items: [{ to: '/notifications', label: 'Notifications', icon: Bell }] },
]

const TITLES = {
  '/instructor': 'Dashboard', '/student': 'Dashboard', '/courses': 'Courses & Students', '/questions': 'Question Bank',
  '/ai-generate': 'AI Question Generator', '/exams': 'Exams', '/results': 'Results & Analytics',
  '/notifications': 'Notifications', '/materials': 'Course Material', '/practice': 'AI Practice',
  '/profile': 'My Profile',
}

function UserMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()
  useEffect(() => {
    if (!open) return undefined
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  return (
    <div className="menu" ref={ref}>
      <button className="icon-btn" style={{ borderRadius: '50%', padding: 0, border: 'none' }} onClick={() => setOpen(!open)}
              aria-label="Account menu">
        <Avatar name={user.full_name || user.email} />
      </button>
      {open && (
        <div className="menu-panel">
          <div className="menu-head">
            <Avatar name={user.full_name || user.email} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 650 }}>{user.full_name}</div>
              <div className="muted small" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</div>
            </div>
          </div>
          <button className="menu-item" onClick={() => { setOpen(false); navigate('/profile') }}>
            <UserRound size={16} /> My profile
          </button>
          <button className="menu-item danger" onClick={onLogout}><LogOut size={16} /> Log out</button>
        </div>
      )}
    </div>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const { pathname } = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  const isInstructor = user?.role === 'instructor'
  const sections = isInstructor ? INSTRUCTOR_NAV : STUDENT_NAV

  useEffect(() => { setNavOpen(false) }, [pathname])

  return (
    <div className={`app-shell ${navOpen ? 'nav-open' : ''}`}>
      <aside className="sidebar">
        <Link to="/" className="brand">
          <div className="brand-mark"><GraduationCap size={21} /></div>
          <div>
            <div className="brand-name">e-Testing</div>
            <div className="brand-sub">COMSATS Abbottabad</div>
          </div>
        </Link>
        <nav aria-label="Main">
          {sections.map((section) => (
            <div key={section.label} className="nav-section">
              <div className="nav-label">{section.label}</div>
              {section.items.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                  <Icon size={18} /> {label}
                </NavLink>
              ))}
            </div>
          ))}
          <div style={{ flex: 1 }} />
          <div className="sidebar-card">
            {isInstructor
              ? <><strong>Generate with AI</strong>Turn lecture notes into reviewed questions in seconds.
                  <div style={{ marginTop: 8 }}><Link to="/ai-generate" style={{ color: '#c7d2fe', fontWeight: 600 }}>Open generator →</Link></div></>
              : <><strong>Practice with AI</strong>Make a self-test from your course material. It never counts.
                  <div style={{ marginTop: 8 }}><Link to="/practice" style={{ color: '#c7d2fe', fontWeight: 600 }}>Start practising →</Link></div></>}
          </div>
        </nav>
        <div className="sidebar-footer">
          <div className="user-badge">
            <Avatar name={user?.full_name || user?.email} />
            <div style={{ minWidth: 0 }}>
              <div className="user-name">{user?.full_name}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
        </div>
      </aside>
      <div className="backdrop-mobile" onClick={() => setNavOpen(false)} />

      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-toggle" onClick={() => setNavOpen(true)} aria-label="Open menu"><Menu size={18} /></button>
          <div className="topbar-title">
            <span className="crumb">{isInstructor ? 'Instructor' : 'Student'}</span>
            <span className="crumb">/</span>
            {TITLES[pathname] || 'e-Testing'}
          </div>
          <div className="topbar-spacer" />
          <button className="icon-btn" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                  title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <NotificationBell />
          <UserMenu user={user} onLogout={logout} />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
