import { Link, useNavigate } from 'react-router-dom'
import { logout, useAccount } from '../auth.js'

// 운영자 구역. 승인 상태와 고객 예약 주소를 보여 준다. 자원 관리(화면 1)와 예약 목록(화면 2)은 아직 없다.
export default function Operator() {
  const navigate = useNavigate()
  const { account, failed } = useAccount('operator')

  if (failed) {
    return (
      <main>
        <h1>운영자</h1>
        <p role="alert">계정 정보를 불러오지 못했습니다. 새로고침해 주세요.</p>
      </main>
    )
  }
  if (!account) {
    return (
      <main>
        <h1>운영자</h1>
        <p>불러오는 중...</p>
      </main>
    )
  }

  return (
    <main>
      <h1>운영자</h1>
      <p>
        {account.name} ({account.email})
      </p>
      {account.operator_status === 'pending' && (
        <section className="result">
          <h2>승인 대기</h2>
          <p>관리자 승인을 기다리고 있습니다. 승인되면 자원을 등록할 수 있습니다. (D-053)</p>
        </section>
      )}
      {account.operator_status === 'approved' && (
        <p>
          고객 예약 주소: <Link to={`/r/${account.booking_slug}`}>/r/{account.booking_slug}</Link>
        </p>
      )}
      <button type="button" onClick={() => logout(navigate)}>
        로그아웃
      </button>
    </main>
  )
}
