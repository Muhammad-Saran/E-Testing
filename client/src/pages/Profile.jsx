import { useState } from 'react'
import { KeyRound, Moon, Save, Sun, UserRound } from 'lucide-react'
import { api } from '../api/client.js'
import { Alert, Avatar, PageHeader } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { errorText } from '../utils/format.js'

export default function Profile() {
  const { user, updateUser } = useAuth()
  const { theme, toggle } = useTheme()
  const toast = useToast()
  const [form, setForm] = useState({ first_name: user.first_name || '', last_name: user.last_name || '',
    registration_number: user.registration_number || '' })
  const [pw, setPw] = useState({ current_password: '', new_password: '', new_password_confirm: '' })
  const [pwError, setPwError] = useState('')

  async function saveProfile(e) {
    e.preventDefault()
    try {
      const { data } = await api.patch('/auth/me/', form)
      updateUser(data)
      toast.ok('Profile updated')
    } catch (err) {
      toast.err('Could not save', errorText(err))
    }
  }

  async function changePassword(e) {
    e.preventDefault()
    setPwError('')
    try {
      await api.post('/auth/change-password/', pw)
      setPw({ current_password: '', new_password: '', new_password_confirm: '' })
      toast.ok('Password changed', 'A confirmation email has been sent.')
    } catch (err) {
      setPwError(errorText(err, 'Could not change the password.'))
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const setP = (k) => (e) => setPw({ ...pw, [k]: e.target.value })

  return (
    <div>
      <PageHeader icon={UserRound} title="My profile" subtitle="Your account details and security." />
      <div className="panel-row">
        <section className="panel">
          <div className="cell-user" style={{ marginBottom: '1.2rem' }}>
            <Avatar name={user.full_name || user.email} size="lg" />
            <div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{user.full_name}</div>
              <div className="muted">{user.email} · <span style={{ textTransform: 'capitalize' }}>{user.role}</span></div>
            </div>
          </div>
          <form className="stack" onSubmit={saveProfile}>
            <div className="grid-2">
              <label>First name<input value={form.first_name} onChange={set('first_name')} required /></label>
              <label>Last name<input value={form.last_name} onChange={set('last_name')} required /></label>
            </div>
            <label>{user.role === 'student' ? 'Registration number' : 'Employee ID'}
              <input value={form.registration_number} onChange={set('registration_number')} />
            </label>
            <div className="split-row">
              <button type="button" className="btn-ghost" onClick={toggle}>
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />} {theme === 'dark' ? 'Light' : 'Dark'} mode
              </button>
              <button className="btn-primary"><Save size={16} /> Save changes</button>
            </div>
          </form>
        </section>
        <section className="panel">
          <h2><KeyRound size={18} style={{ verticalAlign: -3, color: 'var(--primary)' }} /> Change password</h2>
          <form className="stack" onSubmit={changePassword}>
            {pwError && <Alert type="error">{pwError}</Alert>}
            <label>Current password<input type="password" autoComplete="current-password" value={pw.current_password} onChange={setP('current_password')} required /></label>
            <label>New password<input type="password" autoComplete="new-password" value={pw.new_password} onChange={setP('new_password')} minLength={8} required /></label>
            <label>Confirm new password<input type="password" autoComplete="new-password" value={pw.new_password_confirm} onChange={setP('new_password_confirm')} required /></label>
            <div><button className="btn-primary"><KeyRound size={16} /> Update password</button></div>
            <p className="muted small">After 5 failed sign-in attempts an account is locked for 15 minutes, and you are emailed about it.</p>
          </form>
        </section>
      </div>
    </div>
  )
}
