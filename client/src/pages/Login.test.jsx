import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Login from './Login.jsx'

const login = vi.fn()
const navigate = vi.fn()

vi.mock('../api/client.js', () => ({ api: { get: vi.fn(() => Promise.resolve({ data: { demo_accounts: true } })) } }))
vi.mock('../context/AuthContext.jsx', () => ({ useAuth: () => ({ login }) }))
vi.mock('react-router-dom', async (orig) => ({ ...(await orig()), useNavigate: () => navigate }))

const renderLogin = () => render(<MemoryRouter><Login /></MemoryRouter>)

describe('Login page', () => {
  beforeEach(() => { login.mockReset(); navigate.mockReset() })

  it('signs in and routes instructors to their dashboard', async () => {
    login.mockResolvedValue({ role: 'instructor' })
    renderLogin()
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.edu')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(login).toHaveBeenCalledWith('a@b.edu', 'secret123')
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/instructor'))
  })

  it('shows the server message on failure (e.g. a locked account)', async () => {
    login.mockRejectedValue({ response: { data: { detail: 'Too many failed sign-in attempts.' } } })
    renderLogin()
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.edu')
    await userEvent.type(screen.getByLabelText('Password'), 'x')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText('Too many failed sign-in attempts.')).toBeInTheDocument()
  })

  it('offers demo logins when demo data exists', async () => {
    renderLogin()
    await userEvent.click(await screen.findByRole('button', { name: 'Student' }))
    expect(screen.getByLabelText('Email')).toHaveValue('student@demo.edu')
    expect(screen.getByLabelText('Password')).toHaveValue('Demo@12345')
  })
})
