import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ResultDetail from './ResultDetail.jsx'
import { ScoreRing, initials } from './ui.jsx'

const base = {
  exam_id: 1, exam_title: 'Quiz 1', course_code: 'CSC101', score: 3, total_marks: 6, percentage: 50,
  correct_count: 1, question_count: 3, class_average: 4, class_average_percentage: 66.7,
  submitted_at: '2026-10-01T10:00:00Z', auto_submitted: false, submit_reason: 'student', answers_revealed: true,
}
const q = (over) => ({
  exam_question_id: Math.random(), text: 'Q', question_type: 'mcq', marks: 2, awarded_marks: 0, is_correct: false,
  is_partial: false, similarity: null, grading_method: 'key', under_review: false, reviewed: false, review_note: '',
  answered: true, your_answer: 'A', correct_answer: 'B', missing_keywords: [], ...over,
})

describe('ResultDetail', () => {
  it('shows correct, partial and incorrect answers with feedback', () => {
    render(<ResultDetail result={{
      ...base,
      questions: [
        q({ text: 'Right one', is_correct: true, awarded_marks: 2, your_answer: 'B' }),
        q({ text: 'Close one', question_type: 'short_answer', is_partial: true, awarded_marks: 1, similarity: 83,
            grading_method: 'sentence-t5', missing_keywords: ['integrity'], under_review: true }),
        q({ text: 'Wrong one' }),
      ],
    }} />)
    expect(screen.getByText('Correct')).toBeInTheDocument()
    expect(screen.getByText('Partly correct')).toBeInTheDocument()
    expect(screen.getByText('Incorrect')).toBeInTheDocument()
    expect(screen.getByText(/Semantic similarity \(T5\) to the reference answer: 83%/)).toBeInTheDocument()
    expect(screen.getByText('integrity')).toBeInTheDocument()
    expect(screen.getByText('Under review')).toBeInTheDocument()
    expect(screen.getByText(/being reviewed by your instructor/)).toBeInTheDocument()
    // Correct answer only shown for questions the student got wrong.
    expect(screen.getAllByText('B').length).toBeGreaterThan(0)
  })

  it('hides answers until the exam closes and explains automatic submission', () => {
    render(<ResultDetail result={{ ...base, answers_revealed: false, submit_reason: 'time', questions: [q({ correct_answer: null })] }} />)
    expect(screen.getByText(/Answers hidden until the exam closes/)).toBeInTheDocument()
    expect(screen.getByText(/Time ran out/)).toBeInTheDocument()
    expect(screen.queryByText(/Correct answer:/)).not.toBeInTheDocument()
  })
})

describe('ui helpers', () => {
  it('builds initials for avatars', () => {
    expect(initials('Ayesha Malik')).toBe('AM')
    expect(initials('ali')).toBe('A')
  })

  it('renders a score ring with its label', () => {
    render(<ScoreRing percent={72.5} sub="29 / 40" />)
    expect(screen.getByText('72.5%')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '72.5%' })).toBeInTheDocument()
  })
})
