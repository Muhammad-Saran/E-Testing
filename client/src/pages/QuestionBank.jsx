import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckSquare, Copy, FileUp, Library, ListChecks, Lock, Plus, Search, Sparkles, ToggleLeft, Type,
} from 'lucide-react'
import { api } from '../api/client.js'
import QuestionFormModal, { DIFFICULTIES, TYPES } from '../components/QuestionFormModal.jsx'
import { Alert, EmptyState, PageHeader, StatCard } from '../components/ui.jsx'
import { errorText } from '../utils/format.js'

// Near-identical questions across the whole bank (Sentence-T5 similarity).
function DuplicateFinder({ onClose, onChanged }) {
  const [data, setData] = useState(null)
  const load = () => api.get('/questions/duplicates/').then((r) => setData(r.data))
  useEffect(() => { load() }, [])

  async function deactivate(q) {
    await api.patch(`/questions/${q.id}/`, { is_active: false })
    onChanged()
    load()
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
        <h2>Duplicate questions</h2>
        <p className="muted" style={{ margin: 0 }}>
          Pairs of questions with nearly the same wording{data && ` (compared with ${data.engine === 'sentence-t5' ? 'Sentence-T5 embeddings' : 'word overlap'})`}.
          Deactivate one copy to keep the bank clean; questions used in published exams are locked.
        </p>
        {!data && <div className="loading"><div className="spinner" />Comparing questions…</div>}
        {data?.pairs.length === 0 && <EmptyState icon={CheckSquare} title="No duplicates found" text="Every question in your bank is distinct." />}
        {data?.pairs.map((p, i) => (
          <div key={i} className="review-card">
            <div className="split-row"><span className="tag tag-amber">{p.score}% similar</span></div>
            <div className="review-grid">
              {[p.a, p.b].map((q) => (
                <div key={q.id} className="quote">
                  <div className="label">#{q.id} · {q.question_type.replace('_', ' ')}{q.course_code ? ` · ${q.course_code}` : ''}{!q.is_active && ' · inactive'}</div>
                  <div style={{ marginBottom: 8 }}>{q.text}</div>
                  {q.locked ? <span className="tag tag-grey"><Lock size={12} /> in use</span>
                    : q.is_active && <button className="btn-ghost btn-sm" onClick={() => deactivate(q)}>Deactivate this copy</button>}
                </div>
              ))}
            </div>
          </div>
        ))}
        <div className="modal-actions"><button className="btn-primary" onClick={onClose}>Close</button></div>
      </div>
    </div>
  )
}

const PAGE_SIZE = 20
const CSV_TEMPLATE =
  'text,question_type,difficulty,subject,marks,correct_answer_text,options\n' +
  'Which data structure is FIFO?,mcq,remember,Data Structures,2,Queue,Stack|Queue|Tree|Graph\n' +
  'A binary tree node has at most two children.,true_false,understand,Data Structures,1,true,\n' +
  'What does SQL stand for?,short_answer,remember,Databases,2,Structured Query Language,\n'

function answerPreview(q) {
  if (q.question_type === 'short_answer') return q.correct_answer_text
  return q.options.find((o) => o.is_correct)?.text || '—'
}

export default function QuestionBank() {
  const [data, setData] = useState({ results: [], count: 0 })
  const [stats, setStats] = useState(null)
  const [courses, setCourses] = useState([])
  const [filters, setFilters] = useState({ search: '', question_type: '', difficulty: '', course: '', is_ai_generated: '' })
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState(null) // null | 'new' | question
  const [msg, setMsg] = useState(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const [showDupes, setShowDupes] = useState(false)
  const fileRef = useRef(null)

  function load(p = page) {
    const params = { page: p, page_size: PAGE_SIZE, ordering: '-created_at' }
    Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v })
    api.get('/questions/', { params }).then((r) => setData(r.data))
    api.get('/questions/stats/').then((r) => setStats(r.data))
  }

  useEffect(() => {
    api.get('/courses/', { params: { page_size: 100 } }).then((r) => setCourses(r.data.results ?? r.data))
  }, [])

  // Reload when filters change (debounced for the search box).
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); load(1) }, 250)
    return () => clearTimeout(t)
  }, [filters]) // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value })

  async function save(payload) {
    if (editing === 'new') {
      await api.post('/questions/', payload)
      setMsg({ type: 'ok', text: 'Question added to the bank.' })
    } else {
      await api.patch(`/questions/${editing.id}/`, payload)
      setMsg({ type: 'ok', text: 'Question updated.' })
    }
    setEditing(null)
    load()
  }

  async function remove(q) {
    if (!confirm('Delete this question from the bank?')) return
    try {
      await api.delete(`/questions/${q.id}/`)
      setMsg({ type: 'ok', text: 'Question deleted.' })
      load()
    } catch (err) {
      setMsg({ type: 'err', text: errorText(err, 'Could not delete the question.') })
    }
  }

  async function toggleActive(q) {
    try {
      await api.patch(`/questions/${q.id}/`, { is_active: !q.is_active })
      load()
    } catch (err) {
      setMsg({ type: 'err', text: errorText(err, 'Could not update the question.') })
    }
  }

  async function importCsv(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setImporting(true)
    setImportResult(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const { data: res } = await api.post('/questions/import_csv/', form)
      setImportResult(res)
    } catch (err) {
      setImportResult(err.response?.data?.created !== undefined ? err.response.data : { error: errorText(err, 'Import failed.') })
    } finally {
      setImporting(false)
      load()
    }
  }

  function downloadTemplate() {
    const href = URL.createObjectURL(new Blob([CSV_TEMPLATE], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = href
    a.download = 'question-bank-template.csv'
    a.click()
    URL.revokeObjectURL(href)
  }

  const pages = Math.max(1, Math.ceil(data.count / PAGE_SIZE))
  const goTo = (p) => { setPage(p); load(p) }

  return (
    <div>
      <PageHeader icon={Library} title="Question bank" subtitle="Create, organise and reuse questions across your exams."
                  actions={<>
                    <input type="file" accept=".csv,text/csv" ref={fileRef} onChange={importCsv} hidden />
                    <button className="btn-ghost" onClick={() => setShowDupes(true)}><Copy size={16} /> Find duplicates</button>
                    <button className="btn-ghost" onClick={() => fileRef.current?.click()} disabled={importing}>
                      <FileUp size={16} /> {importing ? 'Importing…' : 'Import CSV'}
                    </button>
                    <Link className="btn-soft" to="/ai-generate"><Sparkles size={16} /> Generate with AI</Link>
                    <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={17} /> New question</button>
                  </>} />

      {stats && (
        <div className="stat-grid">
          <StatCard icon={Library} label="Total questions" value={stats.total} hint={`${stats.active} active`} />
          <StatCard icon={ListChecks} label="Multiple choice" value={stats.by_type.mcq} tone="green" />
          <StatCard icon={ToggleLeft} label="True / False" value={stats.by_type.true_false} tone="amber" />
          <StatCard icon={Type} label="Short answer" value={stats.by_type.short_answer} tone="blue" />
          <StatCard icon={Sparkles} label="AI-generated" value={stats.ai_generated} tone="purple" />
        </div>
      )}

      {importResult && (
        <div className={importResult.error || importResult.failed ? 'alert-error' : 'alert-ok'} style={{ marginBottom: '1rem' }}>
          {importResult.error
            ? importResult.error
            : <>Imported {importResult.created} question{importResult.created === 1 ? '' : 's'}
                {importResult.failed ? `, ${importResult.failed} row(s) failed:` : '.'}</>}
          {importResult.errors?.length > 0 && (
            <ul className="error-list">
              {importResult.errors.map((e) => (
                <li key={e.row}>Row {e.row}: {Object.entries(e.errors).map(([k, v]) => `${k} — ${[].concat(v).join(' ')}`).join('; ')}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {msg && <Alert type={msg.type === 'ok' ? 'ok' : 'error'} className="mb">{msg.text}</Alert>}

      <section className="panel">
        <div className="toolbar">
          <div className="input-icon search"><Search size={16} />
            <input placeholder="Search question text or subject…" value={filters.search} onChange={setF('search')} />
          </div>
          <select value={filters.question_type} onChange={setF('question_type')}>
            <option value="">All types</option>
            {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <select value={filters.difficulty} onChange={setF('difficulty')}>
            <option value="">All difficulties</option>
            {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
          <select value={filters.course} onChange={setF('course')}>
            <option value="">All courses</option>
            {courses.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
          </select>
          <select value={filters.is_ai_generated} onChange={setF('is_ai_generated')}>
            <option value="">Any source</option>
            <option value="true">AI-generated</option>
            <option value="false">Written manually</option>
          </select>
        </div>

        {data.results.length === 0 ? (
          <EmptyState icon={Library} title="No questions found"
                      text="Add a question, import a CSV, or let the AI generator write some from your lecture notes."
                      action={<button className="btn-soft btn-sm" onClick={downloadTemplate}>Download CSV template</button>} />
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr><th>Question</th><th>Type</th><th>Difficulty</th><th>Course</th><th>Marks</th><th>Answer</th><th></th></tr>
              </thead>
              <tbody>
                {data.results.map((q) => (
                  <tr key={q.id} className={q.is_active ? '' : 'row-muted'}>
                    <td className="q-text">
                      {q.text}
                      <div className="muted small">
                        {q.is_ai_generated && <span className="tag tag-purple" title="Generated by the T5 model"><Sparkles size={11} /> AI</span>}{' '}
                        {q.required_keywords && <span className="tag tag-blue" title={`Required keywords: ${q.required_keywords}`}>keywords</span>}{' '}
                        {q.subject || 'No subject'} · v{q.version}
                        {q.locked && <span title="Used in a published exam"> · 🔒 in use</span>}
                        {!q.is_active && ' · inactive'}
                      </div>
                    </td>
                    <td><span className="tag">{q.type_display}</span></td>
                    <td>{q.difficulty_display}</td>
                    <td>{q.course_code || '—'}</td>
                    <td>{q.marks}</td>
                    <td className="answer-cell">{answerPreview(q)}</td>
                    <td className="row-actions">
                      {!q.locked && <button className="link" onClick={() => setEditing(q)}>Edit</button>}
                      {!q.locked && (
                        <button className="link" onClick={() => toggleActive(q)}>{q.is_active ? 'Deactivate' : 'Activate'}</button>
                      )}
                      {!q.locked && <button className="link danger" onClick={() => remove(q)}>Delete</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {pages > 1 && (
          <div className="pager">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => goTo(page - 1)}>Previous</button>
            <span className="muted">Page {page} of {pages} · {data.count} questions</span>
            <button className="btn-ghost" disabled={page >= pages} onClick={() => goTo(page + 1)}>Next</button>
          </div>
        )}
        <p className="muted small" style={{ marginTop: '1rem' }}>
          CSV columns: text, question_type (mcq / true_false / short_answer), difficulty, subject, marks,
          correct_answer_text, options (MCQ choices separated by “|”). <button className="link" onClick={downloadTemplate}>Download template</button>
        </p>
      </section>

      {showDupes && <DuplicateFinder onClose={() => setShowDupes(false)} onChanged={() => load()} />}
      {editing && (
        <QuestionFormModal
          question={editing === 'new' ? null : editing}
          courses={courses}
          title={editing === 'new' ? 'New Question' : 'Edit Question'}
          submitLabel={editing === 'new' ? 'Add question' : 'Save changes'}
          onSave={save}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}
