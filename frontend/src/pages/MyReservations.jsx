import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request } from '../api.js'
import { logout, useAccount } from '../auth.js'

const STATUS_LABEL = { reserved: '예약됨', cancelled: '취소됨' }
const timeOf = (dateTime) => dateTime.slice(11, 16)

// 화면 4 중 회원의 내 예약 목록. 로그인한 회원 본인의 예약만 보여 준다. (SCREEN-SPEC 7절, D-045)
export default function MyReservations() {
  const navigate = useNavigate()
  const { account, failed } = useAccount('customer')
  const [reservations, setReservations] = useState(null)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!account) return
    request('/me/reservations').then((res) => {
      if (res.kind === 'ok') setReservations(res.data.reservations)
      else if (res.error?.code === 'UNAUTHENTICATED') {
        navigate('/login', { state: { notice: '다시 로그인해 주세요.' } })
      } else setMessage(res.error ? res.error.message : '예약 목록을 불러오지 못했습니다. 새로고침해 주세요.')
    })
  }, [account, navigate])

  if (failed) {
    return (
      <main>
        <h1>내 예약</h1>
        <p role="alert">계정 정보를 불러오지 못했습니다. 새로고침해 주세요.</p>
      </main>
    )
  }
  if (!account) {
    return (
      <main>
        <h1>내 예약</h1>
        <p>불러오는 중...</p>
      </main>
    )
  }

  return (
    <main>
      <h1>내 예약</h1>
      <p>
        {account.name} ({account.email})
      </p>
      {message && <p role="alert">{message}</p>}
      {reservations === null && !message && <p>불러오는 중...</p>}
      {/* 목록이 비면 "예약이 없습니다"를 표시한다. (D-040) */}
      {reservations?.length === 0 && <p>예약이 없습니다.</p>}
      {reservations?.length > 0 && (
        <ul>
          {reservations.map((r) => (
            <li key={r.reservation_code}>
              {r.resource_name} · {r.start_at.slice(0, 10)} {timeOf(r.start_at)}–{timeOf(r.end_at)} ·{' '}
              {STATUS_LABEL[r.status]} · 예약 코드 <span className="code">{r.reservation_code}</span>
            </li>
          ))}
        </ul>
      )}
      <button type="button" onClick={() => logout(navigate)}>
        로그아웃
      </button>
    </main>
  )
}
