import { useEffect, useState } from 'react'
import { errMsg, getFindingTrace } from '../api'
import type { FindingTrace } from '../types'
import { Detail, ErrorBox, Icon, Spinner } from './ui'

export default function WhyDrawer({ findingId, onClose }: { findingId: number; onClose: () => void }) {
  const [trace, setTrace] = useState<FindingTrace | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setTrace(null)
    setError(null)
    getFindingTrace(findingId).then(setTrace).catch(e => setError(errMsg(e)))
  }, [findingId])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60" onClick={onClose}>
      <aside onClick={e => e.stopPropagation()} className="h-full w-full max-w-lg overflow-y-auto border-l border-white/10 bg-[#12151d] p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="font-serif text-xl text-white">Why did the system reach this finding?</h2>
            <p className="mt-1 text-xs text-slate-500">Auditable evidence trail: each step shows what was checked and which source supports it.</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-slate-400 hover:bg-white/10"><Icon name="close" /></button>
        </div>
        {error && <ErrorBox message={error} />}
        {!trace && !error && <Spinner />}
        {trace && (
          <ol className="relative ml-3 space-y-5 border-l border-white/15 pl-6">
            {trace.steps.map((s, i) => (
              <li key={i} className="relative">
                <span className="absolute -left-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-400 text-[10px] font-bold text-black">{i + 1}</span>
                <div className="text-xs uppercase tracking-wide text-amber-300">{s.stage}</div>
                <div className="text-sm text-slate-100">{s.title}</div>
                <Detail data={s.detail} />
              </li>
            ))}
          </ol>
        )}
      </aside>
    </div>
  )
}
