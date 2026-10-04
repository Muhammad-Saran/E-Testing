import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AlertTriangle, Cpu, FileText, Pencil, Plus, Save, Sparkles, Type } from 'lucide-react'
import { api } from '../api/client.js'
import QuestionFormModal, { DIFFICULTIES, TYPES } from '../components/QuestionFormModal.jsx'
import { Alert, EmptyState, PageHeader } from '../components/ui.jsx'
import { errorText, fmtDateTime, fmtRelative } from '../utils/format.js'

const POLL_MS = 2000
const TYPE_LABEL = Object.fromEntries(TYPES.map((t) => [t.value, t.label]))

function answerOf(q) {
  if (q.question_type === 'short_answer') return q.correct_answer_text
  return q.options.find((o) => o.is_correct)?.text || '—'
}

// AI question generation with instructor review (scope doc, Module 3).
export default function AIGenerate() {
  const [params, setParams] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [courses, setCourses] = useState([])
  const [materials, setMaterials] = useState([])
  const [jobs, setJobs] = useState([])
  const [form, setForm] = useState({
    source: 'text', source_text: '', material: '', course: '', question_type: 'mixed',
    count: 5, difficulty: 'auto', subject: '', quality: 'fast',
  })
  const [error, setError] = useState('')
  const [job, setJob] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [editing, setEditing] = useState(null) // index into candidates
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState(null)
  const jobId = params.get('job')

  const loadJobs = () => api.get('/ai/jobs/', { params: { page_size: 10 } }).then((r) => setJobs(r.data.results ?? r.data))

  useEffect(() => {
    api.get('/ai/jobs/status/').then((r) => setStatus(r.data)).catch(() => {})
    api.get('/courses/', { params: { page_size: 100 } }).then((r) => setCourses(r.data.results ?? r.data))
    api.get('/courses/materials/').then((r) => setMaterials(r.data.results ?? r.data))
    loadJobs()
  }, [])

  // Pre-select everything except likely duplicates.
  const initialSelection = (list) => new Set(list.map((c, i) => (c.duplicate_of ? null : i)).filter((i) => i !== null))

  // Load the selected job and poll it until generation has finished.
  useEffect(() => {
    if (!jobId) { setJob(null); return undefined }
    let timer
    let cancelled = false
    const fetchJob = () => api.get(`/ai/jobs/${jobId}/`).then((r) => {
      if (cancelled) return
      setJob(r.data)
      if (r.data.status === 'pending' || r.data.status === 'running') {
        timer = setTimeout(fetchJob, POLL_MS)
      } else {
        setCandidates(r.data.candidates)
        setSelected(initialSelection(r.data.candidates))
        loadJobs()
      }
    }).catch((err) => setError(errorText(err, 'Could not load the generation job.')))
    setSaveResult(null)
    setCandidates([])
    fetchJob()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [jobId])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function generate(e) {
    e.preventDefault()
    setError('')
    const payload = {
      question_type: form.question_type, count: Number(form.count), difficulty: form.difficulty,
      subject: form.subject, course: form.course || null, quality: form.quality,
    }
    if (form.source === 'text') payload.source_text = form.source_text
    else payload.material = form.material || null
    try {
      const { data } = await api.post('/ai/jobs/', payload)
      setParams({ job: String(data.id) })
    } catch (err) {
      setError(errorText(err, 'Could not start generation.'))
    }
  }

  function toggle(i) {
    const next = new Set(selected)
    next.has(i) ? next.delete(i) : next.add(i)
    setSelected(next)
  }

  async function saveEdit(payload) {
    setCandidates(candidates.map((c, i) => (i === editing ? { ...c, ...payload } : c)))
    setEditing(null)
  }

  async function commit() {
    setSaving(true)
    setSaveResult(null)
    const questions = candidates.filter((_, i) => selected.has(i))
    try {
      const { data } = await api.post(`/ai/jobs/${job.id}/commit/`, { questions })
      setSaveResult({ ok: true, ...data })
      loadJobs()
    } catch (err) {
      setSaveResult({ ok: false, ...(err.response?.data || {}), error: errorText(err, 'Could not save the questions.') })
    } finally {
      setSaving(false)
    }
  }

  const running = job && (job.status === 'pending' || job.status === 'running')
  const qg = status?.question_generation
  const courseMaterials = materials.filter((m) => !form.course || String(m.course) === String(form.course))

  return (
    <div>
      <PageHeader icon={Sparkles} title="AI question generator"
                  subtitle="A T5 Transformer reads your lecture notes and drafts questions. You review, edit and keep the good ones."
                  actions={jobId && <button className="btn-ghost" onClick={() => setParams({})}><Plus size={16} /> New generation</button>} />

      {status && (
        <Alert type={qg.available ? 'info' : 'warn'} className="mb">
          {qg.available
            ? <>Engine: <strong>T5 Transformer</strong> — fast <code>{qg.models?.fast?.model || qg.model}</code>, better <code>{qg.models?.better?.model}</code>.
                {' '}Difficulty can be set automatically by the Bloom's-taxonomy classifier, and questions that repeat your bank are flagged.</>
            : <>The T5 model is not installed on the server, so a simpler rule-based generator is used. See <code>requirements-ai.txt</code>.</>}
        </Alert>
      )}
      {error && <Alert type="error" className="mb">{error}</Alert>}

      {!jobId && (
        <section className="panel">
          <form className="stack" onSubmit={generate}>
            <div className="role-toggle">
              <button type="button" className={form.source === 'text' ? 'active' : ''} onClick={() => setForm({ ...form, source: 'text' })}><Type size={17} /> Paste text</button>
              <button type="button" className={form.source === 'material' ? 'active' : ''} onClick={() => setForm({ ...form, source: 'material' })}><FileText size={17} /> Use course material</button>
            </div>
            <div className="grid-2">
              <label>Course <span className="muted">(questions are tagged with it)</span>
                <select value={form.course} onChange={set('course')}>
                  <option value="">No course</option>
                  {courses.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
                </select>
              </label>
              <label>Subject / topic
                <input value={form.subject} onChange={set('subject')} placeholder="e.g. Data Structures" />
              </label>
            </div>
            {form.source === 'text' ? (
              <label>Source text
                <textarea rows={10} value={form.source_text} onChange={set('source_text')} required
                          placeholder="Paste lecture notes or a chapter summary — complete, factual sentences work best." />
                <span className="muted small">{form.source_text.split(/\s+/).filter(Boolean).length} words</span>
              </label>
            ) : (
              <label>Course material <span className="muted">(PDF, TXT, DOCX or PPTX)</span>
                <select value={form.material} onChange={set('material')} required>
                  <option value="">Choose a file…</option>
                  {courseMaterials.map((m) => <option key={m.id} value={m.id}>{m.course_code} — {m.title} ({m.file_name})</option>)}
                </select>
                {!materials.length && <span className="muted small">Upload material on the <Link to="/courses">Courses</Link> page first.</span>}
              </label>
            )}
            <div className="grid-4">
              <label>Question type
                <select value={form.question_type} onChange={set('question_type')}>
                  <option value="mixed">Mixed</option>
                  {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              <label>How many
                <input type="number" min="1" max="30" value={form.count} onChange={set('count')} required />
              </label>
              <label>Difficulty (Bloom)
                <select value={form.difficulty} onChange={set('difficulty')}>
                  <option value="auto">Auto (classifier)</option>
                  {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <label>AI model
                <select value={form.quality} onChange={set('quality')}>
                  <option value="fast">Fast — T5-small</option>
                  <option value="better">Better — T5-base</option>
                </select>
              </label>
            </div>
            <div><button className="btn-primary btn-lg"><Sparkles size={17} /> Generate questions</button></div>
          </form>
        </section>
      )}

      {running && (
        <section className="panel center">
          <div className="spinner" aria-hidden="true" />
          <p><strong>{job.status_display}…</strong></p>
          <p className="muted">The model is reading your text. This usually takes 5–30 seconds; you can leave this page and you will get a notification when it is done.</p>
        </section>
      )}

      {job && !running && (
        <section className="panel">
          <div className="head-row">
            <h2>Review generated questions</h2>
            <span className="muted small">
              {job.course_code || 'No course'} · <Cpu size={12} style={{ verticalAlign: -1 }} /> {job.engine === 't5' ? `T5 (${job.quality === 'better' ? 'base' : 'small'})` : 'Rule-based'} · {fmtRelative(job.finished_at)}
            </span>
          </div>
          {job.status === 'failed' && <Alert type="error">{job.error}</Alert>}
          {job.status === 'done' && candidates.length === 0 && <Alert type="warn">{job.error}</Alert>}
          {saveResult && (
            <div className={saveResult.ok ? 'alert-ok' : 'alert-error'} style={{ marginBottom: '1rem' }}>
              {saveResult.ok
                ? <>Saved {saveResult.created} question{saveResult.created === 1 ? '' : 's'} to your bank. <Link to="/questions">Open question bank →</Link></>
                : saveResult.error}
              {saveResult.errors?.length > 0 && (
                <ul className="error-list">
                  {saveResult.errors.map((e) => (
                    <li key={e.index}>Question {e.index + 1}: {Object.entries(e.errors).map(([k, v]) => `${k} — ${[].concat(v).flat().map((x) => (typeof x === 'object' ? Object.values(x).join(' ') : x)).join(' ')}`).join('; ')}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {candidates.map((q, i) => (
            <div key={i} className={`q-card candidate ${selected.has(i) ? 'chosen' : ''}`}>
              <div className="q-head">
                <label className="check-row">
                  <input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} />
                  Question {i + 1}
                </label>
                <span><span className="tag tag-grey">{TYPE_LABEL[q.question_type]}</span> <span className="tag">{q.difficulty}</span> {q.marks} mark{q.marks > 1 ? 's' : ''}</span>
              </div>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>{q.text}</div>
              {q.question_type === 'mcq' && (
                <ul className="option-preview">
                  {q.options.map((o, j) => <li key={j} className={o.is_correct ? 'correct' : ''}>{o.text}</li>)}
                </ul>
              )}
              {q.question_type !== 'mcq' && <div className="feedback-line">Answer: <strong>{answerOf(q)}</strong></div>}
              {q.duplicate_of && (
                <div className="similar-box" style={{ marginBottom: 8 }}>
                  <AlertTriangle size={14} style={{ verticalAlign: -2 }} /> {q.duplicate_of.score}% similar to a question already in your bank:
                  {' '}<em>{q.duplicate_of.text}</em>
                </div>
              )}
              {q.source_sentence && <div className="muted small source-line">From: “{q.source_sentence}”</div>}
              <button className="link" onClick={() => setEditing(i)}><Pencil size={13} /> Edit</button>
            </div>
          ))}

          {candidates.length > 0 && (
            <div className="split-row">
              <span className="muted">{selected.size} of {candidates.length} selected</span>
              <button className="btn-primary" onClick={commit} disabled={!selected.size || saving}><Save size={16} />
                {saving ? 'Saving…' : `Add ${selected.size} to question bank`}
              </button>
            </div>
          )}
        </section>
      )}

      {jobs.length > 0 && (
        <section className="panel">
          <h2>Recent generations</h2>
          <table className="data-table">
            <thead><tr><th>When</th><th>Source</th><th>Type</th><th>Status</th><th>Saved</th><th></th></tr></thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{fmtDateTime(j.created_at)}</td>
                  <td className="q-text">{j.material_title || j.source_preview}</td>
                  <td>{j.question_type === 'mixed' ? 'Mixed' : TYPE_LABEL[j.question_type]} × {j.count}</td>
                  <td><span className={j.status === 'done' ? 'tag tag-green' : j.status === 'failed' ? 'tag tag-red' : 'tag tag-amber'}>{j.status_display}</span></td>
                  <td>{j.saved_count}</td>
                  <td><button className="link" onClick={() => setParams({ job: String(j.id) })}>Open</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {editing !== null && (
        <QuestionFormModal
          question={candidates[editing]}
          title="Edit generated question"
          submitLabel="Apply changes"
          onSave={saveEdit}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}
