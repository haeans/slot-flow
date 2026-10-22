import { request } from './api.js'

// 로그인한 역할에 따라 보낼 구역 (D-047). 세션 쿠키는 HttpOnly라 화면이 읽지 않고 서버에 묻는다. (D-049)
const HOME_BY_ROLE = { admin: '/admin', operator: '/operator', customer: '/me' }

export function homeOf(account) {
  return HOME_BY_ROLE[account.role] ?? '/login'
}

export function fetchMe() {
  return request('/auth/me')
}

// 서버 응답과 관계없이 로그인 화면으로 간다. (D-047)
export async function logout(navigate) {
  await request('/auth/logout', { method: 'POST', body: '{}' })
  navigate('/login')
}
