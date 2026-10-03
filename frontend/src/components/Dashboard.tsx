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
    <div className="mx-auto max-w-4xl space-y-8 p-6">
      <div>
        <h1 className="font-serif text-3xl text-white">Contract Intelligence</h1>
        <p className="mt-1 text-sm text-slate-400">Upload a contract to extract clauses, check them against Indian statutes, and see the evidence behind every finding.</p>
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); void handleFile(e.dataTransfer.files[0]) }}
        onClick={() => input.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition ${drag ? 'border-amber-400 bg-amber-400/5' : 'border-white/15 hover:border-white/30'}`}
      >
        <input ref={input} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={e => void handleFile(e.target.files?.[0])} />
        {uploading ? <div className="flex justify-center"><Spinner label="Uploading and extracting clauses…" /></div> : (
          <>
            <Icon name="upload" className="mx-auto h-8 w-8 text-amber-300" />
            <div className="mt-3 text-slate-200">Drag and drop a contract here, or click to browse</div>
            <div className="mt-1 text-xs text-slate-500">PDF, DOCX or TXT · up to 10 MB</div>
          </>
        )}
      </div>

      {error && <ErrorBox message={error} />}

      <section>
        <h2 className="mb-3 font-serif text-xl text-white">Recent contracts</h2>
        {contracts === null && !error ? <Spinner /> : contracts && contracts.length === 0 ? (
          <Empty>No contracts yet. Upload one above.</Empty>
        ) : (
          <div className="space-y-2">
            {contracts?.map(c => (
              <button key={c.id} onClick={() => onOpen(c.id)} className="w-full text-left">
                <Card className="flex items-center gap-3 p-4 transition hover:border-amber-400/40">
                  <Icon name="file" className="h-5 w-5 text-slate-400" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-slate-100">{c.title}</div>
                    <div className="text-xs text-slate-500">{c.doc_type ?? 'contract'} · {c.clauses_count ?? 0} clauses · {new Date(c.created_at).toLocaleString()}</div>
                  </div>
                  <Icon name="right" className="h-4 w-4 text-slate-500" />
                </Card>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
