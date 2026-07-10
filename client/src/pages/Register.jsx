import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

const EMPTY = {
  first_name: '', last_name: '', email: '', registration_number: '',
  role: 'student', password: '', password_confirm: '',
}

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function onSubmit(e) {
    e.preventDefault()
    setErrors({})
    setBusy(true)
    try {
      const user = await register(form)
      navigate(user.role === 'instructor' ? '/instructor' : '/student')
    } catch (err) {
      const data = err.response?.data
      setErrors(typeof data === 'object' ? data : { detail: 'Registration failed.' })
    } finally {
      setBusy(false)
    }
  }

  const fieldError = (k) => errors[k] && <span className="field-error">{errors[k]}</span>

  return (
    <div className="auth-screen">
      <form className="auth-card wide" onSubmit={onSubmit}>
        <div className="brand-lg">e-Testing</div>
        <h1>Create your account</h1>
        <p className="muted">Register as an instructor or student.</p>

        {errors.detail && <div className="alert-error">{errors.detail}</div>}

        <div className="role-toggle">
          {['student', 'instructor'].map((r) => (
            <button type="button" key={r}
                    className={form.role === r ? 'active' : ''}
                    onClick={() => setForm({ ...form, role: r })}>
              {r === 'student' ? 'Student' : 'Instructor'}
            </button>
          ))}
        </div>

        <div className="grid-2">
          <label>First name
            <input value={form.first_name} onChange={set('first_name')} required />
          </label>
          <label>Last name
            <input value={form.last_name} onChange={set('last_name')} required />
          </label>
        </div>

        <label>Email
          <input type="email" value={form.email} onChange={set('email')} required />
          {fieldError('email')}
        </label>
        <label>Registration number <span className="muted">(optional)</span>
          <input value={form.registration_number} onChange={set('registration_number')}
                 placeholder="CIIT/FA22-BCS-000" />
        </label>

        <div className="grid-2">
          <label>Password
            <input type="password" value={form.password} onChange={set('password')} required />
            {fieldError('password')}
          </label>
          <label>Confirm password
            <input type="password" value={form.password_confirm} onChange={set('password_confirm')} required />
            {fieldError('password_confirm')}
          </label>
        </div>

        <button className="btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
        <p className="muted center">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  )
}
