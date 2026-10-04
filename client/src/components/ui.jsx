import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'

// Shared building blocks of the design system (see index.css).

export function PageHeader({ icon: Icon, title, subtitle, actions }) {
  return (
    <header className="page-head">
      <div className="title-row">
        {Icon && <div className="page-icon"><Icon size={22} /></div>}
        <div>
          <h1>{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="row-actions">{actions}</div>}
    </header>
  )
}

export function StatCard({ icon: Icon, label, value, hint, tone = '', to }) {
  const body = (
    <>
      {Icon && <div className="stat-icon"><Icon size={22} /></div>}
      <div>
        <div className="stat-value">{value ?? '—'}</div>
        <div className="stat-label">{label}</div>
        {hint && <div className="stat-hint">{hint}</div>}
      </div>
    </>
  )
  return to
    ? <Link to={to} className={`stat-card ${tone}`}>{body}</Link>
    : <div className={`stat-card ${tone}`}>{body}</div>
}

export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="empty">
      {Icon && <div className="empty-icon"><Icon size={28} /></div>}
      {title && <h3>{title}</h3>}
      {text && <p>{text}</p>}
      {action}
    </div>
  )
}

const ALERT_ICONS = { error: XCircle, ok: CheckCircle2, warn: AlertTriangle, info: Info }

export function Alert({ type = 'info', children, className = '' }) {
  const Icon = ALERT_ICONS[type]
  return <div className={`alert-${type} ${className}`}><Icon size={18} /><div>{children}</div></div>
}

export function SkeletonGrid({ count = 4 }) {
  return (
    <div className="stat-grid">
      {Array.from({ length: count }, (_, i) => <div key={i} className="skeleton skeleton-card" />)}
    </div>
  )
}

export function SkeletonPanel({ lines = 5 }) {
  return (
    <section className="panel">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton skeleton-line" style={{ width: `${90 - (i % 3) * 18}%` }} />
      ))}
    </section>
  )
}

// Donut showing a percentage, colour-coded by band.
export function ScoreRing({ percent, size = 140, stroke = 12, label, sub }) {
  const p = Math.max(0, Math.min(100, Number(percent) || 0))
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const color = p >= 70 ? 'var(--success)' : p >= 50 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div className="ring-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${p}%`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
                strokeDasharray={c} strokeDashoffset={c * (1 - p / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`}
                style={{ transition: 'stroke-dashoffset .8s ease' }} />
      </svg>
      <div className="ring-label">
        <div className="ring-value" style={{ color }}>{label ?? `${p}%`}</div>
        {sub && <div className="ring-sub">{sub}</div>}
      </div>
    </div>
  )
}

export function Progress({ value, tone = '' }) {
  return <div className={`progress ${tone}`}><span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={active === t.id} className={`tab ${active === t.id ? 'active' : ''}`}
                onClick={() => onChange(t.id)}>
          {t.icon && <t.icon size={16} />}{t.label}
          {t.count != null && <span className="count">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function initials(name = '?') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] || '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

export function Avatar({ name, size }) {
  return <div className={`avatar ${size || ''}`} aria-hidden="true">{initials(name)}</div>
}

export const pctTone = (p) => (p == null ? 'grey' : p >= 70 ? 'green' : p >= 50 ? 'amber' : 'red')
