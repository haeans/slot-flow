import { Route, Routes } from 'react-router-dom'
import Booking from './pages/Booking.jsx'
import Login from './pages/Login.jsx'
import Signup from './pages/Signup.jsx'

// 화면 주소 (SCREEN-SPEC 2절)
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Booking />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
    </Routes>
  )
}
