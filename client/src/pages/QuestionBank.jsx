import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client.js'

const TYPES = [
  { value: 'mcq', label: 'Multiple Choice' },
  { value: 'true_false', label: 'True / False' },
  { value: 'short_answer', label: 'Short Answer' },
]
const DIFFICULTIES = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']

const BLANK = {
  text: '', question_type: 'mcq', difficulty: 'understand', subject: '', marks: 1,
  correct_answer_text: '', options: [{ text: '', is_correct: true }, { text: '', is_correct: false }],
}

export default function QuestionBank() {
  const [questions, setQuestions] = useState([])
  const [filters, setFilters] = useState({ search: '', question_type: '', difficulty: '' })
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(BLANK)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const load = useCallback(() => {
    const params = {}
    if (filters.search) params.search = filters.search
    if (filters.question_type) params.question_type = filters.question_type
    if (filters.difficulty) params.difficulty = filters.difficulty
    api.get('/questions/', { params }).then((r) => setQuestions(r.data.results ?? r.data))
  }, [filters])

  useEffect(() => { load() }, [load])

  function openCreate() {
    setEditing(null)
    setForm(BLANK)
    setFormError('')
    setShowModal(true)
  }

  function openEdit(q) {
    setEditing(q.id)
    setForm({
      text: q.text, question_type: q.question_type, difficulty: q.difficulty,
      subject: q.subject || '', marks: q.marks, correct_answer_text: q.correct_answer_text || '',
      options: q.options?.length ? q.options.map((o) => ({ text: o.text, is_correct: o.is_correct })) : BLANK.options,
    })
    setFormError('')
    setShowModal(true)
  }

  async function remove(id) {
    if (!confirm('Delete this question?')) return
    await api.delete(`/questions/${id}/`)
    load()
  }

  const setField = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  function setOption(i, key, value) {
    const options = form.options.map((o, idx) => (idx === i ? { ...o, [key]: value } : o))
    setForm({ ...form, options })
  }
  const addOption = () => setForm({ ...form, options: [...form.options, { text: '', is_correct: false }] })
  const removeOption = (i) => setForm({ ...form, options: form.options.filter((_, idx) => idx !== i) })

  async function save(e) {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    const payload = { ...form, marks: Number(form.marks) }
    if (form.question_type === 'short_answer') delete payload.options
    try {
      if (editing) await api.put(`/questions/${editing}/`, payload)
      else await api.post('/questions/', payload)
      setShowModal(false)
      load()
    } catch (err) {
      const d = err.response?.data
      setFormError(typeof d === 'object' ? JSON.stringify(d) : 'Could not save question.')
    } finally {
      setSaving(false)
    }
  }

  const isChoice = form.question_type === 'mcq' || form.question_type === 'true_false'

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Question Bank</h1>
          <p className="muted">Create, categorize and reuse assessment items.</p>
        </div>
        <button className="btn-primary" onClick={openCreate}>+ New Question</button>
      </header>

      <div className="toolbar">
        <input className="search" placeholder="Search questions…"
               value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
        <select value={filters.question_type} onChange={(e) => setFilters({ ...filters, question_type: e.target.value })}>
          <option value="">All types</option>
          {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select value={filters.difficulty} onChange={(e) => setFilters({ ...filters, difficulty: e.target.value })}>
          <option value="">All difficulties</option>
          {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      <div className="panel">
        {questions.length === 0
          ? <p className="muted">No questions found. Create your first one.</p>
          : (
            <table className="data-table">
              <thead>
                <tr><th>Question</th><th>Type</th><th>Difficulty</th><th>Subject</th><th>Marks</th><th></th></tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.id}>
                    <td className="q-text">{q.text}</td>
                    <td><span className="tag">{q.type_display}</span></td>
                    <td>{q.difficulty_display}</td>
                    <td>{q.subject || '—'}</td>
                    <td>{q.marks}</td>
                    <td className="row-actions">
                      <button className="link" onClick={() => openEdit(q)}>Edit</button>
                      <button className="link danger" onClick={() => remove(q.id)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>

      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <h2>{editing ? 'Edit' : 'New'} Question</h2>
            {formError && <div className="alert-error">{formError}</div>}

            <label>Question text
              <textarea rows={3} value={form.text} onChange={setField('text')} required />
            </label>

            <div className="grid-3">
              <label>Type
                <select value={form.question_type} onChange={setField('question_type')}>
                  {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              <label>Difficulty
                <select value={form.difficulty} onChange={setField('difficulty')}>
                  {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <label>Marks
                <input type="number" min="1" value={form.marks} onChange={setField('marks')} />
              </label>
            </div>

            <label>Subject
              <input value={form.subject} onChange={setField('subject')} placeholder="e.g. Data Structures" />
            </label>

            {isChoice && (
              <div className="options-editor">
                <div className="options-head">
                  <span>Options (tick the correct one)</span>
                  <button type="button" className="link" onClick={addOption}>+ Add</button>
                </div>
                {form.options.map((o, i) => (
                  <div key={i} className="option-row">
                    <input type="checkbox" checked={o.is_correct}
                           onChange={(e) => setOption(i, 'is_correct', e.target.checked)} />
                    <input value={o.text} placeholder={`Option ${i + 1}`}
                           onChange={(e) => setOption(i, 'text', e.target.value)} required />
                    {form.options.length > 2 &&
                      <button type="button" className="link danger" onClick={() => removeOption(i)}>×</button>}
                  </div>
                ))}
              </div>
            )}

            {form.question_type === 'short_answer' && (
              <label>Reference answer
                <textarea rows={2} value={form.correct_answer_text} onChange={setField('correct_answer_text')}
                          placeholder="Model answer used for semantic grading" required />
              </label>
            )}

            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save question'}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
