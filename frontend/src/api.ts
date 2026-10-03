import axios from 'axios'
import type {
  AskRequest, AskResponse, ChangeImpact, ContractDetail, ContractSummary, EvidenceListResponse,
  FindingTrace, IngestionResponse, IssuesResponse, LegalChange, StatuteSummary,
} from './types'

// Dev: Vite proxies /api to the FastAPI backend. Override with VITE_API_URL if needed.
const baseURL = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ?? ''
const http = axios.create({ baseURL, timeout: 180_000 }) // first /ask call loads the embedding model

export function errMsg(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map((x: { msg?: string }) => x.msg ?? 'invalid input').join('; ')
    if (e.code === 'ERR_NETWORK') return 'Cannot reach the backend. Is it running on port 8000?'
    return e.message
  }
  return e instanceof Error ? e.message : 'Something went wrong'
}

export const listContracts = () => http.get<ContractSummary[]>('/api/contracts').then(r => r.data)
export const getContract = (id: number) => http.get<ContractDetail>(`/api/contracts/${id}`).then(r => r.data)
export const uploadContract = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return http.post<IngestionResponse>('/api/documents/upload', form).then(r => r.data)
}
// Share one in-flight request per contract (React StrictMode runs effects twice in dev).
const analyzing = new Map<number, Promise<unknown>>()
export const analyzeContract = (id: number): Promise<unknown> => {
  const running = analyzing.get(id)
  if (running) return running
  const p = http.post(`/api/contracts/${id}/analyze`).then(r => r.data).finally(() => analyzing.delete(id))
  analyzing.set(id, p)
  return p
}
export const getIssues = (id: number) => http.get<IssuesResponse>(`/api/contracts/${id}/issues`).then(r => r.data)
export const getEvidence = (id: number) => http.get<EvidenceListResponse>(`/api/contracts/${id}/evidence`).then(r => r.data)
export const getFindingTrace = (id: number) => http.get<FindingTrace>(`/api/analysis/findings/${id}/trace`).then(r => r.data)
export const askLegal = (body: AskRequest) => http.post<AskResponse>('/api/legal/ask', body).then(r => r.data)
export const listChanges = () => http.get<LegalChange[]>('/api/legal/changes').then(r => r.data)
export const createChange = (body: { title: string; description?: string; citation: string }) =>
  http.post<ChangeImpact>('/api/legal/changes', body).then(r => r.data)
export const listStatutes = () => http.get<StatuteSummary[]>('/api/statutes').then(r => r.data)
