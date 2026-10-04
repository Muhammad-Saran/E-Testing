import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCheck, ExternalLink, Megaphone, Send, Trash2 } from 'lucide-react'
import { api } from '../api/client.js'
import { Alert, EmptyState, PageHeader } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { errorText, fmtDateTime, fmtRelative, notifIcon } from '../utils/format.js'

const PAGE_SIZE = 20
const TYPE_CLASS = {
  exam_published: 'tag', exam_reminder: 'tag tag-amber', result_published: 'tag tag-green', review_needed: 'tag tag-amber',
  answers_released: 'tag tag-green', announcement: 'tag tag-purple', exam_results_ready: 'tag tag-green',
  import_complete: 'tag', ai_generation_complete: 'tag tag-purple', account_activity: 'tag tag-red',
}

// Instructor -> course announcement form (in-app + optional email).
function AnnounceForm() {
  const [courses, setCourses] = useState([])
  const [form, setForm] = useState({ course: '', title: '', message: '', email: true })
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/courses/', { params: { page_size: 100 } }).then((r) => {
      const list = r.data.results ?? r.data
      setCourses(list)
      if (list.length) setForm((f) => ({ ...f, course: String(list[0].id) }))
    })
  }, [])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      const { data } = await api.post('/notifications/announce/', form)
      setMsg({ type: 'ok', text: `Announcement sent to ${data.sent} student${data.sent === 1 ? '' : 's'}.` })
      setForm({ ...form, title: '', message: '' })
    } catch (err) {
      setMsg({ type: 'err', text: errorText(err, 'Could not send the announcement.') })
    } finally {
      setBusy(false)
    }
  }

  if (!courses.length) return null
  return (
    <section className="panel">
      <h2><Megaphone size={18} style={{ verticalAlign: -3, color: 'var(--primary)' }} /> Send an announcement</h2>
      <form className="stack" onSubmit={submit}>
        {msg && <Alert type={msg.type === 'ok' ? 'ok' : 'error'}>{msg.text}</Alert>}
        <div className="grid-2">
          <label>Course
            <select value={form.course} onChange={(e) => setForm({ ...form, course: e.target.value })}>
              {courses.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
            </select>
          </label>
          <label>Title
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={200} required />
          </label>
        </div>
        <label>Message
          <textarea rows={3} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} required />
        </label>
        <div className="split-row">
          <label className="check-row">
            <input type="checkbox" checked={form.email} onChange={(e) => setForm({ ...form, email: e.target.checked })} />
            Also send by email
          </label>
          <button className="btn-primary" disabled={busy}><Send size={16} /> {busy ? 'Sending…' : 'Send to enrolled students'}</button>
        </div>
      </form>
    </section>
  )
}

export default function Notifications() {
  const { user } = useAuth()
  const [data, setData] = useState({ results: [], count: 0 })
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [page, setPage] = useState(1)

  function load(p = page) {
    const params = { page: p, page_size: PAGE_SIZE }
    if (unreadOnly) params.is_read = false
    api.get('/notifications/', { params }).then((r) => setData(r.data))
  }

  useEffect(() => { setPage(1); load(1) }, [unreadOnly]) // eslint-disable-line react-hooks/exhaustive-deps

  const changed = () => window.dispatchEvent(new Event('notifications:changed'))

  async function markRead(n) {
    await api.post(`/notifications/${n.id}/read/`)
    changed()
    load()
  }

  async function markAll() {
    await api.post('/notifications/mark_all_read/')
    changed()
    load()
  }

  async function remove(n) {
    await api.delete(`/notifications/${n.id}/`)
    changed()
    load()
  }

  const pages = Math.max(1, Math.ceil(data.count / PAGE_SIZE))
  const goTo = (p) => { setPage(p); load(p) }

  return (
    <div>
      <PageHeader icon={Bell} title="Notifications"
                  subtitle="Exam schedules, reminders, results and account activity. Important ones are also emailed."
                  actions={<>
                    <label className="check-row">
                      <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} /> Unread only
                    </label>
                    <button className="btn-ghost" onClick={markAll}><CheckCheck size={16} /> Mark all read</button>
                  </>} />

      {user.role === 'instructor' && <AnnounceForm />}

      <section className="panel">
        {data.results.length === 0 ? (
          <EmptyState icon={Bell} title={unreadOnly ? 'All caught up' : 'No notifications yet'} text="New exams, results and announcements will appear here." />
        ) : (
          <ul className="plain-list">
            {data.results.map((n) => (
              <li key={n.id} className={`notif-row ${n.is_read ? '' : 'unread'}`}>
                <div className="notif-icon">{(() => { const Icon = notifIcon(n.type); return <Icon size={18} /> })()}</div>
                <div className="notif-body">
                  <div className="split-row">
                    <strong className="notif-title">{!n.is_read && <span className="unread-dot" style={{ marginRight: 8 }} />}{n.title}</strong>
                    <span className={TYPE_CLASS[n.type] || 'tag'}>{n.type_display}</span>
                  </div>
                  {n.message && <p className="notif-message">{n.message}</p>}
                  <div className="split-row">
                    <span className="muted small" title={fmtDateTime(n.created_at)}>{fmtRelative(n.created_at)}{n.emailed && ' · emailed'}</span>
                    <span className="row-actions notif-actions">
                      {n.link && <Link className="link" to={n.link} onClick={() => !n.is_read && markRead(n)}><ExternalLink size={13} /> Open</Link>}
                      {!n.is_read && <button className="link" onClick={() => markRead(n)}>Mark read</button>}
                      <button className="link danger" onClick={() => remove(n)} aria-label="Delete"><Trash2 size={13} /></button>
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {pages > 1 && (
          <div className="pager">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => goTo(page - 1)}>Previous</button>
            <span className="muted">Page {page} of {pages}</span>
            <button className="btn-ghost" disabled={page >= pages} onClick={() => goTo(page + 1)}>Next</button>
          </div>
        )}
      </section>
    </div>
  )
}
