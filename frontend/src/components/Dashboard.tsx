import { useCallback, useEffect, useRef, useState } from 'react'
import { errMsg, listContracts, uploadContract } from '../api'
import type { ContractSummary } from '../types'
import { Card, Empty, ErrorBox, Icon, Spinner } from './ui'

const MAX_BYTES = 10 * 1024 * 1024

export default function Dashboard({ onOpen }: { onOpen: (id: number) => void }) {
  const [contracts, setContracts] = useState<ContractSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [drag, setDrag] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    setError(null)
    listContracts().then(setContracts).catch(e => setError(errMsg(e)))
  }, [])
  useEffect(load, [load])

  async function handleFile(file: File | undefined) {
    if (!file) return
    const ext = file.name.toLowerCase().split('.').pop()
    if (!['pdf', 'docx', 'txt'].includes(ext ?? '')) return setError('Please upload a PDF, DOCX or TXT file.')
    if (file.size > MAX_BYTES) return setError('File is larger than 10 MB.')
    setError(null)
    setUploading(true)
    try {
      const res = await uploadContract(file)
      onOpen(res.contract_id)
    } catch (e) {
      setError(errMsg(e))
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-12 px-6 py-10 enter lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:px-10 lg:py-14">
      <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl font-bold tracking-tight text-ink lg:text-5xl">Contract Intelligence</h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-muted">Upload a contract to extract clauses, check them against Indian statutes, and see the evidence behind every finding.</p>
        <ol className="mt-5 flex flex-wrap gap-2 text-xs font-medium text-muted">
          {['Extract clauses', 'Check statutes', 'Show evidence'].map((s, i) => (
            <li key={s} className="flex items-center gap-2 rounded-full border border-line-strong bg-surface px-3 py-1"><span className="flex h-4 w-4 items-center justify-center rounded-full bg-brand-solid text-[10px] font-bold text-on-brand">{i + 1}</span>{s}</li>
          ))}
        </ol>
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); void handleFile(e.dataTransfer.files[0]) }}
        onClick={() => input.current?.click()}
        className={`group cursor-pointer rounded-3xl border-2 border-dashed p-14 text-center transition ${drag ? 'border-brand bg-brand/10' : 'border-line-strong bg-surface hover:border-brand/60 hover:bg-brand/[0.06]'}`}
      >
        <input ref={input} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={e => void handleFile(e.target.files?.[0])} />
        {uploading ? <div className="flex justify-center"><Spinner label="Uploading and extracting clauses…" /></div> : (
          <>
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand/15 ring-1 ring-brand/30 transition group-hover:scale-105 group-hover:bg-brand/25"><Icon name="upload" className="h-6 w-6 text-brand" /></div>
            <div className="mt-4 font-medium text-ink">Drag and drop a contract here, or click to browse</div>
            <div className="mt-1 text-xs text-faint">PDF, DOCX or TXT · up to 10 MB</div>
          </>
        )}
      </div>

      {error && <ErrorBox message={error} />}
      </div>

      <section className="lg:border-l lg:border-line lg:pl-12">
        <h2 className="mb-5 font-display text-xl font-semibold text-ink">Recent contracts</h2>
        {contracts === null && !error ? <Spinner /> : contracts && contracts.length === 0 ? (
          <Empty>No contracts yet. Upload one above.</Empty>
        ) : (
          <div className="space-y-3">
            {contracts?.map(c => (
              <button key={c.id} onClick={() => onOpen(c.id)} className="w-full text-left">
                <Card className="flex items-center gap-4 p-4 transition hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-[0_12px_30px_-12px_color-mix(in_srgb,var(--brand)_45%,transparent)]">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-ink/5 ring-1 ring-line"><Icon name="file" className="h-5 w-5 text-brand" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-ink">{c.title}</div>
                    <div className="text-xs text-faint">{c.doc_type ?? 'contract'} · {c.clauses_count ?? 0} clauses · {new Date(c.created_at).toLocaleString()}</div>
                  </div>
                  <Icon name="right" className="h-4 w-4 text-faint" />
                </Card>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
