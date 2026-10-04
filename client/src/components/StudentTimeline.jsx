import { useEffect, useState } from 'react'
import { Line } from 'react-chartjs-2'
import { X } from 'lucide-react'
import { api } from '../api/client.js'
import { PALETTE, areaGradient } from '../utils/charts.js'
import { errorText, fmtDateTime } from '../utils/format.js'

// One student's results across the instructor's exams (scope doc, Module 8).
export default function StudentTimeline({ studentId, onClose }) {
  const [course, setCourse] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    api.get('/exams/student_timeline/', { params: { student: studentId, ...(course ? { course } : {}) } })
      .then((r) => setData(r.data))
      .catch((err) => setError(errorText(err, 'Could not load the timeline.')))
  }, [studentId, course])

  const s = data?.summary
  const chart = data && {
    labels: data.timeline.map((p) => `${p.course_code} · ${p.exam_title}`),
    datasets: [
      { label: 'Student %', data: data.timeline.map((p) => p.percentage), borderColor: PALETTE.indigo,
        backgroundColor: areaGradient(PALETTE.indigo), fill: true, tension: 0.35, pointRadius: 4 },
      { label: 'Class average %', data: data.timeline.map((p) => p.class_average_percentage), borderColor: PALETTE.slate,
        borderDash: [6, 4], tension: 0.35, pointRadius: 0 },
    ],
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="split-row">
          <h2 style={{ margin: 0 }}>{data ? data.student.full_name : 'Student timeline'}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={17} /></button>
        </div>
        {error && <div className="alert-error">{error}</div>}
        {!data && !error && <div className="loading">Loading…</div>}
        {data && (
          <>
            <div className="split-row">
              <span className="muted">{data.student.email}{data.student.registration_number && ` · ${data.student.registration_number}`}</span>
              {data.courses.length > 1 && (
                <select value={course} onChange={(e) => setCourse(e.target.value)}>
                  <option value="">All my courses</option>
                  {data.courses.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
                </select>
              )}
            </div>
            <div className="stat-grid">
              <div className="stat-card blue"><div className="stat-value">{s.exams_taken}</div><div className="stat-label">Exams taken</div></div>
              <div className="stat-card green"><div className="stat-value">{s.average_percentage ?? '—'}{s.average_percentage != null && '%'}</div><div className="stat-label">Average</div></div>
              <div className="stat-card purple"><div className="stat-value">{s.best_percentage ?? '—'}{s.best_percentage != null && '%'}</div><div className="stat-label">Best</div></div>
              <div className="stat-card amber">
                <div className="stat-value">{s.trend == null ? '—' : `${s.trend > 0 ? '+' : ''}${s.trend}`}</div>
                <div className="stat-label">Trend (first → latest, % points)</div>
              </div>
            </div>
            {data.timeline.length === 0 ? <p className="muted">No submitted exams yet.</p> : (
              <>
                <div className="chart-box"><Line data={chart} options={{ scales: { y: { beginAtZero: true, max: 100 } } }} /></div>
                <table className="data-table">
                  <thead><tr><th>Exam</th><th>Submitted</th><th>Score</th><th>%</th><th>Class avg</th><th>Tab switches</th></tr></thead>
                  <tbody>
                    {data.timeline.map((p) => (
                      <tr key={p.exam_id}>
                        <td>{p.exam_title}<div className="muted small">{p.course_code}</div></td>
                        <td>{fmtDateTime(p.submitted_at)}{p.auto_submitted && <div className="muted small">auto-submitted</div>}</td>
                        <td>{p.score}/{p.total_marks}</td>
                        <td>{p.percentage}%</td>
                        <td>{p.class_average_percentage ?? '—'}{p.class_average_percentage != null && '%'}</td>
                        <td>{p.tab_switches}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
