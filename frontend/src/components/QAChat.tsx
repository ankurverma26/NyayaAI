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
    <div className="mx-auto grid h-full max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:px-8 lg:py-8">
      <div className="flex min-h-[70vh] min-w-0 flex-col lg:min-h-0">
        <div className="mb-5">
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">Legal Q&amp;A</h1>
          <p className="mt-1 text-sm text-muted">Research Indian contract law with every answer tied to verified statute text.</p>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
          {msgs.length === 0 && (
            <Card className="p-6">
              <p className="text-sm leading-relaxed text-ink/80">Ask about Indian contract law. Answers are built only from verified statute text in the local corpus; if no source can be verified, the system says so.</p>
            </Card>
          )}
          {msgs.map((m, i) => m.role === 'user'
            ? <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-brand-solid px-4 py-2.5 text-sm font-medium text-on-brand shadow-[0_8px_24px_-10px_color-mix(in_srgb,var(--brand)_80%,transparent)]">{m.text}</div>
            : <Answer key={i} resp={m.resp!} />)}
          {busy && <Spinner label="Researching statutes and verifying evidence…" />}
          {error && <ErrorBox message={error} />}
          <div ref={end} />
        </div>

        <form onSubmit={e => { e.preventDefault(); void send(input) }} className="mt-4 flex gap-2 rounded-2xl border border-line-strong bg-surface p-2 shadow-card transition focus-within:border-brand focus-within:shadow-[0_0_0_3px_color-mix(in_srgb,var(--brand)_22%,transparent)]">
          <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask a legal question…" className="min-w-0 flex-1 bg-transparent px-3 text-sm text-ink outline-none placeholder:text-faint" />
          <button disabled={busy || input.trim().length < 3} className="btn-primary px-5"><Icon name="send" /> Ask</button>
        </form>
      </div>

      <aside className="space-y-4 lg:pt-[4.5rem]">
        <Card className="p-4">
          <label className="mb-2 block text-xs font-semibold text-muted">Research scope</label>
          <select value={scope} onChange={e => setScope(e.target.value === '' ? '' : Number(e.target.value))} className="field text-sm">
            <option value="">General (statute corpus)</option>
            {contracts.map(c => <option key={c.id} value={c.id}>Scope: {c.title}</option>)}
          </select>
        </Card>
        <Card className="p-4">
          <div className="mb-3 text-xs font-semibold text-muted">Try asking</div>
          <div className="flex flex-col gap-2">
            {EXAMPLES.map(x => <button key={x} onClick={() => void send(x)} className="rounded-xl border border-line bg-raised px-3.5 py-2.5 text-left text-[13px] leading-snug text-ink/90 transition hover:-translate-y-px hover:border-brand hover:text-ink">{x}</button>)}
          </div>
        </Card>
      </aside>
    </div>
  )
}

function Answer({ resp }: { resp: AskResponse }) {
  const [open, setOpen] = useState<string | null>(null)
  const items = resp.evidence.flatMap(o => o.evidence)
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2 text-xs capitalize text-faint">
        <Icon name="scale" className="h-3.5 w-3.5 text-warn" /> {resp.intent?.replace(/_/g, ' ')} · confidence: {resp.confidence}
      </div>
      <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{resp.answer}</p>
      {items.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs text-faint">Citations</div>
          <div className="flex flex-wrap gap-2">
            {items.map(e => (
              <button key={e.citation} onClick={() => setOpen(open === e.citation ? null : e.citation)}
                className="chip-cite">{e.citation}</button>
            ))}
          </div>
          {items.filter(e => e.citation === open).map(e => (
            <div key={e.citation} className="mt-2">
              <div className="text-xs text-muted">{e.source} · {e.heading} · law status: {e.law_status}</div>
              <Quote>{e.quote}</Quote>
            </div>
          ))}
        </div>
      )}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer text-muted transition hover:text-brand">Research trace ({resp.trace.length} steps · {resp.workflow_engine})</summary>
        <ol className="mt-2 space-y-2">
          {resp.trace.map((t, i) => (
            <li key={i}>
              <span className={t.status === 'completed' ? 'text-ok' : t.status === 'failed' ? 'text-bad' : 'text-warn'}>●</span>{' '}
              <span className="text-ink">{t.step.replace(/_/g, ' ')}</span>
              <Detail data={t.detail} />
            </li>
          ))}
        </ol>
      </details>
    </Card>
  )
}
