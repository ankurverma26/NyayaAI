import { useCallback, useEffect, useState } from 'react'
import { createChange, errMsg, listChanges, listStatutes } from '../api'
import type { ChangeImpact, LegalChange, StatuteSummary } from '../types'
import { Card, Empty, ErrorBox, Icon, Spinner } from './ui'

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
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div>
        <h1 className="font-serif text-2xl text-white">Legal Changes</h1>
        <p className="mt-1 text-sm text-slate-400">Record a new amendment or judgment (demo) and see which analysed contract clauses may be affected. Analyse a contract first so its clauses are linked to statute sections.</p>
      </div>

      <Card className="space-y-3 p-4">
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title, e.g. Amendment to restraint of trade provision" className="w-full rounded border border-white/10 bg-black/20 px-3 py-2 text-sm outline-none focus:border-amber-400/50" />
        <input value={citation} onChange={e => setCitation(e.target.value)} placeholder="Affected section, e.g. ICA1872 s.27" className="w-full rounded border border-white/10 bg-black/20 px-3 py-2 text-sm outline-none focus:border-amber-400/50" />
        {names && <div className="text-xs text-slate-500">Loaded statutes (short names): {names}</div>}
        <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2} placeholder="Description (optional)" className="w-full rounded border border-white/10 bg-black/20 px-3 py-2 text-sm outline-none focus:border-amber-400/50" />
        <button onClick={() => void submit()} disabled={busy || title.trim().length < 3 || !citation.trim()} className="rounded-lg bg-amber-400 px-4 py-2 text-sm font-medium text-black hover:bg-amber-300 disabled:opacity-40">Add change and check impact</button>
      </Card>

      {busy && <Spinner label="Checking linked clauses…" />}
      {error && <ErrorBox message={error} />}

      {impact && (
        <section className="space-y-3">
          <h2 className="font-serif text-lg text-white">Impact of “{impact.title}”</h2>
          {impact.impacted_clauses.length === 0 && <Empty>No analysed clause is linked to this section yet.</Empty>}
          {impact.impacted_clauses.map(c => (
            <Card key={c.clause_id} className="border-amber-500/40 bg-amber-500/5 p-4">
              <div className="flex items-start gap-3">
                <Icon name="bell" className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
                <div className="flex-1">
                  <p className="text-sm text-slate-100">{c.alert}</p>
                  <button onClick={() => onOpenContract(c.contract_id)} className="mt-2 text-xs text-amber-300 hover:underline">Open contract →</button>
                </div>
              </div>
            </Card>
          ))}
        </section>
      )}

      <section>
        <h2 className="mb-2 font-serif text-lg text-white">Recorded changes</h2>
        {changes === null ? <Spinner /> : changes.length === 0 ? <Empty>No legal changes recorded yet.</Empty> : (
          <ul className="space-y-2">
            {changes.map(c => (
              <li key={c.id}><Card className="px-4 py-2 text-sm text-slate-300">{c.title} <span className="text-xs text-slate-500">· {c.date}</span></Card></li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
