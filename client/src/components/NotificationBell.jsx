import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, CheckCheck } from 'lucide-react'
import { api } from '../api/client.js'
import { fmtRelative, notifIcon } from '../utils/format.js'

const POLL_MS = 30000

// Unread badge kept fresh by polling (scope doc, Module 9), with a quick-view dropdown.
export default function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const ref = useRef(null)
  const navigate = useNavigate()

  function poll() {
    if (document.hidden) return
    api.get('/notifications/unread_count/').then((r) => setUnread(r.data.unread)).catch(() => {})
  }

  useEffect(() => {
    poll()
    const t = setInterval(poll, POLL_MS)
    const onUpdate = () => poll()
    window.addEventListener('notifications:changed', onUpdate)
    return () => { clearInterval(t); window.removeEventListener('notifications:changed', onUpdate) }
  }, [])

  useEffect(() => {
    if (!open) return undefined
    setItems(null)
    api.get('/notifications/', { params: { page_size: 8 } }).then((r) => setItems(r.data.results ?? r.data))
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  async function openItem(n) {
    if (!n.is_read) {
      await api.post(`/notifications/${n.id}/read/`).catch(() => {})
      setUnread((u) => Math.max(0, u - 1))
    }
    setOpen(false)
    if (n.link) navigate(n.link)
  }

  async function markAll() {
    await api.post('/notifications/mark_all_read/')
    setUnread(0)
    setItems((list) => list?.map((n) => ({ ...n, is_read: true })))
  }

  return (
    <div className="bell" ref={ref}>
      <button className="icon-btn" onClick={() => setOpen(!open)} aria-label={`Notifications (${unread} unread)`}>
        <Bell size={18} />
        {unread > 0 && <span className="badge">{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className="bell-menu">
          <div className="split-row bell-menu-head">
            <strong>Notifications</strong>
            {unread > 0 && <button className="link" onClick={markAll}><CheckCheck size={15} /> Mark all read</button>}
          </div>
          {items === null && <p className="muted small" style={{ padding: '0.6rem' }}>Loading…</p>}
          {items?.length === 0 && <p className="muted small" style={{ padding: '0.6rem' }}>You're all caught up.</p>}
          {items?.map((n) => {
            const Icon = notifIcon(n.type)
            return (
              <button key={n.id} className={`bell-item ${n.is_read ? '' : 'unread'}`} onClick={() => openItem(n)}>
                <span className="bell-dot"><Icon size={16} /></span>
                <span>
                  <div className="bell-title">{n.title}</div>
                  <div className="muted small">{fmtRelative(n.created_at)}</div>
                </span>
              </button>
            )
          })}
          <Link to="/notifications" className="bell-all" onClick={() => setOpen(false)}>View all notifications →</Link>
        </div>
      )}
    </div>
  )
}
