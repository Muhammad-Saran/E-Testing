import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Line } from 'react-chartjs-2'
import {
  Award, BookOpen, CalendarClock, CheckCircle2, ClipboardList, FlaskConical, Megaphone, PlayCircle, TrendingUp,
} from 'lucide-react'
import { api } from '../api/client.js'
import { EmptyState, SkeletonGrid, SkeletonPanel, StatCard, pctTone } from '../components/ui.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { PALETTE, areaGradient } from '../utils/charts.js'
import { fmtCountdown, fmtDate, fmtDateTime, fmtRelative, stateClass } from '../utils/format.js'

function Countdown({ target }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [])
  const ms = Math.max(0, new Date(target) - now)
  const parts = [
    ['days', Math.floor(ms / 86400000)], ['hrs', Math.floor((ms % 86400000) / 3600000)],
    ['min', Math.floor((ms % 3600000) / 60000)], ['sec', Math.floor((ms % 60000) / 1000)],
  ]
  return (
    <div className="hero-countdown" aria-label="Time until the exam opens">
      {parts.map(([label, value]) => <div key={label}><strong>{String(value).padStart(2, '0')}</strong><span>{label}</span></div>)}
    </div>
  )
}

export default function StudentDashboard() {
  const { theme } = useTheme()
  const [summary, setSummary] = useState(null)

  useEffect(() => { api.get('/dashboard/summary/').then((r) => setSummary(r.data)) }, [])

  if (!summary) return <><SkeletonGrid count={4} /><SkeletonPanel /></>
  const s = summary.stats
  const live = summary.upcoming_exams.find((e) => e.state === 'active')
  const next = summary.upcoming_exams.find((e) => e.state === 'scheduled')
  const history = [...summary.recent_results].reverse()
  const trend = {
    labels: history.map((r) => fmtDate(r.submitted_at)),
    datasets: [{
      label: 'Your score %', data: history.map((r) => r.percentage), borderColor: PALETTE.indigo,
      backgroundColor: areaGradient(PALETTE.indigo), fill: true, tension: 0.35, pointRadius: 4, pointBackgroundColor: PALETTE.indigo,
    }],
  }

  return (
    <div>
      <section className="hero">
        <div className="hero-row">
          <div>
            <div className="hero-date">{new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}</div>
            <h1 style={{ marginTop: 6 }}>Hello, {summary.name.split(' ')[0]} 👋</h1>
            <p style={{ marginTop: 6 }}>
              {live ? <>Your exam <strong>{live.title}</strong> is open now.</>
                : next ? <>Next up: <strong>{next.title}</strong> ({next.course_code}) on {fmtDateTime(next.available_from)}.</>
                  : 'No exams scheduled right now — a good time to practise.'}
            </p>
            <div className="hero-actions" style={{ marginTop: 14 }}>
              {live
                ? <Link to="/exams" className="btn-glass btn-white"><PlayCircle size={17} /> {live.in_progress ? 'Resume exam' : 'Start exam'}</Link>
                : <Link to="/practice" className="btn-glass btn-white"><FlaskConical size={17} /> Practise with AI</Link>}
              <Link to="/results" className="btn-glass"><Award size={17} /> My results</Link>
            </div>
          </div>
          {!live && next && <Countdown target={next.available_from} />}
        </div>
      </section>

      <div className="stat-grid">
        <StatCard icon={BookOpen} label="Enrolled courses" value={s.enrolled_courses} to="/materials" />
        <StatCard icon={CalendarClock} label="Upcoming exams" value={s.upcoming_exams} tone="amber" to="/exams" />
        <StatCard icon={CheckCircle2} label="Exams completed" value={s.completed_exams} tone="green" to="/results" />
        <StatCard icon={TrendingUp} label="Average score" value={s.average_percentage != null ? `${s.average_percentage}%` : '—'}
                  tone="purple" hint={s.best_percentage != null ? `Best: ${s.best_percentage}%` : undefined} to="/results" />
      </div>

      <div className="panel-row wide-left">
        <section className="panel">
          <div className="head-row"><h2><TrendingUp size={18} /> Your progress</h2><Link to="/results" className="small">All results →</Link></div>
          {history.length >= 2
            ? <div className="chart-box"><Line key={theme} data={trend} options={{
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } }, x: { grid: { display: false } } },
              }} /></div>
            : <EmptyState icon={TrendingUp} title="Your trend appears here" text="After two exams you will see how your scores change over time." />}
        </section>
        <section className="panel">
          <div className="head-row"><h2><ClipboardList size={18} /> Upcoming</h2><Link to="/exams" className="small">All exams →</Link></div>
          {summary.upcoming_exams.length === 0
            ? <EmptyState icon={CalendarClock} title="Nothing scheduled" text="New exams will show up here." />
            : (
              <ul className="plain-list">
                {summary.upcoming_exams.map((e) => (
                  <li key={e.id} className="split-row">
                    <span>
                      <strong>{e.title}</strong>
                      <div className="muted small">
                        {e.course_code} · {e.state === 'scheduled'
                          ? `opens ${fmtCountdown(new Date(e.available_from) - Date.now())}`
                          : `closes ${fmtCountdown(new Date(e.available_until) - Date.now())}`} · {e.duration_minutes} min
                      </div>
                    </span>
                    {e.state === 'active'
                      ? <Link className="btn-primary btn-sm" to="/exams">{e.in_progress ? 'Resume' : 'Start'}</Link>
                      : <span className={stateClass(e.state)}>{e.state}</span>}
                  </li>
                ))}
              </ul>
            )}
        </section>
      </div>

      <div className="panel-row">
        <section className="panel">
          <div className="head-row"><h2><Award size={18} /> Recent results</h2></div>
          {summary.recent_results.length === 0
            ? <p className="muted">No results yet.</p>
            : (
              <ul className="plain-list">
                {summary.recent_results.slice(0, 5).map((r) => (
                  <li key={r.exam_id} className="split-row">
                    <span>
                      <Link to={`/results?exam=${r.exam_id}`}><strong>{r.exam_title}</strong></Link>
                      <div className="muted small">{r.course_code} · {fmtRelative(r.submitted_at)}</div>
                    </span>
                    <span className={`tag tag-${pctTone(r.percentage)}`}>{r.score}/{r.total_marks} · {r.percentage}%</span>
                  </li>
                ))}
              </ul>
            )}
        </section>
        <section className="panel">
          <div className="head-row"><h2><Megaphone size={18} /> Announcements</h2><Link to="/notifications" className="small">Inbox →</Link></div>
          {!summary.announcements?.length
            ? <p className="muted">No announcements from your instructors.</p>
            : (
              <ul className="plain-list">
                {summary.announcements.map((a) => (
                  <li key={a.id}>
                    <div className="split-row"><strong>{a.title}</strong>{!a.is_read && <span className="tag tag-amber">new</span>}</div>
                    <p className="notif-message">{a.message}</p>
                    <div className="muted small">{fmtRelative(a.created_at)}</div>
                  </li>
                ))}
              </ul>
            )}
        </section>
      </div>

      <section className="panel">
        <div className="head-row"><h2><BookOpen size={18} /> My courses</h2><Link to="/materials" className="small">Course material →</Link></div>
        {summary.enrolled_courses.length === 0
          ? <EmptyState icon={BookOpen} title="Not enrolled yet" text="Ask your instructor to add you to a course." />
          : (
            <div className="course-list">
              {summary.enrolled_courses.map((c) => (
                <Link key={c.id} to="/materials" className="course-item">
                  <span className="course-code">{c.code}</span>
                  <span style={{ color: 'var(--text)', fontWeight: 600 }}>{c.title}</span>
                </Link>
              ))}
            </div>
          )}
      </section>
    </div>
  )
}
