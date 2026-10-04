import { useEffect, useRef, useState } from 'react'
import {
  BookOpen, Download, FileSpreadsheet, FileText, FileUp, Plus, Search, Trash2, UserPlus, Users,
} from 'lucide-react'
import { api } from '../api/client.js'
import { Alert, Avatar, EmptyState, PageHeader, Tabs } from '../components/ui.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { downloadFile, downloadText, errorText, fmtBytes, fmtDate } from '../utils/format.js'

const BLANK_COURSE = { code: '', title: '', description: '' }
const CSV_TEMPLATE = 'email,first_name,last_name,registration_number\nali.raza@cuiatd.edu.pk,Ali,Raza,FA22-BCS-001\n'

function BulkEnroll({ course, onDone, onClose }) {
  const [file, setFile] = useState(null)
  const [createMissing, setCreateMissing] = useState(true)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    const form = new FormData()
    form.append('file', file)
    form.append('create_missing', createMissing ? 'true' : 'false')
    try {
      const { data } = await api.post(`/courses/${course.id}/enroll_csv/`, form)
      setReport(data)
      onDone()
    } catch (err) {
      setError(errorText(err, 'Import failed.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>Enroll a class from CSV</h2>
        <p className="muted" style={{ margin: 0 }}>
          One student per row with an <code>email</code> and/or <code>registration_number</code> column; <code>first_name</code> and{' '}
          <code>last_name</code> are optional. <button type="button" className="link" onClick={() => downloadText(CSV_TEMPLATE, 'class-list-template.csv')}>Download template</button>
        </p>
        {error && <Alert type="error">{error}</Alert>}
        {report ? (
          <>
            <div className="grid-3">
              <div className="quote"><div className="label">Enrolled</div><strong style={{ fontSize: '1.3rem' }}>{report.enrolled}</strong></div>
              <div className="quote"><div className="label">New accounts</div><strong style={{ fontSize: '1.3rem' }}>{report.created}</strong></div>
              <div className="quote"><div className="label">Already enrolled</div><strong style={{ fontSize: '1.3rem' }}>{report.already}</strong></div>
            </div>
            {report.created > 0 && <Alert type="ok">New students were emailed a link to choose their password.</Alert>}
            {report.not_found.length > 0 && <Alert type="warn">Not found ({report.not_found.length}): {report.not_found.join(', ')}</Alert>}
            {report.errors.length > 0 && (
              <Alert type="error">
                <ul className="error-list" style={{ margin: 0 }}>{report.errors.map((x) => <li key={x.row}>Row {x.row}: {x.error}</li>)}</ul>
              </Alert>
            )}
            <div className="modal-actions"><button type="button" className="btn-primary" onClick={onClose}>Done</button></div>
          </>
        ) : (
          <>
            <label>Class list (.csv)
              <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
            </label>
            <label className="check-row">
              <input type="checkbox" checked={createMissing} onChange={(e) => setCreateMissing(e.target.checked)} />
              Create accounts for students who have not registered yet (they get an email invite)
            </label>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn-primary" disabled={busy || !file}><FileUp size={16} /> {busy ? 'Importing…' : 'Import'}</button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}

export default function Courses() {
  const toast = useToast()
  const [courses, setCourses] = useState(null)
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState('students')
  const [roster, setRoster] = useState([])
  const [filter, setFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showBulk, setShowBulk] = useState(false)
  const [newCourse, setNewCourse] = useState(BLANK_COURSE)
  const [createError, setCreateError] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [materials, setMaterials] = useState([])
  const [materialTitle, setMaterialTitle] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef(null)

  function loadCourses(selectId) {
    api.get('/courses/', { params: { page_size: 100 } }).then((r) => {
      const list = r.data.results ?? r.data
      setCourses(list)
      const pick = selectId ? list.find((c) => c.id === selectId) : (selected ? list.find((c) => c.id === selected.id) : list[0])
      if (pick) selectCourse(pick)
      else if (list.length === 0) { setSelected(null); setRoster([]) }
    })
  }
  useEffect(() => { loadCourses() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function selectCourse(course) {
    setSelected(course)
    setIdentifier('')
    setFilter('')
    api.get(`/courses/${course.id}/roster/`).then((r) => setRoster(r.data))
    api.get('/courses/materials/', { params: { course: course.id } }).then((r) => setMaterials(r.data.results ?? r.data))
  }
  const refreshRoster = () => {
    api.get(`/courses/${selected.id}/roster/`).then((r) => {
      setRoster(r.data)
      setCourses((list) => list.map((c) => (c.id === selected.id ? { ...c, enrolled_count: r.data.length } : c)))
    })
  }

  async function uploadMaterial(e) {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('course', selected.id)
    form.append('title', materialTitle.trim())
    form.append('file', file)
    setUploading(true)
    try {
      await api.post('/courses/materials/', form)
      setMaterialTitle('')
      e.target.reset()
      toast.ok('Material uploaded', 'Enrolled students can download it now.')
      api.get('/courses/materials/', { params: { course: selected.id } }).then((r) => setMaterials(r.data.results ?? r.data))
    } catch (err) {
      toast.err('Upload failed', errorText(err))
    } finally {
      setUploading(false)
    }
  }

  async function deleteMaterial(m) {
    if (!confirm(`Delete "${m.title}"?`)) return
    await api.delete(`/courses/materials/${m.id}/`)
    setMaterials(materials.filter((x) => x.id !== m.id))
  }

  async function createCourse(e) {
    e.preventDefault()
    setCreateError('')
    try {
      const { data } = await api.post('/courses/', newCourse)
      setShowCreate(false)
      setNewCourse(BLANK_COURSE)
      toast.ok('Course created', `${data.code} — ${data.title}`)
      loadCourses(data.id)
    } catch (err) {
      setCreateError(errorText(err, 'Could not create the course.'))
    }
  }

  async function enroll(e) {
    e.preventDefault()
    try {
      const { data } = await api.post(`/courses/${selected.id}/enroll/`, { identifier: identifier.trim() })
      setIdentifier('')
      toast.ok('Student enrolled', data.full_name)
      refreshRoster()
    } catch (err) {
      toast.err('Could not enroll', errorText(err))
    }
  }

  async function removeStudent(studentId, name) {
    if (!confirm(`Remove ${name} from ${selected.code}?`)) return
    await api.post(`/courses/${selected.id}/unenroll/`, { student_id: studentId })
    refreshRoster()
  }

  const shown = roster.filter((s) => `${s.full_name} ${s.email} ${s.registration_number}`.toLowerCase().includes(filter.toLowerCase()))

  return (
    <div>
      <PageHeader icon={BookOpen} title="Courses & students" subtitle="Create courses, enroll your class and share material."
                  actions={<button className="btn-primary" onClick={() => { setShowCreate(true); setCreateError('') }}><Plus size={17} /> New course</button>} />

      <div className="panel-row" style={{ gridTemplateColumns: 'minmax(260px, 1fr) 2.2fr', alignItems: 'start' }}>
        <section className="panel">
          <h2>My courses</h2>
          {courses?.length === 0 && <EmptyState icon={BookOpen} title="No courses yet" text="Create your first course." />}
          <ul className="plain-list">
            {courses?.map((c) => (
              <li key={c.id} className={`select-row ${selected?.id === c.id ? 'selected' : ''}`} onClick={() => { selectCourse(c); setTab('students') }}>
                <span>
                  <span className="course-code">{c.code}</span>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{c.title}</div>
                </span>
                <span className="tag tag-grey"><Users size={12} /> {c.enrolled_count ?? 0}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          {!selected ? <EmptyState icon={BookOpen} title="Select a course" text="Pick a course to manage its students and material." /> : (
            <>
              <div className="head-row">
                <div>
                  <span className="course-code">{selected.code}</span>
                  <h2 style={{ marginTop: 2 }}>{selected.title}</h2>
                  {selected.description && <p className="muted small">{selected.description}</p>}
                </div>
              </div>
              <Tabs active={tab} onChange={setTab} tabs={[
                { id: 'students', label: 'Students', icon: Users, count: roster.length },
                { id: 'material', label: 'Material', icon: FileText, count: materials.length },
              ]} />

              {tab === 'students' && (
                <>
                  <div className="toolbar">
                    <form onSubmit={enroll} className="row-actions" style={{ flex: 1 }}>
                      <input className="search" style={{ flex: 1, minWidth: 220 }} placeholder="Student email or registration number"
                             value={identifier} onChange={(e) => setIdentifier(e.target.value)} required />
                      <button className="btn-primary" type="submit"><UserPlus size={16} /> Enroll</button>
                    </form>
                    <button className="btn-ghost" onClick={() => setShowBulk(true)}><FileSpreadsheet size={16} /> Import CSV</button>
                  </div>
                  {roster.length > 5 && (
                    <div className="input-icon" style={{ marginBottom: '0.8rem' }}>
                      <Search size={16} />
                      <input placeholder="Filter students…" value={filter} onChange={(e) => setFilter(e.target.value)} />
                    </div>
                  )}
                  {roster.length === 0
                    ? <EmptyState icon={Users} title="No students yet" text="Enroll students one by one, or import the whole class from a CSV file." />
                    : (
                      <div className="table-scroll">
                        <table className="data-table">
                          <thead><tr><th>Student</th><th>Reg #</th><th>Enrolled</th><th /></tr></thead>
                          <tbody>
                            {shown.map((s) => (
                              <tr key={s.id}>
                                <td>
                                  <div className="cell-user"><Avatar name={s.full_name} />
                                    <span><strong style={{ fontSize: '0.88rem' }}>{s.full_name}</strong><div className="muted small">{s.email}</div></span>
                                  </div>
                                </td>
                                <td className="small">{s.registration_number || '—'}</td>
                                <td className="small">{fmtDate(s.enrolled_at)}</td>
                                <td><button className="link danger" onClick={() => removeStudent(s.id, s.full_name)}>Remove</button></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                </>
              )}

              {tab === 'material' && (
                <>
                  <form onSubmit={uploadMaterial} className="toolbar">
                    <input className="search" placeholder="Title, e.g. Lecture 3 — Trees" value={materialTitle}
                           onChange={(e) => setMaterialTitle(e.target.value)} required />
                    <input type="file" ref={fileRef} accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.zip" required />
                    <button className="btn-primary" type="submit" disabled={uploading}><FileUp size={16} /> {uploading ? 'Uploading…' : 'Upload'}</button>
                  </form>
                  <p className="muted small" style={{ marginTop: -6 }}>PDF, Word, PowerPoint, Excel, text or zip — up to 20 MB. PDF/TXT/DOCX/PPTX can feed the AI generator.</p>
                  {materials.length === 0
                    ? <EmptyState icon={FileText} title="No material yet" text="Upload lecture notes for your students — and generate questions from them." />
                    : (
                      <table className="data-table">
                        <thead><tr><th>Title</th><th>File</th><th>Uploaded</th><th /></tr></thead>
                        <tbody>
                          {materials.map((m) => (
                            <tr key={m.id}>
                              <td><strong style={{ fontSize: '0.9rem' }}>{m.title}</strong></td>
                              <td className="small">{m.file_name}<div className="muted">{fmtBytes(m.file_size)}</div></td>
                              <td className="small">{fmtDate(m.created_at)}</td>
                              <td className="row-actions">
                                <button className="icon-btn" title="Download" onClick={() => downloadFile(`/courses/materials/${m.id}/download/`, m.file_name)}><Download size={16} /></button>
                                <button className="icon-btn" title="Delete" onClick={() => deleteMaterial(m)}><Trash2 size={16} color="var(--danger)" /></button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                </>
              )}
            </>
          )}
        </section>
      </div>

      {showCreate && (
        <div className="modal-backdrop" onClick={() => setShowCreate(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={createCourse}>
            <h2>New course</h2>
            {createError && <Alert type="error">{createError}</Alert>}
            <div className="grid-2">
              <label>Course code
                <input value={newCourse.code} onChange={(e) => setNewCourse({ ...newCourse, code: e.target.value })} placeholder="e.g. CSC336" required />
              </label>
              <label>Title
                <input value={newCourse.title} onChange={(e) => setNewCourse({ ...newCourse, title: e.target.value })} placeholder="e.g. Web Technologies" required />
              </label>
            </div>
            <label>Description <span className="muted">(optional)</span>
              <textarea rows={3} value={newCourse.description} onChange={(e) => setNewCourse({ ...newCourse, description: e.target.value })} />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn-primary" type="submit">Create course</button>
            </div>
          </form>
        </div>
      )}
      {showBulk && selected && <BulkEnroll course={selected} onDone={refreshRoster} onClose={() => setShowBulk(false)} />}
    </div>
  )
}
