import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { request } from '../api.js'

// 화면 5 — 가입. 운영자는 승인 대기, 고객은 바로 회원이 된다. (SCREEN-SPEC 8절, D-043)
export default function Signup() {
  const navigate = useNavigate()
  const [role, setRole] = useState('customer')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [bookingSlug, setBookingSlug] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setSubmitting(true)
    setResult(null)
    const body = { email, password, role, name }
    if (role === 'operator') body.booking_slug = bookingSlug
    const res = await request('/auth/signup', { method: 'POST', body: JSON.stringify(body) })
    setSubmitting(false)
    if (res.kind === 'ok' && role === 'customer') {
      navigate('/login', { state: { notice: '가입되었습니다. 로그인해 주세요.' } })
      return
    }
    // 거부되면 비밀번호 외의 입력값은 지우지 않는다. (SCREEN-SPEC 8절)
    if (res.kind !== 'ok') setPassword('')
    setResult(res)
  }

  if (result?.kind === 'ok') {
    return (
      <main>
        <h1>가입</h1>
        <section className="result ok">
          <h2>가입 신청이 접수되었습니다</h2>
          <p>관리자가 승인하면 자원을 등록할 수 있습니다. 승인 전에도 로그인해 상태를 확인할 수 있습니다.</p>
        </section>
        <p>
          <Link to="/login">로그인으로</Link>
        </p>
      </main>
    )
  }

  return (
    <main>
      <h1>가입</h1>
      <form onSubmit={submit}>
        <fieldset>
          <legend>가입 종류</legend>
          <label>
            <input
              type="radio"
              name="role"
              checked={role === 'customer'}
              onChange={() => setRole('customer')}
            />
            고객 회원
          </label>
          <label>
            <input
              type="radio"
              name="role"
              checked={role === 'operator'}
              onChange={() => setRole('operator')}
            />
            운영자 (관리자 승인 필요)
          </label>
        </fieldset>
        <label>
          이메일
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          비밀번호 (8~128자)
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label>
          이름
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        {role === 'operator' && (
          <label>
            예약 주소명 (영문 소문자·숫자·-, 3~30자)
            <input value={bookingSlug} onChange={(e) => setBookingSlug(e.target.value)} />
          </label>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? '요청 중...' : '가입'}
        </button>
      </form>

      {result?.kind === 'no-response' && (
        <p role="alert">서버 응답을 받지 못했습니다. 가입되었는지 로그인으로 확인해 주세요.</p>
      )}
      {result?.error && (
        <section className="result error" role="alert">
          <h2>가입되지 않았습니다</h2>
          <p>{result.error.message}</p>
        </section>
      )}

      <p>
        <Link to="/login">이미 계정이 있으면 로그인</Link>
      </p>
    </main>
  )
}
