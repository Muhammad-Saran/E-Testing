import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const BLANK_COURSE = { code: '', title: '', description: '' }

export default function Courses() {
  const [courses, setCourses] = useState([])
  const [selected, setSelected] = useState(null)
  const [roster, setRoster] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [newCourse, setNewCourse] = useState(BLANK_COURSE)
  const [createError, setCreateError] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [enrollMsg, setEnrollMsg] = useState(null) // { type: 'ok'|'err', text }

  function loadCourses(selectId) {
    api.get('/courses/').then((r) => {
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
    setEnrollMsg(null)
    setIdentifier('')
    api.get(`/courses/${course.id}/roster/`).then((r) => setRoster(r.data))
  }

  async function createCourse(e) {
    e.preventDefault()
    setCreateError('')
    try {
      const { data } = await api.post('/courses/', newCourse)
      setShowCreate(false)
      setNewCourse(BLANK_COURSE)
      loadCourses(data.id)
    } catch (err) {
      const d = err.response?.data
      setCreateError(typeof d === 'object' ? Object.values(d).flat().join(' ') : 'Could not create course.')
    }
  }

  async function enroll(e) {
    e.preventDefault()
    setEnrollMsg(null)
    try {
      const { data } = await api.post(`/courses/${selected.id}/enroll/`, { identifier: identifier.trim() })
      setRoster([...roster, data])
      setIdentifier('')
      setEnrollMsg({ type: 'ok', text: `Enrolled ${data.full_name}.` })
      setCourses(courses.map((c) => (c.id === selected.id ? { ...c, enrolled_count: (c.enrolled_count || 0) + 1 } : c)))
    } catch (err) {
      setEnrollMsg({ type: 'err', text: err.response?.data?.detail || 'Could not enroll student.' })
    }
  }

  async function removeStudent(studentId, name) {
    if (!confirm(`Remove ${name} from ${selected.code}?`)) return
    await api.post(`/courses/${selected.id}/unenroll/`, { student_id: studentId })
    setRoster(roster.filter((s) => s.id !== studentId))
    setCourses(courses.map((c) => (c.id === selected.id ? { ...c, enrolled_count: Math.max(0, (c.enrolled_count || 1) - 1) } : c)))
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Courses</h1>
          <p className="muted">Create courses and enroll your students.</p>
        </div>
        <button className="btn-primary" onClick={() => { setShowCreate(true); setCreateError('') }}>+ New Course</button>
      </header>

      <div className="panel-row" style={{ gridTemplateColumns: '1fr 1.4fr', alignItems: 'start' }}>
        {/* Course list */}
        <section className="panel">
          <h2>My courses</h2>
          {courses.length === 0
            ? <p className="muted">No courses yet. Create your first one.</p>
            : (
              <ul className="plain-list">
                {courses.map((c) => (
                  <li key={c.id} style={{ cursor: 'pointer', justifyContent: 'space-between',
                        background: selected?.id === c.id ? 'var(--bg)' : 'transparent', borderRadius: 8, padding: '0.7rem 0.6rem' }}
                      onClick={() => selectCourse(c)}>
                    <span><strong style={{ color: 'var(--primary)' }}>{c.code}</strong> — {c.title}</span>
                    <span className="tag">{c.enrolled_count ?? 0} students</span>
                  </li>
                ))}
              </ul>
            )}
        </section>

        {/* Roster / enrollment for the selected course */}
        <section className="panel">
          {!selected
            ? <p className="muted">Select a course to manage its students.</p>
            : (
              <>
                <h2>{selected.code} — {selected.title}</h2>

                <form onSubmit={enroll} className="toolbar" style={{ marginBottom: '0.5rem' }}>
                  <input className="search" placeholder="Student email or registration number"
                         value={identifier} onChange={(e) => setIdentifier(e.target.value)} required />
                  <button className="btn-primary" type="submit">Enroll</button>
                </form>
                {enrollMsg && (
                  <div className={enrollMsg.type === 'ok' ? 'alert-ok' : 'alert-error'} style={{ marginBottom: '1rem' }}>
                    {enrollMsg.text}
                  </div>
                )}

                {roster.length === 0
                  ? <p className="muted">No students enrolled yet.</p>
                  : (
                    <table className="data-table">
                      <thead>
                        <tr><th>Name</th><th>Email</th><th>Reg #</th><th></th></tr>
                      </thead>
                      <tbody>
                        {roster.map((s) => (
                          <tr key={s.id}>
                            <td>{s.full_name}</td>
                            <td>{s.email}</td>
                            <td>{s.registration_number || '—'}</td>
                            <td className="row-actions">
                              <button className="link danger" onClick={() => removeStudent(s.id, s.full_name)}>Remove</button>
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

      {showCreate && (
        <div className="modal-backdrop" onClick={() => setShowCreate(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={createCourse}>
            <h2>New Course</h2>
            {createError && <div className="alert-error">{createError}</div>}
            <label>Course code
              <input value={newCourse.code} onChange={(e) => setNewCourse({ ...newCourse, code: e.target.value })}
                     placeholder="e.g. CSC336" required />
            </label>
            <label>Title
              <input value={newCourse.title} onChange={(e) => setNewCourse({ ...newCourse, title: e.target.value })}
                     placeholder="e.g. Web Technologies" required />
            </label>
            <label>Description <span className="muted">(optional)</span>
              <textarea rows={3} value={newCourse.description}
                        onChange={(e) => setNewCourse({ ...newCourse, description: e.target.value })} />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn-primary" type="submit">Create course</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
