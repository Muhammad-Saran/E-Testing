import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const user = await login(email, password)
      navigate(user.role === 'instructor' ? '/instructor' : '/student')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid email or password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="brand-lg">e-Testing</div>
        <h1>Welcome back</h1>
        <p className="muted">Sign in to your examination portal.</p>

        {error && <div className="alert-error">{error}</div>}

        <label>Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                 placeholder="you@cuiatd.edu.pk" required />
        </label>
        <label>Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 placeholder="••••••••" required />
        </label>

        <button className="btn-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="muted center">No account? <Link to="/register">Create one</Link></p>
      </form>
    </div>
  )
}
