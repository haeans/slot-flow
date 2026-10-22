import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { request } from '../api.js'
import { homeOf } from '../auth.js'

// 화면 0 — 로그인. 관리자·운영자·회원 고객이 같은 화면을 쓴다. (SCREEN-SPEC 3절, D-047)
export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setSubmitting(true)
    setResult(null)
    const res = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setSubmitting(false)
    if (res.kind === 'ok') {
      navigate(homeOf(res.data.account))
      return
    }
    // 거부되면 비밀번호 입력 칸을 비운다. (SCREEN-SPEC 3절)
    setPassword('')
    setResult(res)
  }

  return (
    <main>
      <h1>로그인</h1>
      {location.state?.notice && <p>{location.state.notice}</p>}
      <form onSubmit={submit}>
        <label>
          이메일
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          비밀번호
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? '요청 중...' : '로그인'}
        </button>
      </form>

      {result?.kind === 'no-response' && (
        <p role="alert">서버 응답을 받지 못했습니다. 다시 시도해 주세요.</p>
      )}
      {result?.error && (
        <section className="result error" role="alert">
          <h2>로그인되지 않았습니다</h2>
          <p>{result.error.message}</p>
        </section>
      )}

      <p>
        <Link to="/signup">가입</Link>
      </p>
    </main>
  )
}
