import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, ArrowLeft, ArrowRight, CalendarClock, CheckCircle2, ClipboardList, Clock, Flag, Hash, LayoutList,
  Maximize, PlayCircle, Send, ShieldAlert, ShieldCheck, Square, Timer, XCircle,
} from 'lucide-react'
import { api } from '../api/client.js'
import ResultDetail from '../components/ResultDetail.jsx'
import { Alert, EmptyState, PageHeader, Progress, SkeletonPanel } from '../components/ui.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { errorText, fmtClock, fmtCountdown, fmtDateTime } from '../utils/format.js'

const AUTOSAVE_MS = 15000
const KEYS = 'ABCDEFGHIJ'

function toPayload(answers) {
  return Object.entries(answers).map(([id, a]) => ({ exam_question_id: Number(id), ...a }))
}
const isAnswered = (a) => Boolean(a && (a.selected_option_id || (a.answer_text || '').trim()))
const sessionStore = {
  get: (id) => { try { return sessionStorage.getItem(`exam-session-${id}`) } catch { return null } },
  set: (id, key) => { try { sessionStorage.setItem(`exam-session-${id}`, key) } catch { /* ignore */ } },
}

// ---------------------------------------------------------------------------
// Exam list
// ---------------------------------------------------------------------------
function ExamCard({ e, now, onStart, onResult }) {
  const opens = new Date(e.available_from) - now
  const closes = new Date(e.available_until) - now
  return (
    <div className="exam-card">
      <div className="split-row" style={{ alignItems: 'flex-start' }}>
        <div>
          <div className="course-code">{e.course_code}</div>
          <h3 style={{ margin: '0.15rem 0 0', fontSize: '1.02rem' }}>{e.title}</h3>
        </div>
        {e.attempted
          ? <span className={`tag ${e.percentage >= 50 ? 'tag-green' : 'tag-red'}`}>{e.percentage}%</span>
          : e.in_progress ? <span className="tag tag-amber dot">In progress</span>
            : e.is_open ? <span className="tag tag-green dot">Open</span>
              : e.state === 'scheduled' ? <span className="tag tag-amber">{fmtCountdown(opens)}</span>
                : <span className="tag tag-grey">Missed</span>}
      </div>
      <div className="exam-meta">
        <span><Hash size={14} /> {e.question_count} questions</span>
        <span><CheckCircle2 size={14} /> {e.total_marks} marks</span>
        <span><Timer size={14} /> {e.duration_minutes} min</span>
      </div>
      <div className="muted small">
        <CalendarClock size={13} style={{ verticalAlign: -2 }} /> {fmtDateTime(e.available_from)} → {fmtDateTime(e.available_until)}
      </div>
      <div className="split-row" style={{ marginTop: 'auto' }}>
        <span className="muted small">
          {e.is_open && !e.attempted && `Closes ${fmtCountdown(closes)}`}
          {e.attempted && `Scored ${e.score}/${e.total_marks}`}
        </span>
        {e.attempted && <button className="btn-soft btn-sm" onClick={() => onResult(e.id)}>View result</button>}
        {!e.attempted && (e.in_progress || e.is_open) && (
          <button className="btn-primary btn-sm" onClick={() => onStart(e)}><PlayCircle size={15} /> {e.in_progress ? 'Resume' : 'Start'}</button>
        )}
      </div>
    </div>
  )
}

function StartDialog({ exam, onCancel, onConfirm }) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{exam.in_progress ? 'Resume' : 'Start'} {exam.title}?</h2>
        <ul className="plain-list">
          <li className="split-row"><span className="muted">Questions</span><strong>{exam.question_count}</strong></li>
          <li className="split-row"><span className="muted">Total marks</span><strong>{exam.total_marks}</strong></li>
          <li className="split-row"><span className="muted">Time limit</span><strong>{exam.duration_minutes} minutes</strong></li>
        </ul>
        <Alert type="info">
          The timer starts when you begin and keeps running if you close the page. Your answers save automatically and the
          exam is submitted when time runs out. Leaving the exam tab is recorded and reported to your instructor.
        </Alert>
        <div className="modal-actions">
          <button className="btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn-primary" onClick={onConfirm}><PlayCircle size={16} /> {exam.in_progress ? 'Resume' : 'Begin exam'}</button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Taking the exam (focus mode)
// ---------------------------------------------------------------------------
function ExamRunner({ examId, onFinished, onExit }) {
  const toast = useToast()
  const [session, setSession] = useState(null)
  const [answers, setAnswers] = useState({})
  const [flags, setFlags] = useState(new Set())
  const [current, setCurrent] = useState(0)
  const [mode, setMode] = useState('single')
  const [remaining, setRemaining] = useState(0)
  const [violations, setViolations] = useState(0)
  const [saveState, setSaveState] = useState('')
  const [lock, setLock] = useState(null) // null | 'fullscreen' | 'replaced'
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState('')

  const answersRef = useRef({})
  const dirtyRef = useRef(false)
  const doneRef = useRef(false)
  const keyRef = useRef(null)
  const lastCopyRef = useRef(0)

  const headers = () => ({ headers: { 'X-Exam-Session': keyRef.current || '' } })

  // The parent re-renders on its own timers; keep its callbacks in refs so
  // they never re-trigger the start effect (which would reset the exam UI).
  const onFinishedRef = useRef(onFinished)
  const onExitRef = useRef(onExit)
  onFinishedRef.current = onFinished
  onExitRef.current = onExit

  const finish = useCallback((result) => {
    doneRef.current = true
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    onFinishedRef.current(result)
  }, [])

  const loadResult = useCallback(async () => {
    try {
      const { data } = await api.get(`/exams/${examId}/result/`)
      finish(data)
    } catch {
      onExitRef.current()
    }
  }, [examId, finish])

  const start = useCallback(async () => {
    setError('')
    try {
      const stored = sessionStore.get(examId)
      const { data } = await api.post(`/exams/${examId}/start/`, {}, { headers: stored ? { 'X-Exam-Session': stored } : {} })
      keyRef.current = data.session_key
      sessionStore.set(examId, data.session_key)
      const restored = {}
      data.answers.forEach((a) => {
        restored[a.exam_question_id] = a.selected_option_id ? { selected_option_id: a.selected_option_id } : { answer_text: a.answer_text }
      })
      answersRef.current = restored
      dirtyRef.current = false
      doneRef.current = false
      setAnswers(restored)
      setSession({ ...data, deadline: Date.now() + data.remaining_seconds * 1000 })
      setRemaining(data.remaining_seconds)
      setViolations(data.violations ?? data.tab_switches)
      setLock(data.exam.require_fullscreen && !document.fullscreenElement ? 'fullscreen' : null)
    } catch (err) {
      if (err.response?.status === 409) return loadResult()
      setError(errorText(err, 'Could not start the exam.'))
    }
    return undefined
  }, [examId, loadResult])

  useEffect(() => { start() }, [start])

  const handleConflict = useCallback((err) => {
    if (err.response?.data?.session_replaced) { setLock('replaced'); return true }
    if (err.response?.status === 409) { loadResult(); return true }
    return false
  }, [loadResult])

  const saveNow = useCallback(async () => {
    if (!session || !dirtyRef.current || doneRef.current) return
    dirtyRef.current = false
    setSaveState('saving')
    try {
      await api.post(`/exams/${examId}/save/`, { answers: toPayload(answersRef.current) }, headers())
      setSaveState('saved')
    } catch (err) {
      if (handleConflict(err)) return
      dirtyRef.current = true
      setSaveState('offline')
    }
  }, [session, examId, handleConflict])

  const submit = useCallback(async (auto = false) => {
    if (doneRef.current || !session) return
    doneRef.current = true
    setConfirming(false)
    try {
      const { data } = await api.post(`/exams/${examId}/submit/`, { answers: toPayload(answersRef.current), auto }, headers())
      finish(data)
    } catch (err) {
      doneRef.current = false
      if (handleConflict(err)) return
      setError(errorText(err, 'Submit failed — check your connection and try again.'))
    }
  }, [session, examId, finish, handleConflict])

  const report = useCallback(async (eventType) => {
    if (doneRef.current || !session) return
    try {
      const { data } = await api.post(`/exams/${examId}/proctor-event/`, { event_type: eventType }, headers())
      setViolations(data.violations)
      if (data.terminated) {
        toast.err('Exam submitted', data.detail)
        loadResult()
      } else if (eventType !== 'copy_paste' && data.limit) {
        toast.err('Violation recorded', `${data.violations} of ${data.limit} allowed before your exam is submitted.`)
      }
    } catch (err) {
      handleConflict(err)
    }
  }, [session, examId, toast, loadResult, handleConflict])

  // Countdown — auto-submit at zero.
  useEffect(() => {
    if (!session) return undefined
    const tick = () => {
      const left = Math.max(0, Math.round((session.deadline - Date.now()) / 1000))
      setRemaining(left)
      if (left <= 0) submit(true)
    }
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [session, submit])

  // Autosave shortly after each change, and periodically as a fallback.
  useEffect(() => {
    if (!session) return undefined
    const t = setInterval(saveNow, AUTOSAVE_MS)
    return () => clearInterval(t)
  }, [session, saveNow])
  useEffect(() => {
    if (!session || !dirtyRef.current) return undefined
    const t = setTimeout(saveNow, 1200)
    return () => clearTimeout(t)
  }, [answers, session, saveNow])

  // Proctoring: tab switches, fullscreen exits, copy/paste attempts.
  useEffect(() => {
    if (!session) return undefined
    const onVisibility = () => { if (document.hidden) report('tab_switch') }
    const onFullscreen = () => {
      if (session.exam.require_fullscreen && !document.fullscreenElement && !doneRef.current) {
        setLock('fullscreen')
        report('fullscreen_exit')
      }
    }
    const onCopy = (e) => {
      e.preventDefault()
      if (Date.now() - lastCopyRef.current > 4000) {
        lastCopyRef.current = Date.now()
        toast.info('Copy and paste are disabled during the exam')
        report('copy_paste')
      }
    }
    const onContext = (e) => e.preventDefault()
    const onBeforeUnload = (e) => { if (!doneRef.current) { e.preventDefault(); e.returnValue = '' } }
    document.addEventListener('visibilitychange', onVisibility)
    document.addEventListener('fullscreenchange', onFullscreen)
    document.addEventListener('copy', onCopy)
    document.addEventListener('cut', onCopy)
    document.addEventListener('paste', onCopy)
    document.addEventListener('contextmenu', onContext)
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      document.removeEventListener('fullscreenchange', onFullscreen)
      document.removeEventListener('copy', onCopy)
      document.removeEventListener('cut', onCopy)
      document.removeEventListener('paste', onCopy)
      document.removeEventListener('contextmenu', onContext)
      window.removeEventListener('beforeunload', onBeforeUnload)
    }
  }, [session, report, toast])

  function setAnswer(qId, value) {
    const next = { ...answersRef.current, [qId]: value }
    answersRef.current = next
    dirtyRef.current = true
    setAnswers(next)
  }

  function toggleFlag(qId) {
    setFlags((f) => { const n = new Set(f); n.has(qId) ? n.delete(qId) : n.add(qId); return n })
  }

  // Keyboard: ←/→ move, 1–9 / A–J pick an option, F flags.
  useEffect(() => {
    if (!session || mode !== 'single') return undefined
    const onKey = (e) => {
      if (lock || confirming || ['TEXTAREA', 'INPUT'].includes(e.target.tagName)) return
      const q = session.questions[current]
      if (e.key === 'ArrowRight') setCurrent((c) => Math.min(session.questions.length - 1, c + 1))
      else if (e.key === 'ArrowLeft') setCurrent((c) => Math.max(0, c - 1))
      else if (e.key.toLowerCase() === 'f') toggleFlag(q.id)
      else if (q.options?.length) {
        const idx = /^[1-9]$/.test(e.key) ? Number(e.key) - 1 : KEYS.indexOf(e.key.toUpperCase())
        if (idx >= 0 && idx < q.options.length) setAnswer(q.id, { selected_option_id: q.options[idx].id })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [session, mode, current, lock, confirming])

  async function enterFullscreen() {
    try { await document.documentElement.requestFullscreen() } catch { /* not allowed */ }
    if (document.fullscreenElement || !session.exam.require_fullscreen) setLock(null)
  }

  if (error && !session) {
    return (
      <div className="exam-shell"><div className="content" style={{ maxWidth: 560 }}>
        <Alert type="error">{error}</Alert>
        <button className="btn-ghost" style={{ marginTop: 12 }} onClick={onExit}><ArrowLeft size={16} /> Back to exams</button>
      </div></div>
    )
  }
  if (!session) return <div className="exam-shell"><div className="loading"><div className="spinner" />Preparing your exam…</div></div>

  const qs = session.questions
  const answered = qs.filter((q) => isAnswered(answers[q.id])).length
  const warn = remaining <= 60
  const limit = session.exam.max_violations

  const renderQuestion = (q, i) => (
    <div key={q.id} className={mode === 'single' ? '' : 'q-card'}>
      <div className="split-row">
        <span className="q-number">Question {i + 1} of {qs.length} · {q.marks} mark{q.marks > 1 ? 's' : ''}</span>
        <button className={`btn-sm ${flags.has(q.id) ? 'btn-soft' : 'btn-ghost'}`} onClick={() => toggleFlag(q.id)}
                style={flags.has(q.id) ? { color: 'var(--warning)', background: 'var(--warning-soft)' } : undefined}>
          <Flag size={14} /> {flags.has(q.id) ? 'Flagged' : 'Flag for review'}
        </button>
      </div>
      <div className="q-title">{q.text}</div>
      {q.question_type === 'short_answer' ? (
        <>
          <textarea rows={5} placeholder="Type your answer…" style={{ width: '100%' }}
                    value={answers[q.id]?.answer_text || ''} onChange={(e) => setAnswer(q.id, { answer_text: e.target.value })} />
          <div className="muted small" style={{ marginTop: 6 }}>Answer in your own words — answers are graded by meaning, not exact wording.</div>
        </>
      ) : (
        q.options.map((o, k) => {
          const chosen = answers[q.id]?.selected_option_id === o.id
          return (
            <label key={o.id} className={`opt-row ${chosen ? 'chosen' : ''}`}>
              <input type="radio" name={`q-${q.id}`} className="sr-only" checked={chosen}
                     onChange={() => setAnswer(q.id, { selected_option_id: o.id })} />
              <span className="opt-key">{KEYS[k]}</span>
              <span>{o.text}</span>
            </label>
          )
        })
      )}
    </div>
  )

  return (
    <div className="exam-shell no-select" style={{ position: 'fixed', inset: 0, zIndex: 90, overflowY: 'auto' }}>
      <div className="exam-bar">
        <div style={{ minWidth: 0 }}>
          <div className="exam-title">{session.exam.title}</div>
          <div className="muted small">
            {session.exam.course_code} · {answered}/{qs.length} answered ·{' '}
            {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'All answers saved' : saveState === 'offline' ? 'Offline — retrying' : 'Autosave on'}
          </div>
        </div>
        <Progress value={(answered / qs.length) * 100} />
        <div className="topbar-spacer" />
        {(violations > 0 || limit) && (
          <span className={`tag ${violations ? 'tag-red' : 'tag-grey'}`} title="Tab switches and fullscreen exits">
            <ShieldAlert size={13} /> {violations}{limit ? ` / ${limit}` : ''} violations
          </span>
        )}
        <div className={`exam-timer ${warn ? 'warn' : ''}`} aria-live="polite"><Clock size={18} /> {fmtClock(remaining)}</div>
        <button className="btn-primary" onClick={() => setConfirming(true)}><Send size={16} /> Submit</button>
      </div>

      <div className="exam-body">
        <div>
          {error && <Alert type="error" className="mb">{error}</Alert>}
          {mode === 'single' ? (
            <div className="exam-question">
              {renderQuestion(qs[current], current)}
              <div className="exam-nav">
                <button className="btn-ghost" disabled={current === 0} onClick={() => setCurrent(current - 1)}><ArrowLeft size={16} /> Previous</button>
                {current < qs.length - 1
                  ? <button className="btn-primary" onClick={() => setCurrent(current + 1)}>Next <ArrowRight size={16} /></button>
                  : <button className="btn-primary" onClick={() => setConfirming(true)}><Send size={16} /> Review & submit</button>}
              </div>
            </div>
          ) : (
            <div className="exam-question">{qs.map(renderQuestion)}</div>
          )}
        </div>

        <aside className="exam-side">
          <section className="panel tight" style={{ marginBottom: 0 }}>
            <div className="split-row" style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: '0.9rem' }}>Questions</strong>
              <div className="segmented">
                <button className={mode === 'single' ? 'active' : ''} onClick={() => setMode('single')} title="One at a time"><Square size={13} /></button>
                <button className={mode === 'all' ? 'active' : ''} onClick={() => setMode('all')} title="All questions"><LayoutList size={13} /></button>
              </div>
            </div>
            <div className="navigator">
              {qs.map((q, i) => (
                <button key={q.id}
                        className={`nav-q ${isAnswered(answers[q.id]) ? 'answered' : ''} ${mode === 'single' && i === current ? 'current' : ''} ${flags.has(q.id) ? 'flagged' : ''}`}
                        onClick={() => { setMode('single'); setCurrent(i) }} aria-label={`Question ${i + 1}`}>
                  {i + 1}
                </button>
              ))}
            </div>
            <div className="legend">
              <span><i className="answered" /> Answered</span>
              <span><i /> Not answered</span>
              <span><i className="flagged" /> Flagged</span>
            </div>
          </section>
          <section className="panel tight" style={{ marginBottom: 0 }}>
            <div className="muted small" style={{ display: 'grid', gap: 6 }}>
              <span><ShieldCheck size={14} style={{ verticalAlign: -2, color: 'var(--success)' }} /> Answers save automatically</span>
              <span>Keys: <span className="kbd">←</span> <span className="kbd">→</span> move · <span className="kbd">A</span>–<span className="kbd">D</span> answer · <span className="kbd">F</span> flag</span>
              {session.exam.require_fullscreen && <span><Maximize size={14} style={{ verticalAlign: -2 }} /> Fullscreen required</span>}
            </div>
          </section>
        </aside>
      </div>

      {confirming && (
        <div className="modal-backdrop" onClick={() => setConfirming(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Submit your exam?</h2>
            <div className="grid-3">
              <div className="stat-card green" style={{ boxShadow: 'none' }}><div><div className="stat-value">{answered}</div><div className="stat-label">Answered</div></div></div>
              <div className="stat-card red" style={{ boxShadow: 'none' }}><div><div className="stat-value">{qs.length - answered}</div><div className="stat-label">Unanswered</div></div></div>
              <div className="stat-card amber" style={{ boxShadow: 'none' }}><div><div className="stat-value">{flags.size}</div><div className="stat-label">Flagged</div></div></div>
            </div>
            {qs.length - answered > 0 && <Alert type="warn">You still have unanswered questions. You cannot change your answers after submitting.</Alert>}
            <div className="modal-actions">
              <button className="btn-ghost" onClick={() => setConfirming(false)}>Keep working</button>
              <button className="btn-primary" onClick={() => submit(false)}><Send size={16} /> Submit now</button>
            </div>
          </div>
        </div>
      )}

      {lock && (
        <div className="lock-overlay">
          <div className="panel" style={{ textAlign: 'center' }}>
            {lock === 'fullscreen' ? (
              <>
                <div className="empty-icon"><Maximize size={28} /></div>
                <h2>Fullscreen is required</h2>
                <p className="muted">This exam must be taken in fullscreen. Leaving fullscreen is recorded as a violation{limit ? ` (${violations}/${limit})` : ''}.</p>
                <button className="btn-primary btn-lg" style={{ marginTop: 12 }} onClick={enterFullscreen}><Maximize size={17} /> Enter fullscreen</button>
              </>
            ) : (
              <>
                <div className="empty-icon" style={{ color: 'var(--danger)' }}><AlertTriangle size={28} /></div>
                <h2>Exam opened elsewhere</h2>
                <p className="muted">This exam was opened in another tab or device, so this window can no longer save answers. This has been reported to your instructor.</p>
                <div className="row-actions" style={{ justifyContent: 'center', marginTop: 12 }}>
                  <button className="btn-ghost" onClick={onExit}>Leave</button>
                  <button className="btn-primary" onClick={() => { setLock(null); sessionStore.set(examId, ''); start() }}>Continue here</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
export default function StudentExams() {
  const [exams, setExams] = useState(null)
  const [taking, setTaking] = useState(null)
  const [confirm, setConfirm] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [now, setNow] = useState(Date.now())

  const loadList = () => api.get('/exams/available/').then((r) => setExams(r.data)).catch((err) => setError(errorText(err)))
  useEffect(() => { loadList() }, [])
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t) }, [])

  async function openResult(examId) {
    try {
      const { data } = await api.get(`/exams/${examId}/result/`)
      setResult(data)
    } catch (err) {
      setError(errorText(err, 'Could not load the result.'))
    }
  }

  if (taking) {
    return (
      <ExamRunner examId={taking}
                  onFinished={(r) => { setTaking(null); setResult(r); loadList() }}
                  onExit={() => { setTaking(null); loadList() }} />
    )
  }

  if (result) {
    return (
      <div>
        <PageHeader icon={ClipboardList} title="Exam result" subtitle={`${result.course_code} · ${result.exam_title}`}
                    actions={<button className="btn-ghost" onClick={() => setResult(null)}><ArrowLeft size={16} /> Back to exams</button>} />
        <ResultDetail result={result} />
      </div>
    )
  }

  const groups = exams && [
    { title: 'Open now', icon: PlayCircle, items: exams.filter((e) => !e.attempted && (e.is_open || e.in_progress)) },
    { title: 'Upcoming', icon: CalendarClock, items: exams.filter((e) => e.state === 'scheduled' && !e.attempted) },
    { title: 'Completed', icon: CheckCircle2, items: exams.filter((e) => e.attempted) },
    { title: 'Missed', icon: XCircle, items: exams.filter((e) => !e.attempted && !e.in_progress && e.state === 'closed') },
  ]

  return (
    <div>
      <PageHeader icon={ClipboardList} title="My exams" subtitle="Exams in your enrolled courses." />
      {error && <Alert type="error" className="mb">{error}</Alert>}
      {!exams && <SkeletonPanel />}
      {exams?.length === 0 && (
        <section className="panel"><EmptyState icon={ClipboardList} title="No exams yet" text="Exams scheduled in your courses will appear here." /></section>
      )}
      {groups?.filter((g) => g.items.length).map((g) => (
        <section key={g.title} style={{ marginBottom: '1.75rem' }}>
          <div className="head-row"><h2><g.icon size={18} /> {g.title} <span className="tag tag-grey">{g.items.length}</span></h2></div>
          <div className="exam-card-grid">
            {g.items.map((e) => <ExamCard key={e.id} e={e} now={now} onStart={setConfirm} onResult={openResult} />)}
          </div>
        </section>
      ))}
      {confirm && (
        <StartDialog exam={confirm} onCancel={() => setConfirm(null)}
                     onConfirm={() => { setTaking(confirm.id); setConfirm(null) }} />
      )}
    </div>
  )
}
