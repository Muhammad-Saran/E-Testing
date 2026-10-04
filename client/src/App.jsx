import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
const Register = lazy(() => import('./pages/Register.jsx'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword.jsx'))
const ResetPassword = lazy(() => import('./pages/ResetPassword.jsx'))
const StudentDashboard = lazy(() => import('./pages/StudentDashboard.jsx'))
const InstructorDashboard = lazy(() => import('./pages/InstructorDashboard.jsx'))
const Courses = lazy(() => import('./pages/Courses.jsx'))
const QuestionBank = lazy(() => import('./pages/QuestionBank.jsx'))
const InstructorExams = lazy(() => import('./pages/InstructorExams.jsx'))
const InstructorResults = lazy(() => import('./pages/InstructorResults.jsx'))
const StudentExams = lazy(() => import('./pages/StudentExams.jsx'))
const StudentResults = lazy(() => import('./pages/StudentResults.jsx'))
const StudentMaterials = lazy(() => import('./pages/StudentMaterials.jsx'))
const AIGenerate = lazy(() => import('./pages/AIGenerate.jsx'))
const Notifications = lazy(() => import('./pages/Notifications.jsx'))
const Practice = lazy(() => import('./pages/Practice.jsx'))
const Profile = lazy(() => import('./pages/Profile.jsx'))

// Shared paths render the instructor or student view based on role.
function ByRole({ instructor, student }) {
  const { user } = useAuth()
  return user.role === 'instructor' ? instructor : student
}

// Send a logged-in user to the dashboard matching their role.
function HomeRedirect() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'instructor' ? '/instructor' : '/student'} replace />
}

export default function App() {
  const { loading } = useAuth()
  if (loading) return <div className="center-screen"><div><div className="spinner" />Loading…</div></div>

  return (
    <Suspense fallback={<div className="loading"><div className="spinner" /></div>}>
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      <Route element={<Layout />}>
        <Route
          path="/instructor"
          element={<ProtectedRoute role="instructor"><InstructorDashboard /></ProtectedRoute>}
        />
        <Route
          path="/courses"
          element={<ProtectedRoute role="instructor"><Courses /></ProtectedRoute>}
        />
        <Route
          path="/questions"
          element={<ProtectedRoute role="instructor"><QuestionBank /></ProtectedRoute>}
        />
        <Route
          path="/ai-generate"
          element={<ProtectedRoute role="instructor"><AIGenerate /></ProtectedRoute>}
        />
        <Route
          path="/notifications"
          element={<ProtectedRoute><Notifications /></ProtectedRoute>}
        />
        <Route
          path="/practice"
          element={<ProtectedRoute role="student"><Practice /></ProtectedRoute>}
        />
        <Route
          path="/profile"
          element={<ProtectedRoute><Profile /></ProtectedRoute>}
        />
        <Route
          path="/student"
          element={<ProtectedRoute role="student"><StudentDashboard /></ProtectedRoute>}
        />
        <Route
          path="/materials"
          element={<ProtectedRoute role="student"><StudentMaterials /></ProtectedRoute>}
        />
        <Route
          path="/exams"
          element={<ProtectedRoute><ByRole instructor={<InstructorExams />} student={<StudentExams />} /></ProtectedRoute>}
        />
        <Route
          path="/results"
          element={<ProtectedRoute><ByRole instructor={<InstructorResults />} student={<StudentResults />} /></ProtectedRoute>}
        />
      </Route>

      <Route path="/" element={<HomeRedirect />} />
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
    </Suspense>
  )
}
