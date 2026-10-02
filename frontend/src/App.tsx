/**
 * App.tsx — NyayaAI shell (scaffold placeholder)
 *
 * This file will be replaced with the full UI in a future task.
 * For now it just confirms the stack (Vite + React + Tailwind + Axios) is wired up
 * and can reach the backend /health endpoint.
 */
import axios from 'axios'
import { Scale } from 'lucide-react'
import { useEffect, useState } from 'react'

interface HealthResponse {
  status: string
  service: string
  version: string
  use_llm: boolean
  embed_model: string
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    axios
      .get<HealthResponse>('/health')
      .then((res) => setHealth(res.data))
      .catch(() => setError('Backend unreachable — start uvicorn first.'))
  }, [])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 bg-[#0f1117] text-slate-200 p-8">
      {/* Logo row */}
      <div className="flex items-center gap-3">
        <Scale size={40} className="text-violet-400" />
        <h1 className="text-4xl font-bold tracking-tight">
          Nyaya<span className="text-violet-400">AI</span>
        </h1>
      </div>

      <p className="text-slate-400 text-lg text-center max-w-md">
        Indian Legal Reasoning &amp; Contract Intelligence Platform
      </p>

      {/* Backend status */}
      <div className="mt-4 rounded-xl border border-slate-700 bg-slate-800/60 px-6 py-4 w-full max-w-sm text-sm font-mono">
        <p className="text-slate-400 mb-2">Backend /health</p>
        {error && <p className="text-red-400">{error}</p>}
        {health && (
          <ul className="space-y-1 text-slate-300">
            <li>
              <span className="text-slate-500">status: </span>
              <span className="text-green-400">{health.status}</span>
            </li>
            <li>
              <span className="text-slate-500">version: </span>
              {health.version}
            </li>
            <li>
              <span className="text-slate-500">use_llm: </span>
              {String(health.use_llm)}
            </li>
            <li>
              <span className="text-slate-500">embed_model: </span>
              {health.embed_model}
            </li>
          </ul>
        )}
        {!health && !error && (
          <p className="text-slate-500 animate-pulse">Connecting …</p>
        )}
      </div>

      <p className="text-xs text-slate-600">Scaffold · Task 1 of N</p>
    </div>
  )
}
