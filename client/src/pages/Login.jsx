import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, LogIn, Mail } from 'lucide-react'
import { api } from '../api/client.js'
import AuthLayout, { AuthBrand } from '../components/AuthLayout.jsx'
import { Alert } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const DEMO = [
  { label: 'Instructor', email: 'instructor@demo.edu' },
  { label: 'Student', email: 'student@demo.edu' },
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [demo, setDemo] = useState(false)

  useEffect(() => {
    api.get('/health/').then((r) => setDemo(Boolean(r.data.demo_accounts))).catch(() => {})
  }, [])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const user = await login(email, password)
      navigate(user.role === 'instructor' ? '/instructor' : '/student')
    } catch (err) {
      setError(err.response?.data?.detail || (err.response ? 'Invalid email or password.' : 'Cannot reach the server.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <form className="stack" onSubmit={onSubmit}>
        <AuthBrand />
        <div>
          <h1>Welcome back</h1>
          <p className="muted">Sign in to your examination portal.</p>
        </div>

        {error && <Alert type="error">{error}</Alert>}

        <label>Email
          <div className="input-icon"><Mail size={17} />
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username"
                   placeholder="you@cuiatd.edu.pk" required autoFocus />
          </div>
        </label>
        <label>Password
          <div className="input-icon"><Lock size={17} />
            <input type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                   autoComplete="current-password" placeholder="••••••••" required style={{ paddingRight: '2.6rem' }} />
            <button type="button" className="link" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}
                    style={{ position: 'absolute', right: '0.75rem', color: 'var(--faint)' }}>
              {show ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
        </label>

        <div className="form-hint"><Link to="/forgot-password">Forgot password?</Link></div>

        <button className="btn-primary btn-lg btn-block" disabled={busy}>
          <LogIn size={18} /> {busy ? 'Signing in…' : 'Sign in'}
        </button>

        {demo && (
          <div className="demo-box">
            <strong style={{ color: 'var(--text)' }}>Demo accounts</strong> · password <code>Demo@12345</code>
            <div style={{ marginTop: 6 }}>
              {DEMO.map((d) => (
                <button key={d.email} type="button" className="btn-soft btn-sm"
                        onClick={() => { setEmail(d.email); setPassword('Demo@12345') }}>{d.label}</button>
              ))}
            </div>
          </div>
        )}
        <p className="auth-foot">No account? <Link to="/register">Create one</Link></p>
      </form>
    </AuthLayout>
  )
}
