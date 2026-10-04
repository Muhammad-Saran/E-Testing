import { CheckCircle2, CircleDashed, Clock, Eye, EyeOff, MinusCircle, Users, XCircle } from 'lucide-react'
import { fmtDateTime, SUBMIT_REASON } from '../utils/format.js'
import { Alert, ScoreRing } from './ui.jsx'

const METHOD_LABEL = {
  exact: 'Exact match',
  fuzzy: 'Spelling-tolerant match',
  'sentence-t5': 'Semantic similarity (T5)',
  lexical: 'Keyword similarity',
  numeric: 'Number match',
}

function Status({ q }) {
  if (q.is_correct) return <span className="tag tag-green"><CheckCircle2 size={13} /> Correct</span>
  if (q.is_partial) return <span className="tag tag-amber"><MinusCircle size={13} /> Partly correct</span>
  if (!q.answered) return <span className="tag tag-grey"><CircleDashed size={13} /> Not answered</span>
  return <span className="tag tag-red"><XCircle size={13} /> Incorrect</span>
}

// Result summary + question-level feedback for one submitted exam (Module 6).
export default function ResultDetail({ result }) {
  const r = result
  const diff = r.class_average_percentage != null ? Math.round((r.percentage - r.class_average_percentage) * 10) / 10 : null
  const reviewing = r.questions.filter((q) => q.under_review).length

  return (
    <div>
      <section className="panel">
        <div className="hero-row" style={{ gap: '2rem', justifyContent: 'flex-start' }}>
          <ScoreRing percent={r.percentage} size={150} sub={`${r.score} / ${r.total_marks} marks`} />
          <div style={{ flex: 1, minWidth: 240 }}>
            <div className="course-code">{r.course_code}</div>
            <h2 style={{ fontSize: '1.35rem', margin: '0.2rem 0 0.4rem' }}>{r.exam_title}</h2>
            <p className="muted">{r.correct_count} of {r.question_count} questions correct · submitted {fmtDateTime(r.submitted_at)}</p>
            <div className="grid-3" style={{ marginTop: '1rem', maxWidth: 520 }}>
              <div className="quote"><div className="label">You</div><strong style={{ fontSize: '1.2rem' }}>{r.percentage}%</strong></div>
              <div className="quote"><div className="label"><Users size={11} /> Class average</div>
                <strong style={{ fontSize: '1.2rem' }}>{r.class_average_percentage ?? '—'}{r.class_average_percentage != null && '%'}</strong></div>
              <div className="quote"><div className="label">Difference</div>
                <strong style={{ fontSize: '1.2rem', color: diff == null ? undefined : diff >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                  {diff == null ? '—' : `${diff >= 0 ? '+' : ''}${diff}`}
                </strong></div>
            </div>
            {r.submit_reason && r.submit_reason !== 'student' && (
              <p className="muted small" style={{ marginTop: 10 }}><Clock size={13} style={{ verticalAlign: -2 }} /> {SUBMIT_REASON[r.submit_reason]} — submitted automatically.</p>
            )}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="head-row">
          <h2>Question feedback</h2>
          <span className="tag tag-grey">{r.answers_revealed ? <><Eye size={13} /> Answers revealed</> : <><EyeOff size={13} /> Answers hidden until the exam closes</>}</span>
        </div>
        {reviewing > 0 && <Alert type="info" className="mb">{reviewing} short answer{reviewing > 1 ? 's are' : ' is'} being reviewed by your instructor. Your marks may change.</Alert>}
        {r.questions.map((q, i) => (
          <div key={q.exam_question_id} className={`q-card feedback ${q.is_correct ? 'right' : q.is_partial ? 'partial' : 'wrong'}`}>
            <div className="q-head">
              <span>Question {i + 1}</span>
              <strong style={{ color: 'var(--text-2)' }}>{q.awarded_marks} / {q.marks} mark{q.marks > 1 ? 's' : ''}</strong>
            </div>
            <div className="q-title" style={{ marginBottom: '0.5rem' }}>{q.text}</div>
            <div className="feedback-line">
              <Status q={q} />
              {q.under_review && <span className="tag tag-blue">Under review</span>}
              {q.reviewed && <span className="tag tag-purple">Reviewed by instructor</span>}
              {q.answered && <span>Your answer: <strong>{q.your_answer}</strong></span>}
            </div>
            {q.question_type === 'short_answer' && q.answered && q.similarity != null && (
              <div className="feedback-line muted small">{METHOD_LABEL[q.grading_method] || 'Similarity'} to the reference answer: {q.similarity}%</div>
            )}
            {q.missing_keywords?.length > 0 && (
              <div className="feedback-line muted small">Missing key terms: {q.missing_keywords.map((k) => <span key={k} className="tag tag-amber">{k}</span>)}</div>
            )}
            {q.review_note && <div className="feedback-line small">Instructor note: <em>{q.review_note}</em></div>}
            {r.answers_revealed && !q.is_correct && q.correct_answer && (
              <div className="feedback-line" style={{ color: 'var(--success)' }}>Correct answer: <strong>{q.correct_answer}</strong></div>
            )}
          </div>
        ))}
      </section>
    </div>
  )
}
