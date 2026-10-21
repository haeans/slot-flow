// 서버 응답을 세 가지로 나눈다. (SCREEN-SPEC 1절)
// - ok: 성공
// - rejected / failed: 서버가 { error: { code, message } }로 거부(4xx)·실패(5xx)를 알림
// - no-response: 서버 응답을 받지 못해 처리 여부를 알 수 없음
export async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`/api${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    return { kind: 'no-response' }
  }

  let body = null
  try {
    body = await res.json()
  } catch {
    body = null
  }

  if (res.ok) return { kind: 'ok', data: body }
  if (body?.error) {
    return { kind: res.status >= 500 ? 'failed' : 'rejected', error: body.error }
  }
  return { kind: 'no-response' }
}
