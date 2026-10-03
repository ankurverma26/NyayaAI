export type RiskLevel = 'high' | 'medium' | 'low' | 'info'

export interface ContractSummary {
  id: number
  title: string
  doc_type: string | null
  jurisdiction: string | null
  created_at: string
  clauses_count: number | null
}

export interface Clause {
  id: number
  contract_id: number
  clause_number: number
  clause_label: string | null
  heading: string | null
  text: string
  clause_type: string | null
  clause_types: string[] | null
  page: number | null
}

export interface ContractDetail extends ContractSummary {
  clauses: Clause[]
}

export interface IngestionResponse {
  contract_id: number
  title: string
  clauses_count: number
  message: string
}

export interface EvidenceRef {
  section_id: number | null
  citation: string | null
  act: string | null
  section_number: string | null
  heading: string | null
  law_status: string | null
  quote: string
  support: string
  verification: string
}

export interface Issue {
  id: number
  rule_id: string | null
  title: string | null
  risk_level: RiskLevel
  category: string | null
  reason: string
  recommendation: string | null
  evidence_status: string | null
  matched_text: string | null
  clause_id: number | null
  clause_number: number | null
  clause_label: string | null
  clause_heading: string | null
  evidence: EvidenceRef[]
}

export interface IssuesResponse {
  contract_id: number
  issues: Issue[]
  disclaimer: string
}

export interface EvidenceRow extends EvidenceRef {
  id: number
  finding_id: number
  finding_title: string | null
  risk_level: RiskLevel | null
}

export interface EvidenceListResponse {
  contract_id: number
  findings_count: number
  evidence: EvidenceRow[]
}

export interface TraceChainStep {
  stage: string
  title: string
  detail: Record<string, unknown>
}

export interface FindingTrace {
  finding_id: number
  contract_id: number
  steps: TraceChainStep[]
}

export interface AgentTraceEntry {
  step: string
  status: 'completed' | 'warning' | 'failed' | string
  detail: Record<string, unknown>
  timestamp: string
}

export interface AgentEvidenceItem {
  source: string
  section: string
  citation: string
  heading: string | null
  law_status: string | null
  quote: string
  support: string
}

export interface AgentEvidenceObject {
  claim: string
  evidence: AgentEvidenceItem[]
  confidence: string
  status: string
  risk_level?: RiskLevel
}

export interface AskRequest {
  query: string
  contract_id?: number
  clause_text?: string
  intent?: 'legal_qa' | 'clause_explain' | 'contract_risk_audit'
}

export interface AskResponse {
  query: string
  intent: string | null
  answer: string
  confidence: string
  evidence: AgentEvidenceObject[]
  trace: AgentTraceEntry[]
  workflow_engine: string
  agent_run_id: number | null
}

export interface LegalChange {
  id: number
  title: string
  description: string | null
  affected_section_id: number | null
  date: string | null
  processed: boolean
}

export interface ImpactedClause {
  contract_id: number
  contract_title: string
  clause_id: number
  clause_number: number
  clause_label: string | null
  clause_heading: string | null
  alert: string
}

export interface ChangeImpact {
  change_id: number
  title: string
  affected_section_id: number | null
  impacted_clauses: ImpactedClause[]
}

export interface StatuteSummary {
  id: number
  title: string
  short_name: string | null
}
