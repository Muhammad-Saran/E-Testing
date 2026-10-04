import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart3, CalendarClock, ClipboardList, Copy, Library, Lock, Maximize, Pencil, Plus, Send, Shuffle, Square,
  Timer, Trash2, Undo2,
} from 'lucide-react'
import { api } from '../api/client.js'
import QuestionFormModal, { DIFFICULTIES, TYPES } from '../components/QuestionFormModal.jsx'
import { Alert, EmptyState, PageHeader } from '../components/ui.jsx'
import { errorText, fmtDateTime, stateClass } from '../utils/format.js'

const pad = (n) => String(n).padStart(2, '0')
// <input type="datetime-local"> works in local time without a zone…
const toLocalInput = (d) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
// …so convert to a full ISO timestamp (with zone) before sending it to the API.
const toIso = (local) => new Date(local).toISOString()
const plusHours = (h) => { const d = new Date(); d.setMinutes(0, 0, 0); d.setHours(d.getHours() + h); return toLocalInput(d) }

const BLANK_EXAM = () => ({
  course: '', title: '', description: '', available_from: plusHours(1), available_until: plusHours(25),
  duration_minutes: 20, shuffle_questions: true, shuffle_options: true, questions_per_student: '',
  require_fullscreen: false, max_violations: '',
})

const examToForm = (e) => ({
  course: e.course, title: e.title, description: e.description || '',
  available_from: toLocalInput(new Date(e.available_from)),
  available_until: toLocalInput(new Date(e.available_until)),
  duration_minutes: e.duration_minutes, shuffle_questions: e.shuffle_questions, shuffle_options: e.shuffle_options,
  questions_per_student: e.questions_per_student ?? '', require_fullscreen: e.require_fullscreen,
  max_violations: e.max_violations ?? '',
})
const numOrNull = (v) => (v === '' || v == null ? null : Number(v))

function BankPicker({ exam, existing, onAdded, onClose }) {
  const [tab, setTab] = useState('pick') // 'pick' | 'random'
  const [list, setList] = useState([])
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [chosen, setChosen] = useState([])
  const [random, setRandom] = useState({ question_type: 'mcq', difficulty: '', count: 5 })
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/exams/bank_summary/').then((r) => setSummary(r.data))
  }, [])

  useEffect(() => {
    const t = setTimeout(() => {
      const params = { page_size: 100, is_active: true }
      if (search) params.search = search
      if (type) params.question_type = type
      api.get('/questions/', { params }).then((r) => setList(r.data.results ?? r.data))
    }, 250)
    return () => clearTimeout(t)
  }, [search, type])

  const available = list.filter((q) => !existing.has(q.id))
  const toggle = (id) => setChosen(chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id])

  async function addChosen() {
    setError('')
    try {
      const { data } = await api.post(`/exams/${exam.id}/add_from_bank/`, { question_ids: chosen })
      onAdded(`${data.added} question${data.added === 1 ? '' : 's'} added from the bank.`)
    } catch (err) { setError(errorText(err)) }
  }

  async function addRandom(e) {
    e.preventDefault()
    setError('')
    try {
      const { data } = await api.post(`/exams/${exam.id}/compose/`, { ...random, count: Number(random.count) })
      onAdded(data.short_by
        ? `Added ${data.added} of ${data.requested} — the bank did not have enough matching questions.`
        : `${data.added} random question${data.added === 1 ? '' : 's'} added.`)
    } catch (err) { setError(errorText(err)) }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <h2>Add questions from the bank</h2>
        <div className="role-toggle">
          <button type="button" className={tab === 'pick' ? 'active' : ''} onClick={() => setTab('pick')}>Pick questions</button>
          <button type="button" className={tab === 'random' ? 'active' : ''} onClick={() => setTab('random')}>Random selection</button>
        </div>
        {error && <div className="alert-error">{error}</div>}

        {tab === 'pick' ? (
          <>
            <div className="toolbar" style={{ marginBottom: 0 }}>
              <input className="search" placeholder="Search…" value={search} onChange={(e) => setSearch(e.target.value)} />
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="">All types</option>
                {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="pick-list">
              {available.length === 0
                ? <p className="muted">No more bank questions to add. <Link to="/questions">Open the question bank</Link> to create some.</p>
                : available.map((q) => (
                  <label key={q.id} className={`pick-row ${chosen.includes(q.id) ? 'chosen' : ''}`}>
                    <input type="checkbox" checked={chosen.includes(q.id)} onChange={() => toggle(q.id)} />
                    <span className="pick-text">{q.text}</span>
                    <span className="tag">{q.type_display}</span>
                    <span className="muted small">{q.marks}m</span>
                  </label>
                ))}
            </div>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn-primary" disabled={chosen.length === 0} onClick={addChosen}>
                Add {chosen.length || ''} selected
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={addRandom} className="stack">
            <p className="muted" style={{ margin: 0 }}>
              Draw questions at random from your bank.
              {summary && ` Available: ${summary.mcq} MCQ · ${summary.true_false} True/False · ${summary.short_answer} short answer.`}
            </p>
            <div className="grid-3">
              <label>Type
                <select value={random.question_type} onChange={(e) => setRandom({ ...random, question_type: e.target.value })}>
                  {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              <label>Difficulty
                <select value={random.difficulty} onChange={(e) => setRandom({ ...random, difficulty: e.target.value })}>
                  <option value="">Any</option>
                  {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <label>How many
                <input type="number" min="1" value={random.count} onChange={(e) => setRandom({ ...random, count: e.target.value })} />
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn-primary" type="submit">Add random questions</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

export default function InstructorExams() {
  const [exams, setExams] = useState([])
  const [courses, setCourses] = useState([])
  const [selected, setSelected] = useState(null)
  const [examQuestions, setExamQuestions] = useState([])
  const [examModal, setExamModal] = useState(null) // null | 'new' | 'edit'
  const [examForm, setExamForm] = useState(BLANK_EXAM())
  const [examError, setExamError] = useState('')
  const [showNewQ, setShowNewQ] = useState(false)
  const [showBank, setShowBank] = useState(false)
  const [msg, setMsg] = useState(null)

  function loadExams(selectId) {
    api.get('/exams/', { params: { page_size: 100 } }).then((r) => {
      const list = r.data.results ?? r.data
      setExams(list)
      const id = selectId ?? selected?.id
      const pick = id ? list.find((e) => e.id === id) : list[0]
      if (pick) select(pick, false)
      else setSelected(null)
    })
  }
  useEffect(() => {
    loadExams()
    api.get('/courses/', { params: { page_size: 100 } }).then((r) => setCourses(r.data.results ?? r.data))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function select(exam, clearMsg = true) {
    setSelected(exam)
    if (clearMsg) setMsg(null)
    api.get(`/exams/${exam.id}/questions/`).then((r) => setExamQuestions(r.data))
  }
  function refresh(id = selected.id) {
    api.get(`/exams/${id}/`).then((r) => { setSelected(r.data); setExams((p) => p.map((e) => (e.id === id ? r.data : e))) })
    api.get(`/exams/${id}/questions/`).then((r) => setExamQuestions(r.data))
  }

  function openNewExam() { setExamForm(BLANK_EXAM()); setExamError(''); setExamModal('new') }
  function openEditExam() { setExamForm(examToForm(selected)); setExamError(''); setExamModal('edit') }

  async function saveExam(e) {
    e.preventDefault()
    setExamError('')
    const payload = {
      ...examForm,
      duration_minutes: Number(examForm.duration_minutes),
      questions_per_student: numOrNull(examForm.questions_per_student),
      max_violations: numOrNull(examForm.max_violations),
      available_from: toIso(examForm.available_from),
      available_until: toIso(examForm.available_until),
    }
    try {
      if (examModal === 'new') {
        const { data } = await api.post('/exams/', payload)
        setExamModal(null)
        loadExams(data.id)
        setMsg({ type: 'ok', text: 'Exam created. Now add its questions.' })
      } else {
        await api.patch(`/exams/${selected.id}/`, payload)
        setExamModal(null)
        refresh()
        setMsg({ type: 'ok', text: 'Exam updated.' })
      }
    } catch (err) {
      setExamError(errorText(err, 'Could not save the exam.'))
    }
  }

  async function deleteExam() {
    if (!confirm(`Delete "${selected.title}"? This cannot be undone.`)) return
    try {
      await api.delete(`/exams/${selected.id}/`)
      setSelected(null)
      setExamQuestions([])
      loadExams(null)
    } catch (err) {
      setMsg({ type: 'err', text: errorText(err) })
    }
  }

  async function addNewQuestion(payload) {
    await api.post(`/exams/${selected.id}/add_question/`, payload)
    setShowNewQ(false)
    refresh()
    setMsg({ type: 'ok', text: 'Question created, saved to your bank and added to the exam.' })
  }

  async function removeQuestion(eqId) {
    try {
      await api.post(`/exams/${selected.id}/remove_question/`, { exam_question_id: eqId })
      refresh()
    } catch (err) {
      setMsg({ type: 'err', text: errorText(err) })
    }
  }

  async function lifecycle(action, confirmText) {
    if (confirmText && !confirm(confirmText)) return
    try {
      const { data } = await api.post(`/exams/${selected.id}/${action}/`, {})
      setSelected(data)
      setExams((p) => p.map((e) => (e.id === data.id ? data : e)))
      const text = {
        publish: data.state === 'active' ? 'Exam published and open to students now.' : 'Exam published and scheduled.',
        unpublish: 'Exam moved back to draft.',
        close: 'Exam closed. Open attempts were submitted and results are final.',
      }[action]
      setMsg({ type: 'ok', text })
    } catch (err) {
      setMsg({ type: 'err', text: errorText(err, 'Action failed.') })
    }
  }

  const setE = (k) => (e) => setExamForm({ ...examForm, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const isDraft = selected?.status === 'draft'
  const isPublished = selected?.status === 'published'
  const hasAttempts = (selected?.submission_count ?? 0) > 0

  return (
    <div>
      <PageHeader icon={ClipboardList} title="Exams" subtitle="Schedule an exam, add its questions, then publish it to your students."
                  actions={<button className="btn-primary" onClick={openNewExam} disabled={courses.length === 0}><Plus size={17} /> New exam</button>} />
      {courses.length === 0 && (
        <Alert type="warn" className="mb">Create a course first — exams belong to a course. <Link to="/courses">Go to Courses</Link></Alert>
      )}

      <div className="panel-row" style={{ gridTemplateColumns: '1fr 1.6fr', alignItems: 'start' }}>
        <section className="panel">
          <h2>My exams <span className="tag tag-grey">{exams.length}</span></h2>
          {exams.length === 0 ? <EmptyState icon={ClipboardList} title="No exams yet" text="Create your first exam to get started." /> : (
            <ul className="plain-list">
              {exams.map((e) => (
                <li key={e.id} className={`select-row ${selected?.id === e.id ? 'selected' : ''}`} onClick={() => select(e)}>
                  <span>
                    <strong>{e.title}</strong><br />
                    <span className="muted">{e.course_code} · {e.uses_pool ? `${e.question_count} of ${e.pool_size}` : e.question_count} Q · {e.duration_minutes} min</span><br />
                    <span className="muted small">{fmtDateTime(e.available_from)}</span>
                  </span>
                  <span className={stateClass(e.state)}>{e.state}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          {!selected ? <EmptyState icon={ClipboardList} title="No exam selected" text="Select an exam on the left, or create a new one." /> : (
            <>
              <div className="head-row">
                <div>
                  <h2 style={{ marginBottom: 4 }}>{selected.title} <span className={stateClass(selected.state)}>{selected.state}</span></h2>
                  <p className="muted" style={{ margin: 0 }}>
                    {selected.course_code} · {selected.total_marks} marks per student
                  </p>
                  <div className="exam-meta" style={{ margin: '8px 0 4px' }}>
                    <span><CalendarClock size={14} /> {fmtDateTime(selected.available_from)} → {fmtDateTime(selected.available_until)}</span>
                    <span><Timer size={14} /> {selected.duration_minutes} min</span>
                  </div>
                  <div className="row-actions" style={{ gap: 6, marginTop: 6 }}>
                    {selected.uses_pool
                      ? <span className="tag tag-purple"><Library size={12} /> Pool: {selected.question_count} of {selected.pool_size} per student</span>
                      : <span className="tag tag-grey">{selected.question_count} questions</span>}
                    {selected.shuffle_questions && <span className="tag tag-blue"><Shuffle size={12} /> Questions shuffled</span>}
                    {selected.shuffle_options && <span className="tag tag-blue"><Shuffle size={12} /> Options shuffled</span>}
                    {selected.require_fullscreen && <span className="tag tag-amber"><Maximize size={12} /> Fullscreen</span>}
                    {selected.max_violations && <span className="tag tag-red"><Lock size={12} /> Auto-submit at {selected.max_violations} violations</span>}
                  </div>
                </div>
              </div>

              <div className="action-bar">
                {isDraft && <button className="btn-primary" onClick={() => lifecycle('publish')}><Send size={16} /> Publish</button>}
                {isPublished && !hasAttempts && <button className="btn-ghost" onClick={() => lifecycle('unpublish')}><Undo2 size={16} /> Move to draft</button>}
                {isPublished && (
                  <button className="btn-ghost" onClick={() => lifecycle('close', 'Close this exam now? Students still writing will be submitted automatically.')}>
                    <Square size={15} /> Close now
                  </button>
                )}
                {!hasAttempts && selected.status !== 'closed' && <button className="btn-ghost" onClick={openEditExam}><Pencil size={15} /> Edit details</button>}
                {selected.status !== 'draft' && <Link className="btn-soft" to={`/results?exam=${selected.id}`}><BarChart3 size={16} /> Results ({selected.submission_count})</Link>}
                {!hasAttempts && <button className="btn-danger" onClick={deleteExam}><Trash2 size={15} /> Delete</button>}
              </div>
              {msg && <Alert type={msg.type === 'ok' ? 'ok' : 'error'} className="mb">{msg.text}</Alert>}

              <div className="head-row" style={{ marginBottom: '0.75rem' }}>
                <h3 className="section-title">Questions in this exam</h3>
                {isDraft && (
                  <div className="row-actions">
                    <button className="btn-ghost btn-sm" onClick={() => setShowBank(true)}><Copy size={15} /> From bank</button>
                    <button className="btn-primary btn-sm" onClick={() => setShowNewQ(true)}><Plus size={15} /> New question</button>
                  </div>
                )}
              </div>
              {!isDraft && <p className="muted small">Questions are locked while the exam is published or closed.</p>}
              {examQuestions.length === 0 ? <p className="muted">No questions yet — add some from your bank or create a new one.</p> : (
                <table className="data-table">
                  <thead><tr><th>#</th><th>Question</th><th>Type</th><th>Marks</th><th></th></tr></thead>
                  <tbody>
                    {examQuestions.map((eq, i) => (
                      <tr key={eq.id}>
                        <td>{i + 1}</td>
                        <td className="q-text">{eq.text}</td>
                        <td><span className="tag">{eq.type_display}</span></td>
                        <td>{eq.marks}</td>
                        <td className="row-actions">
                          {isDraft && <button className="link danger" onClick={() => removeQuestion(eq.id)}>Remove</button>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </section>
      </div>

      {examModal && (
        <div className="modal-backdrop" onClick={() => setExamModal(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={saveExam}>
            <h2>{examModal === 'new' ? 'New Exam' : 'Edit Exam'}</h2>
            {examError && <div className="alert-error">{examError}</div>}
            <label>Course
              <select value={examForm.course} onChange={setE('course')} required>
                <option value="">Select a course…</option>
                {courses.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
              </select>
            </label>
            <label>Title
              <input value={examForm.title} onChange={setE('title')} placeholder="e.g. Midterm Exam" required />
            </label>
            <label>Instructions <span className="muted">(optional)</span>
              <textarea rows={2} value={examForm.description} onChange={setE('description')} />
            </label>
            <div className="grid-2">
              <label>Opens at
                <input type="datetime-local" value={examForm.available_from} onChange={setE('available_from')} required />
              </label>
              <label>Closes at
                <input type="datetime-local" value={examForm.available_until} onChange={setE('available_until')} required />
              </label>
            </div>
            <label>Duration (minutes to finish once started)
              <input type="number" min="1" value={examForm.duration_minutes} onChange={setE('duration_minutes')} required />
            </label>
            <div className="options-editor">
              <div className="options-head"><span>Delivery and security</span></div>
              <label className="check-row">
                <input type="checkbox" checked={examForm.shuffle_questions} onChange={setE('shuffle_questions')} />
                Shuffle question order for each student
              </label>
              <label className="check-row">
                <input type="checkbox" checked={examForm.shuffle_options} onChange={setE('shuffle_options')} />
                Shuffle the options of multiple-choice questions
              </label>
              <label className="check-row">
                <input type="checkbox" checked={examForm.require_fullscreen} onChange={setE('require_fullscreen')} />
                Require fullscreen (leaving it counts as a violation)
              </label>
              <div className="grid-2">
                <label>Questions per student <span className="muted">(optional pool)</span>
                  <input type="number" min="1" value={examForm.questions_per_student} onChange={setE('questions_per_student')}
                         placeholder="All questions" />
                </label>
                <label>Auto-submit after violations <span className="muted">(optional)</span>
                  <input type="number" min="1" value={examForm.max_violations} onChange={setE('max_violations')} placeholder="Only record" />
                </label>
              </div>
              <span className="muted small">With a pool, each student gets that many questions drawn at random from the exam's questions
                (all must carry the same marks). Violations are tab switches and leaving fullscreen.</span>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={() => setExamModal(null)}>Cancel</button>
              <button className="btn-primary" type="submit">{examModal === 'new' ? 'Create exam' : 'Save changes'}</button>
            </div>
          </form>
        </div>
      )}

      {showNewQ && (
        <QuestionFormModal
          title="New Question"
          submitLabel="Add question"
          onSave={addNewQuestion}
          onClose={() => setShowNewQ(false)}
        />
      )}

      {showBank && (
        <BankPicker
          exam={selected}
          existing={new Set(examQuestions.map((eq) => eq.question))}
          onAdded={(text) => { setShowBank(false); refresh(); setMsg({ type: 'ok', text }) }}
          onClose={() => setShowBank(false)}
        />
      )}
    </div>
  )
}
