import { Route, Routes } from 'react-router-dom'
import Booking from './pages/Booking.jsx'
import Signup from './pages/Signup.jsx'

// 화면 주소 (SCREEN-SPEC 2절)
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Booking />} />
      <Route path="/signup" element={<Signup />} />
    </Routes>
  )
}
