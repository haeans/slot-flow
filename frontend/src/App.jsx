import { useEffect, useState } from 'react'
import { request } from './api.js'

// 거부 사유를 규칙별로 구분해 보여 준다. 문장은 서버가 준 message를 그대로 쓴다. (D-013)
const REASON_LABEL = {
  INVALID_INPUT: '입력 형식',
  RESOURCE_NOT_FOUND: '자원 없음',
  PAST_TIME: '지나간 시각',
  OUTSIDE_OPERATING_HOURS: '운영시간 밖',
  OVERLAP: '겹침',
}

const timeOf = (dateTime) => dateTime.slice(11, 16)

function App() {
  const [resources, setResources] = useState(null)
  const [resourcesFailed, setResourcesFailed] = useState(false)
  const [resourceId, setResourceId] = useState('')
  const [date, setDate] = useState('')
  const [slots, setSlots] = useState(null)
  const [slotsVersion, setSlotsVersion] = useState(0)
  const [slotsMessage, setSlotsMessage] = useState('')
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    request('/resources').then((res) => {
      if (res.kind === 'ok') setResources(res.data.resources)
      else setResourcesFailed(true)
    })
  }, [])

  useEffect(() => {
    if (!resourceId || !date) return
    let ignore = false
    request(`/resources/${resourceId}/slots?date=${date}`).then((res) => {
      if (ignore) return
      if (res.kind === 'ok') {
        setSlots(res.data.slots)
        setSlotsMessage('')
      } else {
        setSlots(null)
        setSlotsMessage(
          res.error ? res.error.message : '칸을 불러오지 못했습니다. 다시 시도해 주세요.',
        )
      }
    })
    return () => {
      ignore = true
    }
  }, [resourceId, date, slotsVersion])

  function chooseResource(value) {
    setResourceId(value)
    setSlots(null)
    setStartAt('')
    setEndAt('')
  }

  function chooseDate(value) {
    setDate(value)
    setSlots(null)
    setStartAt('')
    setEndAt('')
  }

  async function submit(event) {
    event.preventDefault()
    setSubmitting(true)
    setResult(null)
    const res = await request('/reservations', {
      method: 'POST',
      body: JSON.stringify({
        resource_id: Number(resourceId),
        start_at: startAt,
        end_at: endAt,
        customer_name: name,
      }),
    })
    setSubmitting(false)
    setResult(res)
    // 성공했거나 겹침으로 거부되면 칸을 다시 조회해 최신 점유 상태를 보여 준다. (SCREEN-SPEC 6절)
    if (res.kind === 'ok' || res.error?.code === 'OVERLAP') setSlotsVersion((v) => v + 1)
  }

  if (resourcesFailed) {
    return (
      <main>
        <h1>예약하기</h1>
        <p role="alert">자원 목록을 불러오지 못했습니다. 새로고침해 주세요.</p>
      </main>
    )
  }
  if (resources === null) {
    return (
      <main>
        <h1>예약하기</h1>
        <p>불러오는 중...</p>
      </main>
    )
  }

  return (
    <main>
      <h1>예약하기</h1>
      {resources.length === 0 ? (
        <p>예약할 수 있는 자원이 없습니다.</p>
      ) : (
        <form onSubmit={submit}>
          <label>
            자원
            <select value={resourceId} onChange={(e) => chooseResource(e.target.value)}>
              <option value="">선택하세요</option>
              {resources.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            날짜
            <input type="date" value={date} onChange={(e) => chooseDate(e.target.value)} />
          </label>

          {slotsMessage && <p role="alert">{slotsMessage}</p>}

          {slots && (
            <section>
              <h2>{date}의 30분 칸</h2>
              {slots.length === 0 ? (
                <p>이 날은 운영하지 않습니다.</p>
              ) : (
                <ul className="slots">
                  {slots.map((s) => (
                    <li key={s.start_at} className={s.status}>
                      {timeOf(s.start_at)}–{timeOf(s.end_at)}{' '}
                      {s.status === 'reserved' ? '예약됨' : '비어 있음'}
                    </li>
                  ))}
                </ul>
              )}

              {slots.length > 0 && (
                <>
                  <label>
                    시작
                    <select value={startAt} onChange={(e) => setStartAt(e.target.value)}>
                      <option value="">선택하세요</option>
                      {slots.map((s) => (
                        <option key={s.start_at} value={s.start_at}>
                          {timeOf(s.start_at)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    종료
                    <select value={endAt} onChange={(e) => setEndAt(e.target.value)}>
                      <option value="">선택하세요</option>
                      {slots.map((s) => (
                        <option key={s.end_at} value={s.end_at}>
                          {timeOf(s.end_at)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    이름
                    <input value={name} onChange={(e) => setName(e.target.value)} />
                  </label>
                  <button type="submit" disabled={submitting}>
                    {submitting ? '요청 중...' : '예약'}
                  </button>
                </>
              )}
            </section>
          )}
        </form>
      )}

      <Result result={result} />
    </main>
  )
}

function Result({ result }) {
  if (!result) return null
  if (result.kind === 'ok') {
    const r = result.data
    return (
      <section className="result ok">
        <h2>예약됨</h2>
        <p>
          {r.resource_name} · {r.start_at.slice(0, 10)} {timeOf(r.start_at)}–{timeOf(r.end_at)}
        </p>
        <p>
          예약 코드 <strong className="code">{r.reservation_code}</strong>
        </p>
        <p>예약 코드는 내 예약을 조회하고 취소할 때 필요합니다. 꼭 적어 두세요.</p>
      </section>
    )
  }
  if (result.kind === 'no-response') {
    return (
      <section className="result error" role="alert">
        <h2>결과를 확인하지 못했습니다</h2>
        <p>예약이 되었는지 알 수 없습니다. 칸을 다시 조회해 확인해 주세요.</p>
      </section>
    )
  }
  const { code, message } = result.error
  return (
    <section className="result error" role="alert">
      <h2>
        {result.kind === 'failed' ? '처리되지 않았습니다' : '예약되지 않았습니다'}
        {REASON_LABEL[code] && ` — ${REASON_LABEL[code]}`}
      </h2>
      <p>{message}</p>
    </section>
  )
}

export default App
