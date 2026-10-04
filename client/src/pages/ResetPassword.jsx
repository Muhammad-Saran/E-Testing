import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { KeyRound } from 'lucide-react'
import { api } from '../api/client.js'
import AuthLayout, { AuthBrand } from '../components/AuthLayout.jsx'
import { Alert } from '../components/ui.jsx'
import { errorText } from '../utils/format.js'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const uid = params.get('uid') || ''
  const token = params.get('token') || ''
  const [form, setForm] = useState({ password: '', password_confirm: '' })
  const [done, setDone] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { data } = await api.post('/auth/password-reset/confirm/', { uid, token, ...form })
      setDone(data.detail)
    } catch (err) {
      setError(errorText(err, 'Could not reset the password.'))
    } finally {
      setBusy(false)
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <AuthLayout>
      <form className="stack" onSubmit={onSubmit}>
        <AuthBrand />
        <div>
          <h1>Choose a new password</h1>
          <p className="muted">At least 8 characters, not too common, and not similar to your name or email.</p>
        </div>
        {!uid || !token
          ? <Alert type="error">This link is incomplete. Request a new one.</Alert>
          : done
            ? <Alert type="ok">{done}</Alert>
            : (
              <>
                {error && <Alert type="error">{error}</Alert>}
                <label>New password
                  <input type="password" value={form.password} onChange={set('password')} minLength={8} autoComplete="new-password" required autoFocus />
                </label>
                <label>Confirm new password
                  <input type="password" value={form.password_confirm} onChange={set('password_confirm')} autoComplete="new-password" required />
                </label>
                <button className="btn-primary btn-lg btn-block" disabled={busy}><KeyRound size={17} /> {busy ? 'Saving…' : 'Set password'}</button>
              </>
            )}
        <p className="auth-foot">
          {done ? <Link to="/login">Sign in now</Link> : <Link to="/forgot-password">Request a new link</Link>}
        </p>
      </form>
    </AuthLayout>
  )
}
