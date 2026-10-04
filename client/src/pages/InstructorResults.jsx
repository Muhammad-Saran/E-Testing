import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Bar, Line } from 'react-chartjs-2'
import {
  AlertTriangle, BarChart3, CheckCircle2, ClipboardCheck, Download, FileSpreadsheet, GraduationCap, ListOrdered,
  Printer, Search, ShieldAlert, Target, TrendingUp, Trophy, Users,
} from 'lucide-react'
import { api } from '../api/client.js'
import StudentTimeline from '../components/StudentTimeline.jsx'
import { Alert, Avatar, EmptyState, PageHeader, SkeletonGrid, SkeletonPanel, StatCard, Tabs, pctTone } from '../components/ui.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { PALETTE, areaGradient, bandColor } from '../utils/charts.js'
import { SUBMIT_REASON, downloadFile, errorText, fmtDate, fmtDateTime, stateClass } from '../utils/format.js'

const difficultyLabel = (acc) => (acc == null ? '—' : acc >= 70 ? 'Easy' : acc >= 40 ? 'Moderate' : 'Hard')
const discTone = (d) => (d == null ? 'grey' : d >= 0.3 ? 'green' : d >= 0.2 ? 'amber' : 'red')

// ---------------------------------------------------------------------------
function ReviewQueue({ examId, onChanged }) {
  const toast = useToast()
  const [all, setAll] = useState(false)
  const [items, setItems] = useState(null)
  const [draft, setDraft] = useState({})

  const load = () => api.get(`/exams/${examId}/reviews/`, { params: all ? { all: 1 } : {} }).then((r) => setItems(r.data))
  useEffect(() => { setItems(null); load() }, [examId, all]) // eslint-disable-line react-hooks/exhaustive-deps

  async function save(item) {
    const d = draft[item.answer_id] || {}
    try {
      const { data } = await api.post(`/exams/${examId}/review/`, {
        answer_id: item.answer_id, awarded_marks: d.marks ?? item.awarded_marks, note: d.note || '',
      })
      toast.ok('Marks saved', `${item.student_name}: ${data.awarded_marks}/${item.marks}. Score now ${data.attempt_score}.`)
      load()
      onChanged()
    } catch (err) {
      toast.err('Could not save', errorText(err))
    }
  }

  return (
    <section className="panel">
      <div className="head-row">
        <h2><ClipboardCheck size={18} /> Short-answer review</h2>
        <div className="segmented">
          <button className={!all ? 'active' : ''} onClick={() => setAll(false)}>Flagged</button>
          <button className={all ? 'active' : ''} onClick={() => setAll(true)}>All short answers</button>
        </div>
      </div>
      <p className="muted small" style={{ marginTop: -6 }}>
        Answers are flagged when their similarity to the reference is borderline, or when they sound right but miss a required keyword.
        Confirm the automatic mark or change it — every change is recorded in the audit log and the student is notified.
      </p>
      {!items && <div className="loading"><div className="spinner" /></div>}
      {items?.length === 0 && <EmptyState icon={CheckCircle2} title="Nothing to review" text={all ? 'No short answers in this exam.' : 'No answers are flagged. The automatic marks stand.'} />}
      {items?.map((item) => {
        const d = draft[item.answer_id] || {}
        const marks = d.marks ?? item.awarded_marks
        return (
          <div key={item.answer_id} className={`review-card ${item.needs_review ? 'flagged' : ''}`}>
            <div className="split-row">
              <div className="cell-user"><Avatar name={item.student_name} />
                <span><strong>{item.student_name}</strong><div className="muted small">{item.student_email}</div></span>
              </div>
              <div className="row-actions">
                {item.similarity != null && <span className={`tag tag-${pctTone(item.similarity)}`}>{item.similarity}% similar</span>}
                {item.needs_review && <span className="tag tag-amber"><AlertTriangle size={12} /> flagged</span>}
                {item.reviewed && <span className="tag tag-purple">reviewed{item.original_marks != null && ` (was ${item.original_marks})`}</span>}
              </div>
            </div>
            <div style={{ fontWeight: 600, margin: '0.7rem 0 0' }}>{item.question}</div>
            <div className="review-grid">
              <div className="quote"><div className="label">Student answer</div>{item.answer_text || <em className="muted">No answer</em>}</div>
              <div className="quote"><div className="label">Reference answer</div>{item.reference_answer}
                {item.required_keywords && <div className="muted small" style={{ marginTop: 6 }}>Required keywords: {item.required_keywords.replace(/\s*\|\s*/g, ' or ')}</div>}
              </div>
            </div>
            {item.missing_keywords.length > 0 && (
              <div className="feedback-line small" style={{ marginBottom: 8 }}>Missing: {item.missing_keywords.map((k) => <span key={k} className="tag tag-red">{k}</span>)}</div>
            )}
            <div className="split-row" style={{ flexWrap: 'wrap' }}>
              <div className="row-actions">
                <span className="muted small">Marks</span>
                <div className="marks-picker">
                  {Array.from({ length: item.marks + 1 }, (_, m) => (
                    <button key={m} type="button" className={marks === m ? 'active' : ''}
                            onClick={() => setDraft({ ...draft, [item.answer_id]: { ...d, marks: m } })}>{m}</button>
                  ))}
                </div>
              </div>
              <div className="row-actions" style={{ flex: 1, justifyContent: 'flex-end' }}>
                <input placeholder="Note to the student (optional)" style={{ flex: 1, minWidth: 180, maxWidth: 360 }}
                       value={d.note ?? item.review_note ?? ''} onChange={(e) => setDraft({ ...draft, [item.answer_id]: { ...d, note: e.target.value } })} />
                <button className="btn-primary btn-sm" onClick={() => save(item)}>{marks === item.awarded_marks ? 'Confirm' : 'Save marks'}</button>
              </div>
            </div>
          </div>
        )
      })}
    </section>
  )
}

// ---------------------------------------------------------------------------
function CourseTrend({ courseId, onStudent }) {
  const { theme } = useTheme()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    setData(null)
    setError('')
    api.get('/exams/course_analytics/', { params: { course: courseId } }).then((r) => setData(r.data)).catch((e) => setError(errorText(e)))
  }, [courseId])
  if (error) return <Alert type="info">{error}</Alert>
  if (!data) return <SkeletonPanel />
  const t = data.timeline
  const chart = {
    labels: t.map((e) => e.title),
    datasets: [
      { label: 'Average %', data: t.map((e) => e.average_percentage), borderColor: PALETTE.indigo, backgroundColor: areaGradient(PALETTE.indigo), fill: true, tension: 0.35, pointRadius: 4 },
      { label: 'Highest %', data: t.map((e) => e.highest_percentage), borderColor: PALETTE.green, borderDash: [4, 4], tension: 0.35, pointRadius: 0 },
      { label: 'Lowest %', data: t.map((e) => e.lowest_percentage), borderColor: PALETTE.red, borderDash: [4, 4], tension: 0.35, pointRadius: 0 },
    ],
  }
  return (
    <>
      <div className="stat-grid">
        <StatCard icon={ListOrdered} label="Exams held" value={data.summary.exams} />
        <StatCard icon={Users} label="Students enrolled" value={data.summary.enrolled} tone="green" />
        <StatCard icon={Target} label="Course average" value={data.summary.average_percentage != null ? `${data.summary.average_percentage}%` : '—'} tone="purple" />
        <StatCard icon={TrendingUp} label="Participation" value={data.summary.participation != null ? `${data.summary.participation}%` : '—'} tone="amber" />
      </div>
      <section className="panel">
        <h2><TrendingUp size={18} /> {data.course.code} — performance across exams</h2>
        <div className="chart-box tall"><Line key={theme} data={chart} options={{ scales: { y: { beginAtZero: true, max: 100 } }, plugins: { legend: { position: 'top', align: 'end' } } }} /></div>
      </section>
      <div className="panel-row">
        <section className="panel">
          <h2><Trophy size={18} /> Top students</h2>
          <ul className="plain-list">
            {data.top_students.map((s, i) => (
              <li key={s.id} className="split-row" style={{ cursor: 'pointer' }} onClick={() => onStudent(s.id)}>
                <span className="cell-user"><strong style={{ width: 18 }}>{i + 1}</strong><Avatar name={s.full_name} />
                  <span><strong style={{ fontSize: '0.88rem' }}>{s.full_name}</strong><div className="muted small">{s.exams_taken} exams</div></span></span>
                <span className="tag tag-green">{s.average_percentage}%</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="panel">
          <h2><AlertTriangle size={18} /> Students at risk <span className="muted small">(average below 50%)</span></h2>
          {data.at_risk.length === 0 ? <EmptyState icon={CheckCircle2} title="No one at risk" text="Every student averages 50% or more." /> : (
            <ul className="plain-list">
              {data.at_risk.map((s) => (
                <li key={s.id} className="split-row" style={{ cursor: 'pointer' }} onClick={() => onStudent(s.id)}>
                  <span className="cell-user"><Avatar name={s.full_name} />
                    <span><strong style={{ fontSize: '0.88rem' }}>{s.full_name}</strong><div className="muted small">{s.email}</div></span></span>
                  <span className="tag tag-red">{s.average_percentage}%</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
export default function InstructorResults() {
  const { theme } = useTheme()
  const [params, setParams] = useSearchParams()
  const [exams, setExams] = useState(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [timelineFor, setTimelineFor] = useState(null)
  const [filter, setFilter] = useState('')
  const examId = params.get('exam')
  const tab = params.get('tab') || 'overview'
  const setTab = (t) => setParams({ ...(examId ? { exam: examId } : {}), tab: t })

  useEffect(() => {
    api.get('/exams/', { params: { page_size: 100 } }).then((r) => {
      const list = (r.data.results ?? r.data).filter((e) => e.status !== 'draft')
      setExams(list)
      if (!examId && list.length) setParams({ exam: String(list[0].id), tab }, { replace: true })
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const loadAnalytics = () => {
    if (!examId) return
    api.get(`/exams/${examId}/analytics/`).then((r) => setData(r.data)).catch((err) => setError(errorText(err, 'Could not load results.')))
  }
  useEffect(() => { setData(null); setError(''); loadAnalytics() }, [examId]) // eslint-disable-line react-hooks/exhaustive-deps

  const exam = exams?.find((e) => String(e.id) === String(examId))
  const s = data?.summary
  const results = useMemo(() => (data?.results || []).filter((r) =>
    `${r.student_name} ${r.email} ${r.registration_number}`.toLowerCase().includes(filter.toLowerCase())), [data, filter])

  async function exportCsv() {
    try {
      await downloadFile(`/exams/${examId}/export/`, `${data.exam.title.replace(/[^\w-]+/g, '_')}-results.csv`)
    } catch (err) {
      setError(errorText(err, 'Export failed.'))
    }
  }

  if (exams && exams.length === 0) {
    return (
      <div>
        <PageHeader icon={BarChart3} title="Results & analytics" />
        <section className="panel"><EmptyState icon={BarChart3} title="No published exams" text="Publish an exam to see its results and analytics here." /></section>
      </div>
    )
  }

  const distribution = data && {
    labels: data.distribution.labels,
    datasets: [{ label: 'Students', data: data.distribution.counts, borderRadius: 8, maxBarThickness: 42,
      backgroundColor: data.distribution.counts.map((_, i) => bandColor(i * 10 + 5)) }],
  }
  const perQuestion = data && {
    labels: data.questions.map((q) => `Q${q.number}`),
    datasets: [{ label: '% correct', data: data.questions.map((q) => q.accuracy ?? 0), borderRadius: 8, maxBarThickness: 36,
      backgroundColor: data.questions.map((q) => bandColor(q.accuracy ?? 0)) }],
  }

  return (
    <div>
      <PageHeader icon={BarChart3} title="Results & analytics" subtitle={exam ? `${exam.course_code} · ${exam.title}` : 'Performance for each published exam.'}
                  actions={<div className="row-actions no-print">
                    <select value={examId || ''} onChange={(e) => setParams({ exam: e.target.value, tab })} disabled={!exams}>
                      {exams?.map((e) => <option key={e.id} value={e.id}>{e.course_code} — {e.title}</option>)}
                    </select>
                    {data && <button className="btn-ghost" onClick={() => window.print()}><Printer size={16} /> Print / PDF</button>}
                    {data && <button className="btn-primary" onClick={exportCsv} disabled={!data.results.length}><FileSpreadsheet size={16} /> Export CSV</button>}
                  </div>} />

      <div className="print-only" style={{ marginBottom: 16 }}>
        <h2>e-Testing — Result report</h2>
        <p>{exam?.course_code} · {exam?.title} · generated {fmtDateTime(new Date())}</p>
      </div>

      {error && <Alert type="error" className="mb">{error}</Alert>}
      {(!exams || (examId && !data && !error)) && <><SkeletonGrid /><SkeletonPanel /></>}

      {data && (
        <>
          <div className="no-print">
            <Tabs active={tab} onChange={setTab} tabs={[
              { id: 'overview', label: 'Overview', icon: BarChart3 },
              { id: 'items', label: 'Item analysis', icon: ListOrdered, count: data.questions.length },
              { id: 'students', label: 'Students', icon: Users, count: data.results.length },
              { id: 'review', label: 'Review', icon: ClipboardCheck, count: data.pending_reviews || undefined },
              { id: 'course', label: 'Course trend', icon: TrendingUp },
            ]} />
          </div>

          {(tab === 'overview') && (
            <>
              <p className="muted" style={{ marginTop: -8 }}>
                <span className={stateClass(data.exam.state)}>{data.exam.state}</span>{' '}
                {fmtDateTime(data.exam.available_from)} → {fmtDateTime(data.exam.available_until)} · {s.total_marks} marks per student
              </p>
              <div className="stat-grid">
                <StatCard icon={Users} label="Submitted / enrolled" value={`${s.submitted}/${s.enrolled}`} hint={s.in_progress ? `${s.in_progress} writing now` : undefined} />
                <StatCard icon={Target} label="Class average" value={s.average_percentage != null ? `${s.average_percentage}%` : '—'} tone="purple"
                          hint={s.median_percentage != null ? `Median ${s.median_percentage}%` : undefined} />
                <StatCard icon={CheckCircle2} label="Pass rate (≥ 50%)" value={s.pass_rate != null ? `${s.pass_rate}%` : '—'} tone="green" />
                <StatCard icon={Trophy} label="Highest / lowest" value={s.highest != null ? `${s.highest} / ${s.lowest}` : '—'} tone="amber" hint={`out of ${s.total_marks}`} />
                {data.pending_reviews > 0 && <StatCard icon={ClipboardCheck} label="Answers to review" value={data.pending_reviews} tone="red" />}
              </div>
              {data.results.length === 0
                ? <section className="panel"><EmptyState icon={GraduationCap} title="No submissions yet" text={s.in_progress ? `${s.in_progress} student(s) are writing now.` : 'Results appear here as students submit.'} /></section>
                : (
                  <div className="panel-row">
                    <section className="panel">
                      <h2>Score distribution</h2>
                      <div className="chart-box"><Bar key={theme} data={distribution} options={{
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } },
                      }} /></div>
                    </section>
                    <section className="panel">
                      <h2>Difficulty index (% answered correctly)</h2>
                      <div className="chart-box"><Bar key={theme} data={perQuestion} options={{
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, max: 100 }, x: { grid: { display: false } } },
                      }} /></div>
                    </section>
                  </div>
                )}
            </>
          )}

          {tab === 'items' && (
            <section className="panel">
              <h2><ListOrdered size={18} /> Item analysis</h2>
              <p className="muted small" style={{ marginTop: -6 }}>
                <strong>Difficulty</strong> = share of students who answered correctly. <strong>Discrimination</strong> = accuracy of the top 27 % of the class minus
                the bottom 27 % (≥ 0.4 excellent, 0.3 good, 0.2 fair, below 0.2 the question needs revising). <strong>Distractors</strong> show how often each option was picked.
              </p>
              {data.questions.map((q) => {
                const total = q.options.reduce((t, o) => t + o.count, 0) || 1
                return (
                  <div key={q.exam_question_id} className="q-card">
                    <div className="q-head">
                      <span>Q{q.number} · {q.question_type.replace('_', ' ')} · {q.marks} mark{q.marks > 1 ? 's' : ''} · answered by {q.attempted_by}</span>
                      <span className="row-actions" style={{ gap: 6 }}>
                        <span className={`tag tag-${pctTone(q.accuracy)}`}>{q.accuracy ?? '—'}% · {difficultyLabel(q.accuracy)}</span>
                        <span className={`tag tag-${discTone(q.discrimination)}`} title="Discrimination index">D = {q.discrimination ?? '—'} · {q.discrimination_label}</span>
                        {q.needs_review > 0 && <span className="tag tag-amber">{q.needs_review} to review</span>}
                      </span>
                    </div>
                    <div className="q-title" style={{ fontSize: '0.95rem' }}>{q.text}</div>
                    {q.options.map((o) => (
                      <div key={o.id ?? 'none'} className="meter-row">
                        <span style={{ color: o.is_correct ? 'var(--success)' : o.id == null ? 'var(--faint)' : undefined, fontWeight: o.is_correct ? 650 : 400 }}>
                          {o.is_correct && '✓ '}{o.text}
                        </span>
                        <div className={`progress ${o.is_correct ? 'green' : o.id == null ? '' : 'red'}`}><span style={{ width: `${(o.count / total) * 100}%`, opacity: o.id == null ? 0.4 : 1 }} /></div>
                        <span className="muted small tabular">{o.count} ({Math.round((o.count / total) * 100)}%)</span>
                      </div>
                    ))}
                  </div>
                )
              })}
            </section>
          )}

          {tab === 'students' && (
            <section className="panel">
              <div className="head-row">
                <h2><Users size={18} /> Student results</h2>
                <div className="input-icon no-print" style={{ maxWidth: 300, flex: 1 }}><Search size={16} />
                  <input placeholder="Filter by name, email or reg #" value={filter} onChange={(e) => setFilter(e.target.value)} />
                </div>
              </div>
              {data.results.length === 0 ? <EmptyState icon={Users} title="No submissions yet" /> : (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead><tr><th>#</th><th>Student</th><th>Reg #</th><th className="num">Score</th><th className="num">%</th><th>Submitted</th><th className="num">Violations</th></tr></thead>
                    <tbody>
                      {results.map((r, i) => (
                        <tr key={r.attempt_id} style={{ cursor: 'pointer' }} onClick={() => setTimelineFor(r.student_id)} title="Open performance timeline">
                          <td className="muted">{i + 1}</td>
                          <td><div className="cell-user"><Avatar name={r.student_name} />
                            <span><strong style={{ fontSize: '0.88rem' }}>{r.student_name}</strong><div className="muted small">{r.email}</div></span></div></td>
                          <td className="small">{r.registration_number || '—'}</td>
                          <td className="num">{r.score}/{s.total_marks}</td>
                          <td className="num"><span className={`tag tag-${pctTone(r.percentage)}`}>{r.percentage}%</span></td>
                          <td className="small">{fmtDate(r.submitted_at)}{r.submit_reason && r.submit_reason !== 'student' && <div className="muted">{SUBMIT_REASON[r.submit_reason]}</div>}</td>
                          <td className="num">{r.tab_switches > 0 ? <span className="tag tag-red"><ShieldAlert size={12} /> {r.tab_switches}</span> : '0'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="muted small no-print" style={{ marginTop: 10 }}><Download size={13} style={{ verticalAlign: -2 }} /> Click a student for their performance timeline across all your exams.</p>
            </section>
          )}

          {tab === 'review' && <ReviewQueue examId={examId} onChanged={loadAnalytics} />}
          {tab === 'course' && exam && <CourseTrend courseId={exam.course} onStudent={setTimelineFor} />}
        </>
      )}

      {timelineFor && <StudentTimeline studentId={timelineFor} onClose={() => setTimelineFor(null)} />}
    </div>
  )
}
