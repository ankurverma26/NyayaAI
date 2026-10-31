import { useCallback, useEffect, useState } from 'react'
import { createChange, errMsg, listChanges, listStatutes } from '../api'
import type { ChangeImpact, LegalChange, StatuteSummary } from '../types'
import { Card, Empty, ErrorBox, Icon, Spinner } from './ui'
import SourceCheckPanel from './SourceCheckPanel'

export default function LegalChanges({ onOpenContract }: { onOpenContract: (id: number) => void }) {
  const [title, setTitle] = useState('')
  const [citation, setCitation] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [impact, setImpact] = useState<ChangeImpact | null>(null)
  const [changes, setChanges] = useState<LegalChange[] | null>(null)
  const [statutes, setStatutes] = useState<StatuteSummary[]>([])

  const load = useCallback(() => { listChanges().then(setChanges).catch(e => setError(errMsg(e))) }, [])
  useEffect(() => {
    load()
    listStatutes().then(setStatutes).catch(() => setStatutes([]))
  }, [load])

  async function submit() {
    setBusy(true)
    setError(null)
    setImpact(null)
    try {
      setImpact(await createChange({ title: title.trim(), citation: citation.trim(), description: description.trim() || undefined }))
      load()
    } catch (e) {
      setError(errMsg(e))
    } finally {
      setBusy(false)
    }
  }

  const names = statutes.map(s => s.short_name).filter(Boolean).join(', ')
  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-10 enter">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">Legal Changes</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-muted">Record a new amendment or judgment (demo) and see which analysed contract clauses may be affected. Analyse a contract first so its clauses are linked to statute sections.</p>
      </div>

      <SourceCheckPanel onChecked={load} onOpenContract={onOpenContract} />

      <Card className="space-y-3 p-5">
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title, e.g. Amendment to restraint of trade provision" className="field" />
        <input value={citation} onChange={e => setCitation(e.target.value)} placeholder="Affected section, e.g. ICA1872 s.27" className="field" />
        {names && <div className="text-xs text-faint">Loaded statutes (short names): {names}</div>}
        <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2} placeholder="Description (optional)" className="field" />
        <button onClick={() => void submit()} disabled={busy || title.trim().length < 3 || !citation.trim()} className="btn-primary">Add change and check impact</button>
      </Card>

      {busy && <Spinner label="Checking linked clauses…" />}
      {error && <ErrorBox message={error} />}

      {impact && (
        <section className="space-y-3">
          <h2 className="font-display text-lg font-semibold text-ink">Impact of “{impact.title}”</h2>
          {impact.impacted_clauses.length === 0 && <Empty>No analysed clause is linked to this section yet.</Empty>}
          {impact.impacted_clauses.map(c => (
            <Card key={c.clause_id} className="border-warn/40 bg-warn/[0.06] p-4 shadow-[0_0_30px_-12px_color-mix(in_srgb,var(--warn)_40%,transparent)]">
              <div className="flex items-start gap-3">
                <Icon name="bell" className="mt-0.5 h-5 w-5 shrink-0 text-warn" />
                <div className="flex-1">
                  <p className="text-sm text-ink">{c.alert}</p>
                  <button onClick={() => onOpenContract(c.contract_id)} className="mt-2 text-xs font-medium text-warn hover:text-warn hover:underline">Open contract →</button>
                </div>
              </div>
            </Card>
          ))}
        </section>
      )}

      <section>
        <h2 className="mb-2 font-display text-lg font-semibold text-ink">Recorded changes</h2>
        {changes === null ? <Spinner /> : changes.length === 0 ? <Empty>No legal changes recorded yet.</Empty> : (
          <ul className="space-y-2">
            {changes.map(c => (
              <li key={c.id}><Card className="px-4 py-3 text-sm text-ink">{c.title} <span className="text-xs text-faint">· {c.date}</span></Card></li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
