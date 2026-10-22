import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request } from './api.js'

// 로그인한 역할에 따라 보낼 구역 (D-047). 세션 쿠키는 HttpOnly라 화면이 읽지 않고 서버에 묻는다. (D-049)
const HOME_BY_ROLE = { admin: '/admin', operator: '/operator', customer: '/me' }

export function homeOf(account) {
  return HOME_BY_ROLE[account.role] ?? '/login'
}

export function fetchMe() {
  return request('/auth/me')
}

// 로그인이 필요한 화면의 진입. 세션이 없으면 로그인 화면으로, 역할이 다르면 그 역할의 구역으로 보낸다. (D-047)
export function useAccount(role) {
  const navigate = useNavigate()
  const [account, setAccount] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let ignore = false
    fetchMe().then((res) => {
      if (ignore) return
      if (res.kind === 'ok') {
        const me = res.data.account
        if (me.role === role) setAccount(me)
        else navigate(homeOf(me), { replace: true })
      } else if (res.error?.code === 'UNAUTHENTICATED') {
        navigate('/login', { replace: true, state: { notice: '다시 로그인해 주세요.' } })
      } else {
        setFailed(true)
      }
    })
    return () => {
      ignore = true
    }
  }, [role, navigate])

  return { account, failed }
}

// 서버 응답과 관계없이 로그인 화면으로 간다. (D-047)
export async function logout(navigate) {
  await request('/auth/logout', { method: 'POST', body: '{}' })
  navigate('/login')
}
