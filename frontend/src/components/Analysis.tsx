import { useCallback, useEffect, useMemo, useState } from 'react'
import { analyzeContract, askLegal, errMsg, getContract, getEvidence, getIssues } from '../api'
import type { AskResponse, Clause, ContractDetail, EvidenceRow, Issue, RiskLevel } from '../types'
import { Card, Detail, Empty, ErrorBox, Icon, Quote, RISK, RiskBadge, Spinner, VerifyBadge } from './ui'
import WhyDrawer from './WhyDrawer'

type Tab = 'issues' | 'evidence' | 'trace'
const clauseName = (c: Clause) => `${c.clause_label ?? c.clause_number}${c.heading ? ` · ${c.heading}` : ''}`

export default function Analysis({ contractId, onBack }: { contractId: number; onBack: () => void }) {
  const [contract, setContract] = useState<ContractDetail | null>(null)
  const [issues, setIssues] = useState<Issue[]>([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('Loading contract…')
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('issues')
  const [selected, setSelected] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [riskFilter, setRiskFilter] = useState('all')
  const [why, setWhy] = useState<number | null>(null)

  const load = useCallback(async (forceAnalyze = false) => {
    setLoading(true)
    setError(null)
    try {
      setStatus('Loading contract…')
      setContract(await getContract(contractId))
      let res = await getIssues(contractId)
      if (forceAnalyze || res.issues.length === 0) {
        setStatus('Analyzing clauses and checking statutes…')
        await analyzeContract(contractId)
        res = await getIssues(contractId)
      }
      setIssues(res.issues)
    } catch (e) {
      setError(errMsg(e))
    } finally {
      setLoading(false)
    }
  }, [contractId])
  useEffect(() => { void load() }, [load])

  const counts = useMemo(() => {
    const c: Record<RiskLevel, number> = { high: 0, medium: 0, low: 0, info: 0 }
    issues.forEach(i => { c[i.risk_level] += 1 })
    return {
      issues: c.high + c.medium,
      warnings: c.low + c.info,
      verified: issues.filter(i => i.evidence_status === 'verified').length,
      review: issues.filter(i => i.evidence_status === 'source_verification_required').length,
    }
  }, [issues])

  const worstByClause = useMemo(() => {
    const m = new Map<number, RiskLevel>()
    issues.forEach(i => {
      if (i.clause_id == null) return
      const cur = m.get(i.clause_id)
      if (!cur || RISK[i.risk_level].rank > RISK[cur].rank) m.set(i.clause_id, i.risk_level)
    })
    return m
  }, [issues])

  const types = useMemo(() => Array.from(new Set((contract?.clauses ?? []).flatMap(c => c.clause_types ?? []))).sort(), [contract])
  const clauses = useMemo(() => (contract?.clauses ?? []).filter(c => {
    const q = search.toLowerCase()
    if (q && !`${c.heading ?? ''} ${c.text}`.toLowerCase().includes(q)) return false
    if (typeFilter !== 'all' && !(c.clause_types ?? []).includes(typeFilter)) return false
    if (riskFilter !== 'all' && worstByClause.get(c.id) !== riskFilter) return false
    return true
  }), [contract, search, typeFilter, riskFilter, worstByClause])

  const selectedClause = contract?.clauses.find(c => c.id === selected) ?? null
  const shownIssues = selectedClause ? issues.filter(i => i.clause_id === selectedClause.id) : issues

  if (loading) return <div className="p-8"><Spinner label={status} /></div>
  if (error || !contract) return <div className="mx-auto max-w-2xl p-8"><ErrorBox message={error ?? 'Contract not found'} onRetry={() => void load()} /></div>

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line bg-canvas px-6 py-5 lg:px-8">
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={onBack} className="rounded-lg px-2 py-1 text-sm text-muted transition hover:bg-ink/5 hover:text-ink">← Dashboard</button>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">{contract.title}</h1>
          <span className="rounded-md border border-line bg-ink/5 px-2 py-0.5 text-xs capitalize text-ink/80">{contract.doc_type ?? 'contract'}</span>
          <button onClick={() => void load(true)} className="btn-ghost ml-auto">Re-run analysis</button>
        </div>
        <Card className="mt-4 grid grid-cols-2 sm:grid-cols-4 sm:divide-x sm:divide-line">
          {[
            ['Issues', counts.issues, 'text-bad'],
            ['Warnings', counts.warnings, 'text-mod'],
            ['Verified', counts.verified, 'text-ok'],
            ['Source review required', counts.review, 'text-warn'],
          ].map(([label, n, color]) => (
            <div key={String(label)} className="px-5 py-4"><div className={`font-display text-3xl font-bold tabular-nums ${color}`}>{n}</div><div className="mt-0.5 text-xs font-medium text-muted">{label}</div></div>
          ))}
        </Card>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[340px_1fr]">
        {/* Clause explorer */}
        <section className="flex min-h-0 flex-col border-b border-line lg:border-b-0 lg:border-r bg-surface">
          <div className="space-y-2 p-3">
            <div className="flex items-center gap-2 rounded-xl border border-line bg-canvas/60 px-3 transition focus-within:border-brand focus-within:shadow-[0_0_0_3px_color-mix(in_srgb,var(--brand)_25%,transparent)]">
              <Icon name="search" className="h-4 w-4 text-faint" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search clauses" className="w-full bg-transparent py-2 text-sm outline-none placeholder:text-faint" />
            </div>
            <div className="flex gap-2">
              <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className="field w-1/2 px-2 py-1.5 text-xs">
                <option value="all">All types</option>
                {types.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)} className="field w-1/2 px-2 py-1.5 text-xs">
                <option value="all">All risk levels</option>
                {(Object.keys(RISK) as RiskLevel[]).map(r => <option key={r} value={r}>{RISK[r].label}</option>)}
              </select>
            </div>
            <div className="text-xs font-medium text-faint">Clause Explorer · {clauses.length} of {contract.clauses.length}</div>
          </div>
          <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 pb-3">
            {clauses.map(c => {
              const lvl = worstByClause.get(c.id)
              return (
                <li key={c.id}>
                  <button onClick={() => setSelected(selected === c.id ? null : c.id)}
                    className={`w-full rounded-xl border p-3 text-left transition ${selected === c.id ? 'border-brand bg-brand/10 shadow-[0_0_24px_-12px_var(--brand)]' : 'border-line bg-surface hover:border-line-strong hover:bg-raised'}`}>
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${lvl ? RISK[lvl].dot : 'bg-faint'}`} title={lvl ? RISK[lvl].label : 'No issue identified'} />
                      <span className="truncate text-sm text-ink">{clauseName(c)}</span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {(c.clause_types ?? []).map(t => <span key={t} className="rounded-md bg-ink/[0.07] px-1.5 py-0.5 text-[10px] text-ink/80">{t}</span>)}
                    </div>
                  </button>
                </li>
              )
            })}
            {clauses.length === 0 && <Empty>No clauses match the filters.</Empty>}
          </ul>
        </section>

        {/* Right workspace */}
        <section className="flex min-h-0 flex-col">
          <div className="m-4 mb-0 inline-flex w-fit gap-1 rounded-xl border border-line bg-raised p-1">
            {([['issues', 'Issues'], ['evidence', 'Evidence & Citations'], ['trace', 'Research Trace']] as [Tab, string][]).map(([k, label]) => (
              <button key={k} onClick={() => setTab(k)} className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${tab === k ? 'bg-surface text-ink shadow-card ring-1 ring-line-strong' : 'text-muted hover:text-ink'}`}>{label}</button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-5 lg:p-6">
            {selectedClause && (
              <Card className="mb-5 border-brand/25 p-4">
                <div className="flex items-center justify-between text-xs text-muted">
                  <span>Selected clause {clauseName(selectedClause)}{selectedClause.page ? ` · page ${selectedClause.page}` : ''}</span>
                  <button onClick={() => setSelected(null)} className="font-medium text-brand hover:underline">Show all findings</button>
                </div>
                <p className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink/80">{selectedClause.text}</p>
              </Card>
            )}
            {tab === 'issues' && <IssuesTab issues={shownIssues} scoped={!!selectedClause} onWhy={setWhy} />}
            {tab === 'evidence' && <EvidenceTab contractId={contractId} issues={issues} />}
            {tab === 'trace' && <TraceTab contractId={contractId} />}
          </div>
        </section>
      </div>
      {why !== null && <WhyDrawer findingId={why} onClose={() => setWhy(null)} />}
    </div>
  )
}

function IssuesTab({ issues, scoped, onWhy }: { issues: Issue[]; scoped: boolean; onWhy: (id: number) => void }) {
  if (issues.length === 0) return <Empty>{scoped ? 'No issue identified from retrieved sources for this clause.' : 'No findings.'}</Empty>
  return (
    <div className="space-y-4">
      {issues.map(i => (
        <Card key={i.id} className="p-5 transition hover:border-line-strong">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge level={i.risk_level} />
            <h3 className="text-[15px] font-semibold text-ink">{i.title ?? i.rule_id}</h3>
            <span className="text-xs text-faint">{i.clause_number != null ? `Clause ${i.clause_label ?? i.clause_number}${i.clause_heading ? ` · ${i.clause_heading}` : ''}` : 'Whole contract'}</span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-ink/80">{i.reason}</p>
          {i.recommendation && <p className="mt-3 rounded-lg border-l-2 border-brand/50 bg-brand/[0.06] px-3 py-2 text-xs leading-relaxed text-ink/80"><span className="font-medium text-brand">Suggested review: </span>{i.recommendation}</p>}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <VerifyBadge status={i.evidence_status} />
            {i.evidence.map((e, k) => <span key={k} className="chip-cite">{e.citation}</span>)}
            <button onClick={() => onWhy(i.id)} className="btn-ghost ml-auto">Why this finding?</button>
          </div>
        </Card>
      ))}
    </div>
  )
}

function EvidenceTab({ contractId, issues }: { contractId: number; issues: Issue[] }) {
  const [rows, setRows] = useState<EvidenceRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { getEvidence(contractId).then(r => setRows(r.evidence)).catch(e => setError(errMsg(e))) }, [contractId])
  const unverified = issues.filter(i => i.evidence_status === 'source_verification_required')
  if (error) return <ErrorBox message={error} />
  if (!rows) return <Spinner />
  return (
    <div className="space-y-4">
      {rows.length === 0 && <Empty>No statutory evidence is attached to the findings yet.</Empty>}
      {rows.map(r => (
        <Card key={r.id} className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-serif text-base font-medium text-cite">{r.citation}</span>
            <span className="text-sm text-ink/80">{r.heading}</span>
            <VerifyBadge status={r.verification} />
          </div>
          <div className="mt-1 text-xs text-faint">{r.act} · law status: {r.law_status ?? 'unknown'}{r.law_status === 'verify_current_status' ? ' (confirm on India Code)' : ''}</div>
          <Quote>{r.quote}</Quote>
          <div className="mt-2 text-xs text-faint">Supports finding: {r.finding_title}</div>
        </Card>
      ))}
      {unverified.length > 0 && (
        <Card className="border-warn/30 bg-warn/[0.04] p-4">
          <div className="text-sm font-medium text-warn">Source verification required</div>
          <ul className="mt-1 list-disc pl-5 text-xs text-muted">{unverified.map(i => <li key={i.id}>{i.title}</li>)}</ul>
        </Card>
      )}
    </div>
  )
}

function TraceTab({ contractId }: { contractId: number }) {
  const [run, setRun] = useState<AskResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function start() {
    setBusy(true)
    setError(null)
    try { setRun(await askLegal({ query: 'Review this contract', contract_id: contractId, intent: 'contract_risk_audit' })) }
    catch (e) { setError(errMsg(e)) }
    finally { setBusy(false) }
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => void start()} disabled={busy} className="btn-primary">Run agent research audit</button>
        <span className="text-xs text-faint">Runs the LangGraph workflow: router → planner → retriever → evidence verifier → reasoner.</span>
      </div>
      {busy && <Spinner label="Agents are researching… (the first run loads the search index)" />}
      {error && <ErrorBox message={error} />}
      {run && (
        <>
          <Card className="p-5">
            <div className="mb-2 text-xs text-faint">Workflow engine: {run.workflow_engine} · confidence: {run.confidence}</div>
            <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{run.answer}</p>
          </Card>
          <ol className="space-y-3">
            {run.trace.map((t, i) => (
              <li key={i} className="flex gap-3">
                <Icon name={t.status === 'completed' ? 'check' : t.status === 'failed' ? 'fail' : 'warn'}
                  className={`mt-0.5 h-4 w-4 shrink-0 ${t.status === 'completed' ? 'text-ok' : t.status === 'failed' ? 'text-bad' : 'text-warn'}`} />
                <div>
                  <div className="text-sm text-ink">{t.step.replace(/_/g, ' ')} <span className="text-xs text-faint">{new Date(t.timestamp).toLocaleTimeString()}</span></div>
                  <Detail data={t.detail} />
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
      {!run && !busy && <Empty>Run the audit to see each agent step: planning, statute search, evidence verification.</Empty>}
    </div>
  )
}
