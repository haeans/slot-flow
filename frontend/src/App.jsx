import { Navigate, Route, Routes } from 'react-router-dom'
import Admin from './pages/Admin.jsx'
import Booking from './pages/Booking.jsx'
import Login from './pages/Login.jsx'
import Operator from './pages/Operator.jsx'
import Signup from './pages/Signup.jsx'

// 화면 주소 (SCREEN-SPEC 2절). 첫 화면(/)은 정해지지 않아 로그인으로 보낸다. (D-066)
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/r/:slug" element={<Booking />} />
      <Route path="/operator" element={<Operator />} />
      <Route path="/admin" element={<Admin />} />
    </Routes>
  )
}
