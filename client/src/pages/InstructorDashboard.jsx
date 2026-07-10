import { useEffect, useState } from 'react'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend,
} from 'chart.js'
import { api } from '../api/client.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

export default function InstructorDashboard() {
  const [summary, setSummary] = useState(null)
  const [typeStats, setTypeStats] = useState(null)

  useEffect(() => {
    api.get('/dashboard/summary/').then((r) => setSummary(r.data))
    api.get('/questions/stats/').then((r) => setTypeStats(r.data))
  }, [])

  if (!summary) return <div className="loading">Loading dashboard…</div>
  const s = summary.stats

  const cards = [
    { label: 'Courses', value: s.courses, accent: 'blue' },
    { label: 'Students', value: s.students, accent: 'green' },
    { label: 'Questions', value: s.questions, accent: 'purple' },
    { label: 'AI-Generated', value: s.ai_questions, accent: 'amber' },
  ]

  const chartData = typeStats && {
    labels: ['Multiple Choice', 'True / False', 'Short Answer'],
    datasets: [{
      label: 'Questions by type',
      data: [typeStats.by_type.mcq, typeStats.by_type.true_false, typeStats.by_type.short_answer],
      backgroundColor: ['#4f7cff', '#22c55e', '#a855f7'],
      borderRadius: 6,
    }],
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Welcome, {summary.name}</h1>
          <p className="muted">Instructor overview</p>
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

      <div className="panel-row">
        <section className="panel">
          <h2>Question bank composition</h2>
          {chartData
            ? <Bar data={chartData} options={{ plugins: { legend: { display: false } }, responsive: true }} />
            : <p className="muted">No questions yet.</p>}
        </section>

        <section className="panel">
          <h2>Recent courses</h2>
          {summary.recent_courses.length === 0
            ? <p className="muted">You haven’t created any courses yet.</p>
            : (
              <ul className="plain-list">
                {summary.recent_courses.map((c) => (
                  <li key={c.id}><strong>{c.code}</strong> — {c.title}</li>
                ))}
              </ul>
            )}
        </section>
      </div>
    </div>
  )
}
