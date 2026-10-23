import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request } from '../api.js'
import { logout, useAccount } from '../auth.js'

const STATUS_LABEL = { pending: '승인 대기', approved: '승인', suspended: '정지' }

// 화면 6 — 운영자 관리. 관리자가 운영자를 승인하고 정지한다. (SCREEN-SPEC 9절, D-043, D-067)
export default function Admin() {
  const navigate = useNavigate()
  const { account, failed } = useAccount('admin')
  const [operators, setOperators] = useState(null)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!account) return
    request('/admin/operators').then((res) => {
      if (res.kind === 'ok') setOperators(res.data.operators)
      else setMessage(res.error ? res.error.message : '운영자 목록을 불러오지 못했습니다. 새로고침해 주세요.')
    })
  }, [account])

  async function change(operator, action) {
    // 정지하면 그 운영자는 곧바로 로그아웃되고 자원이 새 예약을 받지 않는다. (D-053, D-065)
    if (action === 'suspend' && !window.confirm(`${operator.name}(${operator.email})을 정지할까요? 정지하면 다시 승인할 수 없습니다.`)) {
      return
    }
    setMessage('')
    const res = await request(`/admin/operators/${operator.booking_slug}/${action}`, {
      method: 'POST',
      body: '{}',
    })
    if (res.kind === 'ok') {
      setOperators((list) =>
        list.map((o) => (o.booking_slug === operator.booking_slug ? res.data.operator : o)),
      )
    } else if (res.error?.code === 'UNAUTHENTICATED') {
      navigate('/login', { state: { notice: '다시 로그인해 주세요.' } })
    } else {
      setMessage(res.error ? res.error.message : '서버 응답을 받지 못했습니다. 목록을 새로고침해 확인해 주세요.')
    }
  }

  if (failed) {
    return (
      <main>
        <h1>운영자 관리</h1>
        <p role="alert">계정 정보를 불러오지 못했습니다. 새로고침해 주세요.</p>
      </main>
    )
  }
  if (!account) {
    return (
      <main>
        <h1>운영자 관리</h1>
        <p>불러오는 중...</p>
      </main>
    )
  }

  return (
    <main>
      <h1>운영자 관리</h1>
      {message && <p role="alert">{message}</p>}
      {operators === null && !message && <p>불러오는 중...</p>}
      {operators?.length === 0 && <p>운영자가 없습니다.</p>}
      {operators?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>이름</th>
              <th>이메일</th>
              <th>예약 주소명</th>
              <th>상태</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {operators.map((o) => (
              <tr key={o.booking_slug}>
                <td>{o.name}</td>
                <td>{o.email}</td>
                <td>{o.booking_slug}</td>
                <td>{STATUS_LABEL[o.operator_status]}</td>
                <td>
                  {o.operator_status === 'pending' && (
                    <button type="button" onClick={() => change(o, 'approve')}>
                      승인
                    </button>
                  )}
                  {o.operator_status !== 'suspended' && (
                    <button type="button" onClick={() => change(o, 'suspend')}>
                      정지
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <button type="button" onClick={() => logout(navigate)}>
        로그아웃
      </button>
    </main>
  )
}
