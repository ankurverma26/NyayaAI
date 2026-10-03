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
      <div className="border-b border-white/10 px-6 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={onBack} className="text-sm text-slate-400 hover:text-white">← Dashboard</button>
          <h1 className="font-serif text-xl text-white">{contract.title}</h1>
          <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-slate-300">{contract.doc_type ?? 'contract'}</span>
          <button onClick={() => void load(true)} className="ml-auto rounded border border-white/15 px-3 py-1 text-xs text-slate-300 hover:bg-white/10">Re-run analysis</button>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ['Issues', counts.issues, 'text-red-300'],
            ['Warnings', counts.warnings, 'text-yellow-200'],
            ['Verified', counts.verified, 'text-emerald-300'],
            ['Source review required', counts.review, 'text-amber-200'],
          ].map(([label, n, color]) => (
            <Card key={String(label)} className="px-3 py-2"><div className={`text-2xl font-semibold ${color}`}>{n}</div><div className="text-xs text-slate-400">{label}</div></Card>
          ))}
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[360px_1fr]">
        {/* Clause explorer */}
        <section className="flex min-h-0 flex-col border-b border-white/10 lg:border-b-0 lg:border-r">
          <div className="space-y-2 p-3">
            <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-2">
              <Icon name="search" className="h-4 w-4 text-slate-500" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search clauses" className="w-full bg-transparent py-1.5 text-sm outline-none placeholder:text-slate-600" />
            </div>
            <div className="flex gap-2">
              <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className="w-1/2 rounded border border-white/10 bg-[#161a23] px-2 py-1 text-xs">
                <option value="all">All types</option>
                {types.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)} className="w-1/2 rounded border border-white/10 bg-[#161a23] px-2 py-1 text-xs">
                <option value="all">All risk levels</option>
                {(Object.keys(RISK) as RiskLevel[]).map(r => <option key={r} value={r}>{RISK[r].label}</option>)}
              </select>
            </div>
            <div className="text-xs text-slate-500">Clause Explorer · {clauses.length} of {contract.clauses.length}</div>
          </div>
          <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 pb-3">
            {clauses.map(c => {
              const lvl = worstByClause.get(c.id)
              return (
                <li key={c.id}>
                  <button onClick={() => setSelected(selected === c.id ? null : c.id)}
                    className={`w-full rounded-lg border p-2.5 text-left transition ${selected === c.id ? 'border-amber-400/60 bg-amber-400/5' : 'border-white/10 hover:border-white/25'}`}>
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${lvl ? RISK[lvl].dot : 'bg-slate-600'}`} title={lvl ? RISK[lvl].label : 'No issue identified'} />
                      <span className="truncate text-sm text-slate-100">{clauseName(c)}</span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {(c.clause_types ?? []).map(t => <span key={t} className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-slate-300">{t}</span>)}
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
          <div className="flex gap-1 border-b border-white/10 px-4 pt-2">
            {([['issues', 'Issues'], ['evidence', 'Evidence & Citations'], ['trace', 'Research Trace']] as [Tab, string][]).map(([k, label]) => (
              <button key={k} onClick={() => setTab(k)} className={`rounded-t-lg px-4 py-2 text-sm ${tab === k ? 'border-b-2 border-amber-400 text-white' : 'text-slate-400 hover:text-slate-200'}`}>{label}</button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {selectedClause && (
              <Card className="mb-4 p-3">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Selected clause {clauseName(selectedClause)}{selectedClause.page ? ` · page ${selectedClause.page}` : ''}</span>
                  <button onClick={() => setSelected(null)} className="text-amber-300 hover:underline">Show all findings</button>
                </div>
                <p className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap text-sm text-slate-300">{selectedClause.text}</p>
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
    <div className="space-y-3">
      {issues.map(i => (
        <Card key={i.id} className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge level={i.risk_level} />
            <h3 className="text-sm font-medium text-slate-100">{i.title ?? i.rule_id}</h3>
            <span className="text-xs text-slate-500">{i.clause_number != null ? `Clause ${i.clause_label ?? i.clause_number}${i.clause_heading ? ` · ${i.clause_heading}` : ''}` : 'Whole contract'}</span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{i.reason}</p>
          {i.recommendation && <p className="mt-2 text-xs text-slate-400"><span className="text-slate-500">Suggested review: </span>{i.recommendation}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <VerifyBadge status={i.evidence_status} />
            {i.evidence.map((e, k) => <span key={k} className="rounded border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-xs text-amber-200">{e.citation}</span>)}
            <button onClick={() => onWhy(i.id)} className="ml-auto rounded border border-white/15 px-3 py-1 text-xs text-slate-200 hover:bg-white/10">Why this finding?</button>
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
    <div className="space-y-3">
      {rows.length === 0 && <Empty>No statutory evidence is attached to the findings yet.</Empty>}
      {rows.map(r => (
        <Card key={r.id} className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-amber-200">{r.citation}</span>
            <span className="text-sm text-slate-300">{r.heading}</span>
            <VerifyBadge status={r.verification} />
          </div>
          <div className="mt-1 text-xs text-slate-500">{r.act} · law status: {r.law_status ?? 'unknown'}{r.law_status === 'verify_current_status' ? ' (confirm on India Code)' : ''}</div>
          <Quote>{r.quote}</Quote>
          <div className="mt-2 text-xs text-slate-500">Supports finding: {r.finding_title}</div>
        </Card>
      ))}
      {unverified.length > 0 && (
        <Card className="border-amber-500/30 p-4">
          <div className="text-sm font-medium text-amber-200">Source verification required</div>
          <ul className="mt-1 list-disc pl-5 text-xs text-slate-400">{unverified.map(i => <li key={i.id}>{i.title}</li>)}</ul>
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
        <button onClick={() => void start()} disabled={busy} className="rounded-lg bg-amber-400 px-4 py-2 text-sm font-medium text-black hover:bg-amber-300 disabled:opacity-50">Run agent research audit</button>
        <span className="text-xs text-slate-500">Runs the LangGraph workflow: router → planner → retriever → evidence verifier → reasoner.</span>
      </div>
      {busy && <Spinner label="Agents are researching… (the first run loads the search index)" />}
      {error && <ErrorBox message={error} />}
      {run && (
        <>
          <Card className="p-4">
            <div className="mb-2 text-xs text-slate-500">Workflow engine: {run.workflow_engine} · confidence: {run.confidence}</div>
            <p className="whitespace-pre-wrap text-sm text-slate-200">{run.answer}</p>
          </Card>
          <ol className="space-y-3">
            {run.trace.map((t, i) => (
              <li key={i} className="flex gap-3">
                <Icon name={t.status === 'completed' ? 'check' : t.status === 'failed' ? 'fail' : 'warn'}
                  className={`mt-0.5 h-4 w-4 shrink-0 ${t.status === 'completed' ? 'text-emerald-400' : t.status === 'failed' ? 'text-red-400' : 'text-amber-300'}`} />
                <div>
                  <div className="text-sm text-slate-100">{t.step.replace(/_/g, ' ')} <span className="text-xs text-slate-500">{new Date(t.timestamp).toLocaleTimeString()}</span></div>
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
