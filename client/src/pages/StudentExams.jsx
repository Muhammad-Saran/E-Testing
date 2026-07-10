import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'

const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

export default function StudentExams() {
  const [view, setView] = useState('list')   // 'list' | 'taking' | 'result'
  const [exams, setExams] = useState([])
  const [session, setSession] = useState(null) // { examId, questions, exam }
  const [answers, setAnswers] = useState({})
  const [remaining, setRemaining] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const submittingRef = useRef(false)

  function loadList() {
    api.get('/exams/available/').then((r) => setExams(r.data))
  }
  useEffect(() => { loadList() }, [])

  async function startExam(examId) {
    setError('')
    try {
      const { data } = await api.post(`/exams/${examId}/start/`, {})
      setSession({ examId, questions: data.questions, exam: data.exam })
      setAnswers({})
      setRemaining(data.remaining_seconds)
      setResult(null)
      submittingRef.current = false
      setView('taking')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not start the exam.')
    }
  }

  const submitExam = useCallback(async () => {
    if (submittingRef.current || !session) return
    submittingRef.current = true
    const payload = {
      answers: session.questions.map((q) => ({
        exam_question_id: q.id,
        ...(answers[q.id] || {}),
      })),
    }
    try {
      const { data } = await api.post(`/exams/${session.examId}/submit/`, payload)
      setResult(data)
      setView('result')
      loadList()
    } catch (err) {
      setError(err.response?.data?.detail || 'Submit failed.')
      submittingRef.current = false
    }
  }, [session, answers])

  // countdown — auto-submit at zero
  useEffect(() => {
    if (view !== 'taking') return
    if (remaining <= 0) { submitExam(); return }
    const t = setInterval(() => setRemaining((r) => r - 1), 1000)
    return () => clearInterval(t)
  }, [view, remaining, submitExam])

  function choose(qId, optionId) {
    setAnswers({ ...answers, [qId]: { selected_option_id: optionId } })
  }
  function typeAnswer(qId, text) {
    setAnswers({ ...answers, [qId]: { answer_text: text } })
  }

  // ----- RESULT VIEW -----
  if (view === 'result' && result) {
    return (
      <div>
        <header className="page-head"><div><h1>Exam Submitted</h1></div></header>
        <div className="panel result-hero">
          <div className="result-score">{result.score} / {result.total_marks}</div>
          <p className="muted" style={{ fontSize: '1.1rem', marginTop: 8 }}>{result.percentage}% · {result.correct_count} of {result.question_count} correct</p>
          <button className="btn-primary" style={{ marginTop: 16 }} onClick={() => setView('list')}>Back to exams</button>
        </div>
      </div>
    )
  }

  // ----- TAKING VIEW -----
  if (view === 'taking' && session) {
    const warn = remaining <= 60
    return (
      <div>
        <header className="page-head" style={{ position: 'sticky', top: 0 }}>
          <div><h1>{session.exam.title}</h1><p className="muted">{session.questions.length} questions · {session.exam.total_marks} marks</p></div>
          <div className={`exam-timer ${warn ? 'warn' : ''}`}>⏱ {fmt(remaining)}</div>
        </header>
        {error && <div className="alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

        {session.questions.map((q, i) => (
          <div key={q.id} className="q-card">
            <div className="q-head"><span>Question {i + 1}</span><span>{q.marks} mark{q.marks > 1 ? 's' : ''}</span></div>
            <div style={{ fontWeight: 600, marginBottom: '0.75rem' }}>{q.text}</div>

            {q.question_type === 'short_answer' ? (
              <textarea rows={2} placeholder="Your answer"
                        value={answers[q.id]?.answer_text || ''}
                        onChange={(e) => typeAnswer(q.id, e.target.value)} style={{ width: '100%' }} />
            ) : (
              q.options.map((o) => (
                <label key={o.id} className={`opt-row ${answers[q.id]?.selected_option_id === o.id ? 'chosen' : ''}`}>
                  <input type="radio" name={`q-${q.id}`} checked={answers[q.id]?.selected_option_id === o.id}
                         onChange={() => choose(q.id, o.id)} />
                  {o.text}
                </label>
              ))
            )}
          </div>
        ))}

        <button className="btn-primary" onClick={submitExam} style={{ padding: '0.8rem 1.5rem' }}>Submit exam</button>
      </div>
    )
  }

  // ----- LIST VIEW -----
  return (
    <div>
      <header className="page-head"><div><h1>Exams</h1><p className="muted">Exams available in your enrolled courses.</p></div></header>
      {error && <div className="alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}
      <section className="panel">
        {exams.length === 0 ? <p className="muted">No exams available right now.</p> : (
          <table className="data-table">
            <thead><tr><th>Exam</th><th>Course</th><th>Questions</th><th>Duration</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {exams.map((e) => (
                <tr key={e.id}>
                  <td><strong>{e.title}</strong></td>
                  <td>{e.course_code}</td>
                  <td>{e.question_count}</td>
                  <td>{e.duration_minutes} min</td>
                  <td>
                    {e.attempted
                      ? <span className="tag tag-green">Done · {e.score}/{e.total_marks}</span>
                      : e.is_open ? <span className="tag tag-green">Open</span> : <span className="tag">Not open</span>}
                  </td>
                  <td className="row-actions">
                    {!e.attempted && e.is_open &&
                      <button className="btn-primary" onClick={() => startExam(e.id)}>Start</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
