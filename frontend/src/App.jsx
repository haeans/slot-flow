import { useEffect, useState } from 'react'

function App() {
  const [health, setHealth] = useState('확인 중...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('연결 실패'))
  }, [])

  return (
    <main>
      <h1>slot-flow</h1>
      <p>서버 상태: {health}</p>
    </main>
  )
}

export default App
