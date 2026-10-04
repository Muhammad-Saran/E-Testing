import { useEffect, useState } from 'react'
import { AlertTriangle, Plus, Wand2, X } from 'lucide-react'
import { api } from '../api/client.js'
import { errorText } from '../utils/format.js'
import { Alert } from './ui.jsx'

export const TYPES = [
  { value: 'mcq', label: 'Multiple Choice' },
  { value: 'true_false', label: 'True / False' },
  { value: 'short_answer', label: 'Short Answer' },
]
export const DIFFICULTIES = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']

function toForm(question) {
  if (!question) {
    return {
      text: '', question_type: 'mcq', difficulty: 'understand', marks: 1, subject: '', course: '',
      correct_answer_text: '', required_keywords: '', tf_correct: 'true',
      options: [{ text: '', is_correct: true }, { text: '', is_correct: false }],
    }
  }
  const options = question.options?.length
    ? question.options.map((o) => ({ text: o.text, is_correct: o.is_correct }))
    : [{ text: '', is_correct: true }, { text: '', is_correct: false }]
  const tfCorrect = question.options?.find((o) => o.is_correct)?.text?.toLowerCase() === 'false' ? 'false' : 'true'
  return {
    text: question.text, question_type: question.question_type, difficulty: question.difficulty,
    marks: question.marks, subject: question.subject || '', course: question.course || '',
    correct_answer_text: question.correct_answer_text || '', required_keywords: question.required_keywords || '',
    tf_correct: tfCorrect, options,
  }
}

/**
 * Create / edit a question. `onSave(payload)` should POST or PATCH it and
 * throw on failure; errors are shown inside the modal.
 * Pass `courses` to let the instructor tag the question with a course.
 */
export default function QuestionFormModal({ question, courses, title, submitLabel, onSave, onClose }) {
  const [q, setQ] = useState(() => toForm(question))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [similar, setSimilar] = useState([])
  const [bloomCue, setBloomCue] = useState('')

  const set = (k) => (e) => setQ({ ...q, [k]: e.target.value })
  const setOptText = (i, text) => setQ({ ...q, options: q.options.map((o, idx) => (idx === i ? { ...o, text } : o)) })
  const markCorrect = (i) => setQ({ ...q, options: q.options.map((o, idx) => ({ ...o, is_correct: idx === i })) })
  const addOpt = () => setQ({ ...q, options: [...q.options, { text: '', is_correct: false }] })
  const rmOpt = (i) => {
    let options = q.options.filter((_, idx) => idx !== i)
    if (!options.some((o) => o.is_correct)) options = options.map((o, idx) => ({ ...o, is_correct: idx === 0 }))
    setQ({ ...q, options })
  }

  // Warn about near-duplicates already in the bank while typing.
  useEffect(() => {
    if (q.text.trim().split(/\s+/).length < 4) { setSimilar([]); return undefined }
    const t = setTimeout(() => {
      api.post('/questions/similar/', { text: q.text, exclude: question?.id })
        .then((r) => setSimilar(r.data.matches || [])).catch(() => {})
    }, 700)
    return () => clearTimeout(t)
  }, [q.text, question?.id])

  async function suggestBloom() {
    const { data } = await api.post('/questions/suggest_difficulty/', { text: q.text })
    setQ((cur) => ({ ...cur, difficulty: data.difficulty }))
    setBloomCue(data.cue ? `Suggested from the verb “${data.cue}”.` : 'No action verb found — recall level assumed.')
  }

  function buildPayload() {
    const base = {
      text: q.text, question_type: q.question_type, difficulty: q.difficulty,
      marks: Number(q.marks), subject: q.subject,
    }
    if (courses) base.course = q.course || null
    if (q.question_type === 'mcq') return { ...base, options: q.options, correct_answer_text: '', required_keywords: '' }
    if (q.question_type === 'true_false') {
      return {
        ...base, correct_answer_text: q.tf_correct, required_keywords: '',
        options: [
          { text: 'True', is_correct: q.tf_correct === 'true' },
          { text: 'False', is_correct: q.tf_correct === 'false' },
        ],
      }
    }
    return { ...base, options: [], correct_answer_text: q.correct_answer_text, required_keywords: q.required_keywords }
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await onSave(buildPayload())
    } catch (err) {
      setError(errorText(err, 'Could not save the question.'))
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal modal-wide" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="split-row"><h2>{title}</h2><button type="button" className="icon-btn" onClick={onClose} aria-label="Close"><X size={17} /></button></div>
        {error && <Alert type="error">{error}</Alert>}
        <label>Question text
          <textarea rows={3} value={q.text} onChange={set('text')} required autoFocus />
        </label>
        {similar.length > 0 && (
          <div className="similar-box">
            <strong><AlertTriangle size={14} style={{ verticalAlign: -2 }} /> Similar question{similar.length > 1 ? 's' : ''} already in your bank</strong>
            <ul>{similar.map((m) => <li key={m.id}>{m.text} <span className="muted small">({m.score}% similar{m.course_code ? `, ${m.course_code}` : ''})</span></li>)}</ul>
          </div>
        )}
        <div className="grid-3">
          <label>Type
            <select value={q.question_type} onChange={set('question_type')}>
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </label>
          <label>
            <span className="split-row">Difficulty (Bloom)
              <button type="button" className="link" onClick={suggestBloom} disabled={!q.text.trim()} title="Suggest from the wording"><Wand2 size={13} /> Suggest</button>
            </span>
            <select value={q.difficulty} onChange={set('difficulty')}>
              {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label>Marks
            <input type="number" min="1" value={q.marks} onChange={set('marks')} required />
          </label>
        </div>
        {bloomCue && <span className="muted small" style={{ marginTop: -8 }}>{bloomCue}</span>}
        <div className={courses ? 'grid-2' : ''}>
          <label>Subject / topic
            <input value={q.subject} onChange={set('subject')} placeholder="e.g. Data Structures" />
          </label>
          {courses && (
            <label>Course <span className="muted">(optional)</span>
              <select value={q.course} onChange={set('course')}>
                <option value="">No course</option>
                {courses.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
              </select>
            </label>
          )}
        </div>

        {q.question_type === 'mcq' && (
          <div className="options-editor">
            <div className="options-head"><span>Options — select the correct one</span>
              <button type="button" className="link" onClick={addOpt}><Plus size={14} /> Add option</button></div>
            {q.options.map((o, i) => (
              <div key={i} className="option-row">
                <input type="radio" name="correct-option" checked={o.is_correct} onChange={() => markCorrect(i)}
                       aria-label={`Option ${i + 1} is correct`} />
                <input value={o.text} placeholder={`Option ${i + 1}`} onChange={(e) => setOptText(i, e.target.value)} required />
                {q.options.length > 2 && <button type="button" className="icon-btn" style={{ width: 32, height: 32 }} onClick={() => rmOpt(i)} aria-label="Remove option"><X size={15} /></button>}
              </div>
            ))}
          </div>
        )}
        {q.question_type === 'true_false' && (
          <label>Correct answer
            <select value={q.tf_correct} onChange={set('tf_correct')}>
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          </label>
        )}
        {q.question_type === 'short_answer' && (
          <>
            <label>Reference answer
              <textarea rows={2} value={q.correct_answer_text} onChange={set('correct_answer_text')}
                        placeholder="Model answer used for grading" required />
            </label>
            <label>Required keywords <span className="muted">(optional)</span>
              <input value={q.required_keywords} onChange={set('required_keywords')}
                     placeholder="e.g. last in first out | LIFO, stack" />
              <span className="muted small" style={{ fontWeight: 400 }}>
                Comma-separated key terms, “|” for alternatives. Answers missing some get at most half marks; missing all get none.
                Answers are otherwise graded by meaning (Sentence-T5); close answers earn half marks and borderline ones are flagged for your review.
              </span>
            </label>
          </>
        )}

        <div className="modal-actions">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" type="submit" disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
        </div>
      </form>
    </div>
  )
}
