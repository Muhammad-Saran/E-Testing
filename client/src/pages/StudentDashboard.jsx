import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export default function StudentDashboard() {
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    api.get('/dashboard/summary/').then((r) => setSummary(r.data))
  }, [])

  if (!summary) return <div className="loading">Loading dashboard…</div>
  const s = summary.stats

  const cards = [
    { label: 'Enrolled Courses', value: s.enrolled_courses, accent: 'blue' },
    { label: 'Upcoming Exams', value: s.upcoming_exams, accent: 'amber' },
    { label: 'Completed Exams', value: s.completed_exams, accent: 'green' },
  ]

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Hello, {summary.name}</h1>
          <p className="muted">Student overview</p>
        </div>
      </header>

      <div className="stat-grid">
        {cards.map((c) => (
          <div key={c.label} className={`stat-card ${c.accent}`}>
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
          </div>
        ))}
      </div>

      <section className="panel">
        <h2>My courses</h2>
        {summary.enrolled_courses.length === 0
          ? <p className="muted">You are not enrolled in any courses yet.</p>
          : (
            <div className="course-list">
              {summary.enrolled_courses.map((c) => (
                <div key={c.id} className="course-item">
                  <div className="course-code">{c.code}</div>
                  <div>{c.title}</div>
                </div>
              ))}
            </div>
          )}
      </section>

      <section className="panel">
        <h2>Upcoming examinations</h2>
        <p className="muted">
          You have <strong>{s.upcoming_exams}</strong> exam{s.upcoming_exams === 1 ? '' : 's'} open to take.
          Head to the <strong>Exams</strong> tab to start.
        </p>
      </section>
    </div>
  )
}
