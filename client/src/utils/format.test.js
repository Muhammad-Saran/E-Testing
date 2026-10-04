import { describe, expect, it } from 'vitest'
import { errorText, fmtClock, fmtCountdown, fmtRelative, stateClass } from './format.js'

describe('format helpers', () => {
  it('formats the exam clock', () => {
    expect(fmtClock(65)).toBe('1:05')
    expect(fmtClock(3725)).toBe('1:02:05')
    expect(fmtClock(0)).toBe('0:00')
  })

  it('formats countdowns to an exam', () => {
    expect(fmtCountdown(-1)).toBe('now')
    expect(fmtCountdown(30 * 1000)).toBe('in 1m')
    expect(fmtCountdown((2 * 60 + 5) * 60 * 1000)).toBe('in 2h 5m')
    expect(fmtCountdown((26 * 60) * 60 * 1000)).toBe('in 1d 2h')
  })

  it('formats relative times', () => {
    expect(fmtRelative(new Date())).toBe('just now')
    expect(fmtRelative(new Date(Date.now() - 5 * 60 * 1000))).toBe('5 min ago')
    expect(fmtRelative(new Date(Date.now() - 3 * 3600 * 1000))).toBe('3 h ago')
  })

  it('turns DRF errors into one readable line', () => {
    expect(errorText({ response: { data: { detail: 'Nope.' } } })).toBe('Nope.')
    expect(errorText({ response: { data: { email: ['Taken.'], password: ['Too short.'] } } })).toBe('Taken. Too short.')
    expect(errorText({ response: { data: { options: [{ text: ['Required.'] }] } } })).toBe('Required.')
    expect(errorText({}, 'x')).toMatch(/Cannot reach the server/)
  })

  it('maps exam states to tag styles', () => {
    expect(stateClass('active')).toContain('tag-green')
    expect(stateClass('scheduled')).toContain('tag-amber')
  })
})
