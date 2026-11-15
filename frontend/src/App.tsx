import { useEffect, useState } from 'react'
import { fetchHealth } from './api'

type BackendStatus = 'checking' | 'online' | 'offline'

export default function App() {
  const [status, setStatus] = useState<BackendStatus>('checking')

  useEffect(() => {
    fetchHealth()
      .then(() => setStatus('online'))
      .catch(() => setStatus('offline'))
  }, [])

  return (
    <main className="app">
      <h1>Weather-Aware Truck Routing</h1>
      <p>
        Backend: <strong data-status={status}>{status}</strong>
      </p>
    </main>
  )
}
