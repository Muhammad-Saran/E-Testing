import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import StudentDashboard from './pages/StudentDashboard.jsx'
import InstructorDashboard from './pages/InstructorDashboard.jsx'
import QuestionBank from './pages/QuestionBank.jsx'

// Send a logged-in user to the dashboard matching their role.
function HomeRedirect() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'instructor' ? '/instructor' : '/student'} replace />
}

export default function App() {
  const { loading } = useAuth()
  if (loading) return <div className="center-screen">Loading…</div>

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<Layout />}>
        <Route
          path="/instructor"
          element={<ProtectedRoute role="instructor"><InstructorDashboard /></ProtectedRoute>}
        />
        <Route
          path="/questions"
          element={<ProtectedRoute role="instructor"><QuestionBank /></ProtectedRoute>}
        />
        <Route
          path="/student"
          element={<ProtectedRoute role="student"><StudentDashboard /></ProtectedRoute>}
        />
      </Route>

      <Route path="/" element={<HomeRedirect />} />
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  )
}
