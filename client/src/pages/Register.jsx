import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { GraduationCap, Presentation, UserPlus } from 'lucide-react'
import AuthLayout, { AuthBrand } from '../components/AuthLayout.jsx'
import { Alert } from '../components/ui.jsx'
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
      setErrors(typeof data === 'object' && data ? data : { detail: 'Registration failed.' })
    } finally {
      setBusy(false)
    }
  }

  const fieldError = (k) => errors[k] && <span className="field-error">{[].concat(errors[k]).join(' ')}</span>

  return (
    <AuthLayout wide>
      <form className="stack" onSubmit={onSubmit}>
        <AuthBrand />
        <div>
          <h1>Create your account</h1>
          <p className="muted">Use your institutional email address.</p>
        </div>

        {errors.detail && <Alert type="error">{errors.detail}</Alert>}

        <div className="role-toggle">
          <button type="button" className={form.role === 'student' ? 'active' : ''} onClick={() => setForm({ ...form, role: 'student' })}>
            <GraduationCap size={18} /> Student
          </button>
          <button type="button" className={form.role === 'instructor' ? 'active' : ''} onClick={() => setForm({ ...form, role: 'instructor' })}>
            <Presentation size={18} /> Instructor
          </button>
        </div>

        <div className="grid-2">
          <label>First name<input value={form.first_name} onChange={set('first_name')} required /></label>
          <label>Last name<input value={form.last_name} onChange={set('last_name')} required /></label>
        </div>
        <label>Email
          <input type="email" value={form.email} onChange={set('email')} placeholder="you@cuiatd.edu.pk" required />
          {fieldError('email')}
        </label>
        <label>{form.role === 'student' ? 'Registration number' : 'Employee ID'} <span className="muted">(optional)</span>
          <input value={form.registration_number} onChange={set('registration_number')}
                 placeholder={form.role === 'student' ? 'CIIT/FA22-BCS-000' : 'EMP-0000'} />
        </label>
        <div className="grid-2">
          <label>Password
            <input type="password" value={form.password} onChange={set('password')} autoComplete="new-password" required />
            {fieldError('password')}
          </label>
          <label>Confirm password
            <input type="password" value={form.password_confirm} onChange={set('password_confirm')} autoComplete="new-password" required />
            {fieldError('password_confirm')}
          </label>
        </div>

        <button className="btn-primary btn-lg btn-block" disabled={busy}><UserPlus size={18} /> {busy ? 'Creating…' : 'Create account'}</button>
        <p className="auth-foot">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </AuthLayout>
  )
}
