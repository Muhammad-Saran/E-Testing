import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, Doughnut } from 'react-chartjs-2'
import {
  Activity, AlertTriangle, BookOpen, ClipboardList, FileCheck2, Library, PlusCircle, Radio, Sparkles, Users,
} from 'lucide-react'
import { api } from '../api/client.js'
import { Avatar, EmptyState, SkeletonGrid, SkeletonPanel, StatCard, pctTone } from '../components/ui.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { PALETTE, bandColor } from '../utils/charts.js'
import { fmtDateTime, fmtRelative, stateClass } from '../utils/format.js'

const today = () => new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' }

export default function InstructorDashboard() {
  const { theme } = useTheme()
  const [summary, setSummary] = useState(null)
  const [typeStats, setTypeStats] = useState(null)

  useEffect(() => {
    api.get('/dashboard/summary/').then((r) => setSummary(r.data))
    api.get('/questions/stats/').then((r) => setTypeStats(r.data))
  }, [])

  if (!summary) return <><SkeletonGrid count={4} /><SkeletonPanel /></>
  const s = summary.stats
  const graded = summary.recent_exams.filter((e) => e.average_percentage != null).reverse()

  const examChart = {
    labels: graded.map((e) => e.title.length > 22 ? `${e.title.slice(0, 20)}…` : e.title),
    datasets: [{
      label: 'Class average %', data: graded.map((e) => e.average_percentage),
      backgroundColor: graded.map((e) => bandColor(e.average_percentage)), borderRadius: 8, maxBarThickness: 46,
    }],
  }
  const typeChart = typeStats && {
    labels: ['Multiple choice', 'True / False', 'Short answer'],
    datasets: [{
      data: [typeStats.by_type.mcq, typeStats.by_type.true_false, typeStats.by_type.short_answer],
      backgroundColor: [PALETTE.indigo, PALETTE.green, PALETTE.violet], borderWidth: 0, hoverOffset: 6,
    }],
  }

  return (
    <div>
      <section className="hero">
        <div className="hero-row">
          <div>
            <div className="hero-date">{today()}</div>
            <h1 style={{ marginTop: 6 }}>{greeting()}, {summary.name.split(' ')[0]}</h1>
            <p style={{ marginTop: 6 }}>
              {s.active_exams
                ? `${s.active_exams} exam${s.active_exams > 1 ? 's are' : ' is'} live right now.`
                : 'No exams are live right now.'}{' '}
              {s.answers_to_review > 0 && `${s.answers_to_review} short answer${s.answers_to_review > 1 ? 's' : ''} need your review.`}
            </p>
          </div>
          <div className="hero-actions">
            <Link to="/exams" className="btn-glass btn-white"><PlusCircle size={17} /> New exam</Link>
            <Link to="/ai-generate" className="btn-glass"><Sparkles size={17} /> Generate questions</Link>
          </div>
        </div>
      </section>

      <div className="stat-grid">
        <StatCard icon={BookOpen} label="Courses" value={s.courses} to="/courses" />
        <StatCard icon={Users} label="Students" value={s.students} tone="green" to="/courses" />
        <StatCard icon={Library} label="Questions in bank" value={s.questions} tone="purple" to="/questions" />
        <StatCard icon={ClipboardList} label="Exams" value={s.exams} tone="amber" hint={`${s.active_exams} live now`} to="/exams" />
        <StatCard icon={FileCheck2} label="Submissions" value={s.submissions} tone="blue" to="/results" />
        <StatCard icon={AlertTriangle} label="Answers to review" value={s.answers_to_review} tone={s.answers_to_review ? 'red' : 'green'}
                  to="/results?tab=review" hint={s.pending_review ? `${s.pending_review} AI questions to review` : 'All caught up'} />
      </div>

      <div className="panel-row wide-left">
        <section className="panel">
          <div className="head-row"><h2><Activity size={18} /> Class average by exam</h2><Link to="/results" className="small">Analytics →</Link></div>
          {graded.length
            ? <div className="chart-box"><Bar key={theme} data={examChart} options={{
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } }, x: { grid: { display: false } } },
              }} /></div>
            : <EmptyState icon={Activity} title="No results yet" text="Averages appear here once students submit." />}
        </section>
        <section className="panel">
          <h2>Question bank mix</h2>
          {typeStats && typeStats.total > 0
            ? (
              <>
                <div className="chart-box short"><Doughnut key={theme} data={typeChart} options={{ cutout: '68%', plugins: { legend: { position: 'bottom' } } }} /></div>
                <p className="muted small center" style={{ marginTop: 8 }}>{typeStats.total} questions · {typeStats.ai_generated} generated by AI</p>
              </>
            )
            : <EmptyState icon={Library} title="Empty bank" text="Add questions or generate them with AI." action={<Link className="btn-soft btn-sm" to="/ai-generate"><Sparkles size={15} /> Generate</Link>} />}
        </section>
      </div>

      <div className="panel-row wide-left">
        <section className="panel">
          <div className="head-row"><h2><ClipboardList size={18} /> Recent exams</h2><Link to="/exams" className="small">Manage →</Link></div>
          {summary.recent_exams.length === 0
            ? <EmptyState icon={ClipboardList} title="No exams yet" text="Create your first exam from the Exams page." />
            : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead><tr><th>Exam</th><th>Opens</th><th>Status</th><th className="num">Submitted</th><th className="num">Average</th></tr></thead>
                  <tbody>
                    {summary.recent_exams.map((e) => (
                      <tr key={e.id}>
                        <td>
                          {e.state !== 'draft' ? <Link to={`/results?exam=${e.id}`}><strong>{e.title}</strong></Link> : <strong>{e.title}</strong>}
                          <div className="muted small">{e.course_code}</div>
                        </td>
                        <td className="small">{fmtDateTime(e.available_from)}</td>
                        <td>
                          <span className={stateClass(e.state)}>{e.state === 'active' && <Radio size={12} />} {e.state}</span>
                        </td>
                        <td className="num">{e.submitted}</td>
                        <td className="num">
                          {e.average_percentage != null ? <span className={`tag tag-${pctTone(e.average_percentage)}`}>{e.average_percentage}%</span> : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </section>
        <section className="panel">
          <h2>Latest submissions</h2>
          {summary.recent_submissions.length === 0
            ? <p className="muted">No submissions yet.</p>
            : (
              <ul className="plain-list">
                {summary.recent_submissions.map((r, i) => (
                  <li key={i} className="split-row">
                    <span className="cell-user">
                      <Avatar name={r.student_name} />
                      <span>
                        <strong style={{ fontSize: '0.88rem' }}>{r.student_name}</strong>
                        <div className="muted small">{r.exam_title} · {fmtRelative(r.submitted_at)}</div>
                      </span>
                    </span>
                    <span className={`tag tag-${pctTone(r.percentage)}`}>{r.percentage}%</span>
                  </li>
                ))}
              </ul>
            )}
        </section>
      </div>
    </div>
  )
}
