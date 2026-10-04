import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Line } from 'react-chartjs-2'
import { ArrowLeft, Award, BarChart3, ChevronRight, Target, Trophy } from 'lucide-react'
import { api } from '../api/client.js'
import ResultDetail from '../components/ResultDetail.jsx'
import { Alert, EmptyState, PageHeader, SkeletonGrid, SkeletonPanel, StatCard, pctTone } from '../components/ui.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { PALETTE, areaGradient } from '../utils/charts.js'
import { errorText, fmtDateTime } from '../utils/format.js'

export default function StudentResults() {
  const { theme } = useTheme()
  const [params, setParams] = useSearchParams()
  const [results, setResults] = useState(null)
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const examId = params.get('exam')

  useEffect(() => { api.get('/exams/results/').then((r) => setResults(r.data)) }, [])

  useEffect(() => {
    setDetail(null)
    if (!examId) return
    api.get(`/exams/${examId}/result/`)
      .then((r) => setDetail(r.data))
      .catch((err) => setError(errorText(err, 'Could not load that result.')))
  }, [examId])

  if (examId) {
    return (
      <div>
        <PageHeader icon={Award} title={detail?.exam_title || 'Result'} subtitle={detail?.course_code}
                    actions={<button className="btn-ghost" onClick={() => setParams({})}><ArrowLeft size={16} /> All results</button>} />
        {error && <Alert type="error">{error}</Alert>}
        {detail ? <ResultDetail result={detail} /> : !error && <SkeletonPanel lines={8} />}
      </div>
    )
  }

  if (!results) return <><SkeletonGrid count={3} /><SkeletonPanel /></>

  const timeline = [...results].reverse()
  const chart = {
    labels: timeline.map((r) => r.exam_title),
    datasets: [
      { label: 'You', data: timeline.map((r) => r.percentage), borderColor: PALETTE.indigo, backgroundColor: areaGradient(PALETTE.indigo),
        fill: true, tension: 0.35, pointRadius: 4, pointBackgroundColor: PALETTE.indigo },
      { label: 'Class average', data: timeline.map((r) => r.class_average_percentage), borderColor: PALETTE.slate,
        borderDash: [6, 5], tension: 0.35, pointRadius: 0 },
    ],
  }
  const average = results.length ? Math.round(results.reduce((t, r) => t + r.percentage, 0) / results.length * 10) / 10 : null
  const aboveAvg = results.filter((r) => r.class_average_percentage != null && r.percentage >= r.class_average_percentage).length

  return (
    <div>
      <PageHeader icon={Trophy} title="My results" subtitle="Your exam history and how you are progressing." />
      {results.length === 0 ? (
        <section className="panel"><EmptyState icon={Trophy} title="No results yet" text="Complete an exam and your score appears here instantly." /></section>
      ) : (
        <>
          <div className="stat-grid">
            <StatCard icon={Award} label="Exams completed" value={results.length} />
            <StatCard icon={BarChart3} label="Your average" value={`${average}%`} tone="green" />
            <StatCard icon={Trophy} label="Best score" value={`${Math.max(...results.map((r) => r.percentage))}%`} tone="purple" />
            <StatCard icon={Target} label="At or above class average" value={`${aboveAvg}/${results.length}`} tone="amber" />
          </div>

          {results.length > 1 && (
            <section className="panel">
              <h2>Progress over time</h2>
              <div className="chart-box"><Line key={theme} data={chart} options={{
                scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } }, x: { grid: { display: false } } },
                plugins: { legend: { position: 'top', align: 'end' } },
              }} /></div>
            </section>
          )}

          <section className="panel">
            <h2>All results</h2>
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Exam</th><th className="num">Score</th><th className="num">You</th><th className="num">Class avg</th><th>Submitted</th><th /></tr></thead>
                <tbody>
                  {results.map((r) => (
                    <tr key={r.exam_id} style={{ cursor: 'pointer' }} onClick={() => setParams({ exam: String(r.exam_id) })}>
                      <td><strong>{r.exam_title}</strong><div className="muted small">{r.course_code}</div></td>
                      <td className="num">{r.score}/{r.total_marks}</td>
                      <td className="num"><span className={`tag tag-${pctTone(r.percentage)}`}>{r.percentage}%</span></td>
                      <td className="num">{r.class_average_percentage ?? '—'}{r.class_average_percentage != null && '%'}</td>
                      <td className="small">{fmtDateTime(r.submitted_at)}</td>
                      <td><ChevronRight size={16} color="var(--faint)" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
