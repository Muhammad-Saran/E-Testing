import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Mail, Send } from 'lucide-react'
import { api } from '../api/client.js'
import AuthLayout, { AuthBrand } from '../components/AuthLayout.jsx'
import { Alert } from '../components/ui.jsx'
import { errorText } from '../utils/format.js'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { data } = await api.post('/auth/password-reset/', { email })
      setSent(data.detail)
    } catch (err) {
      setError(errorText(err, 'Could not send the reset link.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <form className="stack" onSubmit={onSubmit}>
        <AuthBrand />
        <div>
          <h1>Reset your password</h1>
          <p className="muted">Enter your account email and we will send you a reset link. It works once and expires in an hour.</p>
        </div>
        {error && <Alert type="error">{error}</Alert>}
        {sent
          ? <Alert type="ok">{sent}</Alert>
          : (
            <>
              <label>Email
                <div className="input-icon"><Mail size={17} />
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
                </div>
              </label>
              <button className="btn-primary btn-lg btn-block" disabled={busy}><Send size={17} /> {busy ? 'Sending…' : 'Send reset link'}</button>
            </>
          )}
        <p className="auth-foot"><Link to="/login"><ArrowLeft size={14} style={{ verticalAlign: -2 }} /> Back to sign in</Link></p>
      </form>
    </AuthLayout>
  )
}
