import {
  AlertTriangle, Bell, CalendarClock, ClipboardCheck, FileUp, KeyRound, Megaphone, Sparkles, Trophy,
} from 'lucide-react'
import { api } from '../api/client.js'

// Flatten a DRF error response into one readable line.
export function errorText(err, fallback = 'Something went wrong.') {
  const d = err?.response?.data
  if (!d) return err?.response ? fallback : 'Cannot reach the server. Check your connection.'
  if (typeof d === 'string') return fallback
  if (d.detail) return d.detail
  return Object.values(d).flat().map((v) => (typeof v === 'object' ? Object.values(v).flat().join(' ') : v)).join(' ') || fallback
}

export const fmtDateTime = (value) =>
  value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—'

export const fmtDate = (value) =>
  value ? new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '—'

export const fmtClock = (s) => {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

// "in 2d 3h", "in 45m" — for countdowns to an exam's start.
export function fmtCountdown(ms) {
  if (ms <= 0) return 'now'
  const mins = Math.floor(ms / 60000)
  const d = Math.floor(mins / 1440)
  const h = Math.floor((mins % 1440) / 60)
  const m = mins % 60
  if (d) return `in ${d}d ${h}h`
  if (h) return `in ${h}h ${m}m`
  return `in ${Math.max(1, m)}m`
}

// "just now", "5 min ago", "3 h ago", "2 days ago", then a date.
export function fmtRelative(value) {
  if (!value) return '—'
  const diff = (Date.now() - new Date(value)) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} day${diff < 172800 ? '' : 's'} ago`
  return fmtDate(value)
}

export const fmtBytes = (n) => {
  if (n == null) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

const STATE_CLASS = { draft: 'tag-grey', scheduled: 'tag-amber', active: 'tag-green', closed: 'tag-grey' }
export const stateClass = (state) => `tag dot cap ${STATE_CLASS[state] ?? ''}`

const NOTIF_ICONS = {
  exam_published: CalendarClock, exam_reminder: CalendarClock, result_published: Trophy,
  answers_released: ClipboardCheck, announcement: Megaphone, exam_results_ready: ClipboardCheck,
  review_needed: AlertTriangle, import_complete: FileUp, ai_generation_complete: Sparkles,
  account_activity: KeyRound,
}
export const notifIcon = (type) => NOTIF_ICONS[type] || Bell

export const SUBMIT_REASON = {
  student: 'Submitted', time: 'Time ran out', violations: 'Too many violations', closed: 'Closed by instructor',
}

// Download a file from an authenticated endpoint (the JWT is sent by axios).
export async function downloadFile(url, filename) {
  const res = await api.get(url, { responseType: 'blob' })
  const href = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(href)
}

export function downloadText(text, filename, type = 'text/csv') {
  const href = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  a.click()
  URL.revokeObjectURL(href)
}
