import { useCallback, useEffect, useState } from 'react'
import { errMsg, getSyncStatus, runSourceCheck } from '../api'
import type { CheckAlert, SourceStatus } from '../types'
import { Card, ErrorBox, Icon, Spinner } from './ui'

const OUTCOME: Record<string, { label: string; cls: string }> = {
  verified: { label: 'Matches the official text', cls: 'border-ok/35 bg-ok/10 text-ok' },
  needs_review: { label: 'Needs review', cls: 'border-warn/35 bg-warn/10 text-warn' },
  unreachable: { label: 'Official source unreachable (stored text in use)', cls: 'border-line-strong bg-ink/5 text-ink/80' },
  no_source_url: { label: 'No source URL set', cls: 'border-line-strong bg-ink/5 text-ink/80' },
  never_checked: { label: 'Never checked', cls: 'border-line-strong bg-ink/5 text-ink/80' },
}

export default function SourceCheckPanel({ onChecked, onOpenContract }: { onChecked: () => void; onOpenContract: (id: number) => void }) {
  const [sources, setSources] = useState<SourceStatus[] | null>(null)
  const [alerts, setAlerts] = useState<CheckAlert[]>([])
  const [busy, setBusy] = useState(false)
  const [force, setForce] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => { getSyncStatus().then(setSources).catch(e => setError(errMsg(e))) }, [])
  useEffect(load, [load])

  async function check() {
    setBusy(true)
    setError(null)
    try {
      const res = await runSourceCheck(force)
      setAlerts(res.alerts)
      load()
      onChecked()
    } catch (e) {
      setError(errMsg(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="mr-auto">
          <h2 className="font-display text-lg font-semibold text-ink">Live check against the official source</h2>
          <p className="text-xs text-faint">Compares the stored statute text with the Act on India Code. Stored text is never overwritten automatically.</p>
        </div>
        <label className="flex items-center gap-1 text-xs text-muted">
          <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)} className="accent-brand" /> re-download
        </label>
        <button onClick={() => void check()} disabled={busy} className="btn-primary">Check now</button>
      </div>

      {busy && <Spinner label="Downloading the Acts and comparing sections… (large Acts can take a minute)" />}
      {error && <ErrorBox message={error} />}
      {!sources && !error && <Spinner />}

      <ul className="space-y-2">
        {sources?.map(s => {
          const o = OUTCOME[s.outcome] ?? OUTCOME.never_checked
          return (
            <li key={s.source_id} className="rounded-xl border border-line bg-ink/[0.02] p-3.5 transition hover:border-line-strong">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-ink">{s.short_name ?? s.title}</span>
                <span className={`rounded-full border px-2 py-0.5 text-xs ${o.cls}`}>{o.label}</span>
                {s.changed_since_last && <span className="rounded-full border border-warn/40 px-2 py-0.5 text-xs text-warn">official document changed since the last check</span>}
                <span className="ml-auto text-xs text-faint">{s.last_checked ? `last checked ${new Date(s.last_checked).toLocaleString()}` : 'not checked yet'}</span>
              </div>
              {Object.keys(s.counts).length > 0 && (
                <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted">
                  {Object.entries(s.counts).map(([k, v]) => <span key={k}>{k.replace(/_/g, ' ')}: {v}</span>)}
                </div>
              )}
              {s.error && <div className="mt-1 text-xs text-faint">{s.error}</div>}
              {s.flagged.map(f => (
                <div key={f.section_number} className="mt-1 text-xs text-muted">
                  s.{f.section_number}: <span className="text-warn">{f.status.replace(/_/g, ' ')}</span> (similarity {f.score})
                  {f.missing_examples && f.missing_examples.length > 0 && <span className="text-faint"> · not found in the official text: “…{f.missing_examples[0]}…”</span>}
                </div>
              ))}
            </li>
          )
        })}
      </ul>

      {alerts.map(a => (
        <div key={a.change_id} className="rounded-xl border border-warn/40 bg-warn/[0.06] p-3.5">
          <div className="flex items-center gap-2 text-sm text-ink"><Icon name="bell" className="h-4 w-4 text-warn" /> {a.title}</div>
          {a.impacted_clauses.length === 0 && <div className="mt-1 text-xs text-faint">No analysed clause is linked to this section yet.</div>}
          {a.impacted_clauses.map(c => (
            <div key={c.clause_id} className="mt-1 text-xs text-ink/80">
              {c.alert} <button onClick={() => onOpenContract(c.contract_id)} className="font-medium text-warn hover:underline">Open contract →</button>
            </div>
          ))}
        </div>
      ))}
    </Card>
  )
}
