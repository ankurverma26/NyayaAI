import { useEffect, useRef, useState } from 'react'
import { askLegal, errMsg, listContracts } from '../api'
import type { AskResponse, ContractSummary } from '../types'
import { Card, Detail, ErrorBox, Icon, Quote, Spinner } from './ui'

interface Msg { role: 'user' | 'assistant'; text: string; resp?: AskResponse }

const EXAMPLES = [
  'Is a 3-year non-compete after resignation valid?',
  'What does section 74 say about penalty clauses?',
  'What law applies to an arbitration agreement?',
  'What is a contract of indemnity?',
]

export default function QAChat({ defaultContractId }: { defaultContractId: number | null }) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [contracts, setContracts] = useState<ContractSummary[]>([])
  const [scope, setScope] = useState<number | ''>(defaultContractId ?? '')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => { listContracts().then(setContracts).catch(() => setContracts([])) }, [])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  async function send(text: string) {
    const q = text.trim()
    if (q.length < 3 || busy) return
    setInput('')
    setError(null)
    setMsgs(m => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const resp = await askLegal({ query: q, contract_id: scope === '' ? undefined : scope })
      setMsgs(m => [...m, { role: 'assistant', text: resp.answer, resp }])
    } catch (e) {
      setError(errMsg(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-2xl text-white">Legal Q&amp;A</h1>
        <select value={scope} onChange={e => setScope(e.target.value === '' ? '' : Number(e.target.value))} className="ml-auto rounded border border-white/10 bg-[#161a23] px-2 py-1 text-xs">
          <option value="">General (statute corpus)</option>
          {contracts.map(c => <option key={c.id} value={c.id}>Scope: {c.title}</option>)}
        </select>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
        {msgs.length === 0 && (
          <Card className="p-5">
            <p className="text-sm text-slate-300">Ask about Indian contract law. Answers are built only from verified statute text in the local corpus; if no source can be verified, the system says so.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLES.map(x => <button key={x} onClick={() => void send(x)} className="rounded-full border border-white/15 px-3 py-1 text-xs text-slate-300 hover:bg-white/10">{x}</button>)}
            </div>
          </Card>
        )}
        {msgs.map((m, i) => m.role === 'user'
          ? <div key={i} className="ml-auto max-w-[85%] rounded-2xl bg-amber-400/15 px-4 py-2 text-sm text-amber-50">{m.text}</div>
          : <Answer key={i} resp={m.resp!} />)}
        {busy && <Spinner label="Researching statutes and verifying evidence…" />}
        {error && <ErrorBox message={error} />}
        <div ref={end} />
      </div>

      <form onSubmit={e => { e.preventDefault(); void send(input) }} className="mt-3 flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask a legal question…" className="flex-1 rounded-lg border border-white/10 bg-[#161a23] px-3 py-2 text-sm outline-none focus:border-amber-400/50" />
        <button disabled={busy || input.trim().length < 3} className="flex items-center gap-1 rounded-lg bg-amber-400 px-4 text-sm font-medium text-black hover:bg-amber-300 disabled:opacity-40"><Icon name="send" /> Ask</button>
      </form>
    </div>
  )
}

function Answer({ resp }: { resp: AskResponse }) {
  const [open, setOpen] = useState<string | null>(null)
  const items = resp.evidence.flatMap(o => o.evidence)
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
        <Icon name="scale" className="h-3.5 w-3.5" /> {resp.intent?.replace(/_/g, ' ')} · confidence: {resp.confidence}
      </div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{resp.answer}</p>
      {items.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs text-slate-500">Citations</div>
          <div className="flex flex-wrap gap-2">
            {items.map(e => (
              <button key={e.citation} onClick={() => setOpen(open === e.citation ? null : e.citation)}
                className="rounded border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-xs text-amber-200 hover:bg-amber-400/20">{e.citation}</button>
            ))}
          </div>
          {items.filter(e => e.citation === open).map(e => (
            <div key={e.citation} className="mt-2">
              <div className="text-xs text-slate-400">{e.source} · {e.heading} · law status: {e.law_status}</div>
              <Quote>{e.quote}</Quote>
            </div>
          ))}
        </div>
      )}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer text-slate-400 hover:text-slate-200">Research trace ({resp.trace.length} steps · {resp.workflow_engine})</summary>
        <ol className="mt-2 space-y-2">
          {resp.trace.map((t, i) => (
            <li key={i}>
              <span className={t.status === 'completed' ? 'text-emerald-400' : t.status === 'failed' ? 'text-red-400' : 'text-amber-300'}>●</span>{' '}
              <span className="text-slate-200">{t.step.replace(/_/g, ' ')}</span>
              <Detail data={t.detail} />
            </li>
          ))}
        </ol>
      </details>
    </Card>
  )
}
