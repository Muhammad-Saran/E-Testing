import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, FileText, FlaskConical } from 'lucide-react'
import { api } from '../api/client.js'
import { EmptyState, PageHeader, SkeletonPanel } from '../components/ui.jsx'
import { downloadFile, fmtBytes, fmtDate } from '../utils/format.js'

const PRACTICABLE = ['.pdf', '.txt', '.docx', '.pptx']

export default function StudentMaterials() {
  const [materials, setMaterials] = useState(null)
  const [course, setCourse] = useState('')

  useEffect(() => { api.get('/courses/materials/').then((r) => setMaterials(r.data.results ?? r.data)) }, [])

  if (!materials) return <SkeletonPanel />

  const courses = [...new Map(materials.map((m) => [m.course, `${m.course_code} — ${m.course_title}`])).entries()]
  const shown = course ? materials.filter((m) => String(m.course) === course) : materials

  return (
    <div>
      <PageHeader icon={FileText} title="Course material" subtitle="Lecture notes and resources shared by your instructors."
                  actions={courses.length > 1 && (
                    <select value={course} onChange={(e) => setCourse(e.target.value)}>
                      <option value="">All courses</option>
                      {courses.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                    </select>
                  )} />
      {shown.length === 0 ? (
        <section className="panel"><EmptyState icon={FileText} title="No material yet" text="Your instructors have not uploaded anything for your courses." /></section>
      ) : (
        <div className="exam-card-grid">
          {shown.map((m) => (
            <div key={m.id} className="exam-card">
              <div className="split-row" style={{ alignItems: 'flex-start' }}>
                <div className="stat-icon" style={{ width: 42, height: 42 }}><FileText size={20} /></div>
                <span className="tag tag-grey">{m.file_name.split('.').pop().toUpperCase()}</span>
              </div>
              <div>
                <div className="course-code">{m.course_code}</div>
                <h3 style={{ margin: '0.15rem 0 0', fontSize: '1rem' }}>{m.title}</h3>
              </div>
              <div className="muted small">{fmtBytes(m.file_size)} · added {fmtDate(m.created_at)}</div>
              <div className="row-actions" style={{ marginTop: 'auto' }}>
                <button className="btn-ghost btn-sm" onClick={() => downloadFile(`/courses/materials/${m.id}/download/`, m.file_name)}>
                  <Download size={15} /> Download
                </button>
                {PRACTICABLE.some((ext) => m.file_name.toLowerCase().endsWith(ext)) && (
                  <Link className="btn-soft btn-sm" to={`/practice?material=${m.id}`}><FlaskConical size={15} /> Practise</Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
