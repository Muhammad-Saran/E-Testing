import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const TYPES = [
  { value: 'mcq', label: 'Multiple Choice' },
  { value: 'true_false', label: 'True / False' },
  { value: 'short_answer', label: 'Short Answer' },
]
const DIFFICULTIES = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']

const pad = (n) => String(n).padStart(2, '0')
const toLocal = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
const plusHours = (h) => { const d = new Date(); d.setHours(d.getHours() + h); return toLocal(d) }
const BLANK_EXAM = () => ({ course: '', title: '', available_from: plusHours(0), available_until: plusHours(24), duration_minutes: 20 })

const BLANK_Q = () => ({
  text: '', question_type: 'mcq', difficulty: 'understand', marks: 1, subject: '',
  correct_answer_text: '', tf_correct: 'true',
  options: [{ text: '', is_correct: true }, { text: '', is_correct: false }],
})

export default function InstructorExams() {
  const [exams, setExams] = useState([])
  const [courses, setCourses] = useState([])
  const [selected, setSelected] = useState(null)
  const [examQuestions, setExamQuestions] = useState([])
  const [showExam, setShowExam] = useState(false)
  const [examForm, setExamForm] = useState(BLANK_EXAM())
  const [examError, setExamError] = useState('')
  const [showQ, setShowQ] = useState(false)
  const [q, setQ] = useState(BLANK_Q())
  const [qError, setQError] = useState('')
  const [msg, setMsg] = useState(null)

  function loadExams(selectId) {
    api.get('/exams/').then((r) => {
      const list = r.data.results ?? r.data
      setExams(list)
      const pick = selectId ? list.find((e) => e.id === selectId) : (selected && list.find((e) => e.id === selected.id))
      if (pick) select(pick)
    })
  }
  useEffect(() => {
    loadExams()
    api.get('/courses/').then((r) => setCourses(r.data.results ?? r.data))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function select(exam) {
    setSelected(exam); setMsg(null)
    api.get(`/exams/${exam.id}/questions/`).then((r) => setExamQuestions(r.data))
  }
  function refresh(id) {
    api.get(`/exams/${id}/`).then((r) => { setSelected(r.data); setExams((p) => p.map((e) => (e.id === id ? r.data : e))) })
    api.get(`/exams/${id}/questions/`).then((r) => setExamQuestions(r.data))
  }

  async function createExam(e) {
    e.preventDefault(); setExamError('')
    try {
      const { data } = await api.post('/exams/', examForm)
      setShowExam(false); setExamForm(BLANK_EXAM()); loadExams(data.id)
    } catch (err) {
      const d = err.response?.data
      setExamError(typeof d === 'object' ? Object.values(d).flat().join(' ') : 'Could not create exam.')
    }
  }

  function openAddQuestion() { setQ(BLANK_Q()); setQError(''); setShowQ(true) }

  function buildPayload() {
    const base = { text: q.text, question_type: q.question_type, difficulty: q.difficulty,
      marks: Number(q.marks), subject: q.subject }
    if (q.question_type === 'mcq') return { ...base, options: q.options }
    if (q.question_type === 'true_false') {
      return { ...base, options: [
        { text: 'True', is_correct: q.tf_correct === 'true' },
        { text: 'False', is_correct: q.tf_correct === 'false' },
      ] }
    }
    return { ...base, correct_answer_text: q.correct_answer_text }
  }

  async function addQuestion(e) {
    e.preventDefault(); setQError('')
    try {
      await api.post(`/exams/${selected.id}/add_question/`, buildPayload())
      setShowQ(false); refresh(selected.id)
      setMsg({ type: 'ok', text: 'Question added to the exam.' })
    } catch (err) {
      const d = err.response?.data
      setQError(typeof d === 'object' ? Object.values(d).flat().join(' ') : 'Could not add question.')
    }
  }

  async function removeQuestion(eqId) {
    await api.post(`/exams/${selected.id}/remove_question/`, { exam_question_id: eqId })
    refresh(selected.id)
  }

  async function togglePublish() {
    const action = selected.status === 'published' ? 'unpublish' : 'publish'
    try {
      const { data } = await api.post(`/exams/${selected.id}/${action}/`, {})
      setSelected(data); setExams((p) => p.map((e) => (e.id === data.id ? data : e)))
      setMsg({ type: 'ok', text: action === 'publish' ? 'Exam published — students can now take it.' : 'Exam moved back to draft.' })
    } catch (err) {
      setMsg({ type: 'err', text: err.response?.data?.detail || 'Action failed.' })
    }
  }

  const setE = (k) => (e) => setExamForm({ ...examForm, [k]: e.target.value })
  const setQf = (k) => (e) => setQ({ ...q, [k]: e.target.value })
  const setOpt = (i, key, val) => setQ({ ...q, options: q.options.map((o, idx) => (idx === i ? { ...o, [key]: val } : o)) })
  const addOpt = () => setQ({ ...q, options: [...q.options, { text: '', is_correct: false }] })
  const rmOpt = (i) => setQ({ ...q, options: q.options.filter((_, idx) => idx !== i) })

  return (
    <div>
      <header className="page-head">
        <div><h1>Exams</h1><p className="muted">Schedule an exam, then add its questions.</p></div>
        <button className="btn-primary" onClick={() => { setExamForm(BLANK_EXAM()); setExamError(''); setShowExam(true) }}
                disabled={courses.length === 0}>+ New Exam</button>
      </header>
      {courses.length === 0 && <div className="alert-error" style={{ marginBottom: '1rem' }}>Create a course first — exams belong to a course.</div>}

      <div className="panel-row" style={{ gridTemplateColumns: '1fr 1.5fr', alignItems: 'start' }}>
        <section className="panel">
          <h2>My exams</h2>
          {exams.length === 0 ? <p className="muted">No exams yet.</p> : (
            <ul className="plain-list">
              {exams.map((e) => (
                <li key={e.id} style={{ cursor: 'pointer', justifyContent: 'space-between',
                      background: selected?.id === e.id ? 'var(--bg)' : 'transparent', borderRadius: 8, padding: '0.7rem 0.6rem' }}
                    onClick={() => select(e)}>
                  <span><strong>{e.title}</strong><br /><span className="muted">{e.course_code} · {e.question_count} Q · {e.duration_minutes}m</span></span>
                  <span className={`tag ${e.status === 'published' ? 'tag-green' : ''}`}>{e.status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          {!selected ? <p className="muted">Select an exam to add questions, or create one.</p> : (
            <>
              <div className="head-row">
                <h2 style={{ marginBottom: 4 }}>{selected.title}</h2>
                <button className={selected.status === 'published' ? 'btn-ghost' : 'btn-primary'} onClick={togglePublish}>
                  {selected.status === 'published' ? 'Unpublish' : 'Publish'}
                </button>
              </div>
              <p className="muted" style={{ marginTop: 0 }}>
                {selected.course_code} · {selected.duration_minutes} min · {selected.question_count} questions · {selected.total_marks} marks
              </p>
              {msg && <div className={msg.type === 'ok' ? 'alert-ok' : 'alert-error'} style={{ marginBottom: '1rem' }}>{msg.text}</div>}

              <div className="head-row" style={{ marginBottom: '0.75rem' }}>
                <h3 style={{ margin: 0, fontSize: '0.95rem' }}>Questions in this exam</h3>
                <button className="btn-primary" onClick={openAddQuestion}>+ Add Question</button>
              </div>
              {examQuestions.length === 0 ? <p className="muted">No questions yet — add the first one.</p> : (
                <table className="data-table">
                  <thead><tr><th>#</th><th>Question</th><th>Type</th><th>Marks</th><th></th></tr></thead>
                  <tbody>
                    {examQuestions.map((eq, i) => (
                      <tr key={eq.id}>
                        <td>{i + 1}</td>
                        <td className="q-text">{eq.text}</td>
                        <td><span className="tag">{eq.type_display}</span></td>
                        <td>{eq.marks}</td>
                        <td className="row-actions"><button className="link danger" onClick={() => removeQuestion(eq.id)}>Remove</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </section>
      </div>

      {/* Create exam modal */}
      {showExam && (
        <div className="modal-backdrop" onClick={() => setShowExam(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={createExam}>
            <h2>New Exam</h2>
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
            <div className="grid-2">
              <label>Available from
                <input type="datetime-local" value={examForm.available_from} onChange={setE('available_from')} required />
              </label>
              <label>Available until
                <input type="datetime-local" value={examForm.available_until} onChange={setE('available_until')} required />
              </label>
            </div>
            <label>Duration (minutes to finish once started)
              <input type="number" min="1" value={examForm.duration_minutes} onChange={setE('duration_minutes')} required />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={() => setShowExam(false)}>Cancel</button>
              <button className="btn-primary" type="submit">Create exam</button>
            </div>
          </form>
        </div>
      )}

      {/* Add question modal */}
      {showQ && (
        <div className="modal-backdrop" onClick={() => setShowQ(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={addQuestion}>
            <h2>New Question</h2>
            {qError && <div className="alert-error">{qError}</div>}
            <label>Question text
              <textarea rows={3} value={q.text} onChange={setQf('text')} required />
            </label>
            <div className="grid-3">
              <label>Type
                <select value={q.question_type} onChange={setQf('question_type')}>
                  {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              <label>Difficulty
                <select value={q.difficulty} onChange={setQf('difficulty')}>
                  {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <label>Marks
                <input type="number" min="1" value={q.marks} onChange={setQf('marks')} />
              </label>
            </div>
            <label>Subject
              <input value={q.subject} onChange={setQf('subject')} placeholder="e.g. Data Structures" />
            </label>

            {q.question_type === 'mcq' && (
              <div className="options-editor">
                <div className="options-head"><span>Options (tick the correct one)</span>
                  <button type="button" className="link" onClick={addOpt}>+ Add</button></div>
                {q.options.map((o, i) => (
                  <div key={i} className="option-row">
                    <input type="checkbox" checked={o.is_correct} onChange={(e) => setOpt(i, 'is_correct', e.target.checked)} />
                    <input value={o.text} placeholder={`Option ${i + 1}`} onChange={(e) => setOpt(i, 'text', e.target.value)} required />
                    {q.options.length > 2 && <button type="button" className="link danger" onClick={() => rmOpt(i)}>×</button>}
                  </div>
                ))}
              </div>
            )}
            {q.question_type === 'true_false' && (
              <label>Correct answer
                <select value={q.tf_correct} onChange={setQf('tf_correct')}>
                  <option value="true">True</option>
                  <option value="false">False</option>
                </select>
              </label>
            )}
            {q.question_type === 'short_answer' && (
              <label>Reference answer
                <textarea rows={2} value={q.correct_answer_text} onChange={setQf('correct_answer_text')}
                          placeholder="Model answer used for grading" required />
              </label>
            )}

            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={() => setShowQ(false)}>Cancel</button>
              <button className="btn-primary" type="submit">Add question</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
