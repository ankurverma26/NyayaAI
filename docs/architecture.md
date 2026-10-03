# NyayaAI: Architecture

All diagrams are [Mermaid](https://mermaid.js.org/). They render in GitHub, VS Code (Markdown Preview Mermaid Support extension) and https://mermaid.live. What is **implemented** is shown with solid lines; **planned** work is shown dashed.

## 1. System architecture

```mermaid
flowchart LR
  U([User]) --> FE["React + Vite + Tailwind<br/>Dashboard, Analysis, Q&A, Legal Changes"]
  FE -->|"/api (Vite proxy)"| API["FastAPI routers<br/>contracts, documents, legal, trace, statutes"]
  API --> ING["Ingestion<br/>parser, clause splitter, classifier"]
  API --> RISK["Risk engine<br/>risk_rules.json"]
  API --> AG["LangGraph research agent"]
  RISK --> RET
  AG --> RET["Hybrid retriever<br/>BM25 + embeddings + citation boost"]
  RET --> IDX[("Embedding index<br/>data/index")]
  RET --> DB[("SQLite + SQLAlchemy")]
  ING --> DB
  RISK --> DB
  AG --> DB
  LAWS["data/laws/*.json<br/>text copied from India Code"] -->|"load_laws.py"| DB
  AG -.->|"optional"| LLM["Ollama LLM<br/>(wording only)"]
```

**Principle:** the LLM is never the authority. Statute text comes only from the database; the optional LLM may only rephrase verified evidence.

## 2. Agent workflow (LangGraph state machine)

```mermaid
stateDiagram-v2
  [*] --> router
  router --> planner: intent found
  planner --> retriever: research plan
  retriever --> evidence_verifier: candidate sections
  evidence_verifier --> reasoner: evidence verified
  evidence_verifier --> query_expander: nothing verified (first attempt)
  query_expander --> retriever: broadened queries
  evidence_verifier --> reasoner: nothing verified (after one retry)
  reasoner --> [*]
```

| Node | What it does |
|---|---|
| router | Neutralises instruction-like text, picks the intent: `legal_qa`, `clause_explain` or `contract_risk_audit` |
| planner | Builds a research plan (search steps, direct section lookups); for contracts it derives steps from the rule engine's findings |
| retriever | Runs the plan with at most 2 worker threads (RAM limit) |
| evidence_verifier | Checks the section exists, the quote is verbatim from stored text, and the section is relevant |
| query_expander | One retry with broadened queries if nothing was verified |
| reasoner | Builds evidence objects and the answer (template, or LLM with strict output checks); otherwise says "Source verification required." |

Every node appends `{step, status, detail, timestamp}` to the trace, which is saved in `agent_runs` and shown in the UI. This is an audit trail, not hidden reasoning.

## 3. Hybrid retrieval pipeline

```mermaid
flowchart TD
  Q["Query"] --> X["Query expansion<br/>legal synonym map, section and Act detection"]
  X --> B["BM25 keyword scores"]
  X --> D["Dense scores<br/>MiniLM embeddings, best chunk per section"]
  B --> N["Min-max normalisation"]
  D --> N
  N --> F["Weighted fusion<br/>alpha = 0.5"]
  X --> C["Citation boost<br/>exact section number, Act name"]
  C --> F
  F --> R["Ranked sections with scores and sources"]
```

## 4. Ingestion pipeline

```mermaid
flowchart LR
  F["PDF, DOCX or TXT upload<br/>max 10 MB, validated"] --> P["Parser<br/>in memory, page numbers kept"]
  P --> S["Clause splitter<br/>numbering, headings, label"]
  S --> C["Multi-label classifier"]
  C --> D[("Contract + Clauses in DB")]
```

Uploads are parsed from memory and never written to disk; only a SHA-256 hash is kept.

## 5. Risk analysis flow

```mermaid
flowchart TD
  CL["Clause text"] --> TY["Clause types (multi-label)"]
  TY --> RU["Rules in risk_rules.json<br/>pattern + scope + document type"]
  RU --> FI["Finding<br/>level, cautious reason, recommendation"]
  FI --> EV["Evidence lookup via hybrid retriever<br/>rule-mapped statute section"]
  EV --> OK{"Section found<br/>and quote verbatim?"}
  OK -->|"yes"| V["Verified evidence"]
  OK -->|"no"| SV["Source verification required."]
  MC["Missing-clause rules"] --> FI
```

Restraint clauses get a **scope check**: `post_employment`, `during_only` or `unclear`. Only post-employment restraints get the highest priority.

## 6. Database ER diagram

```mermaid
erDiagram
  USER ||--o{ DOCUMENT : uploads
  USER ||--o{ CONTRACT : owns
  DOCUMENT ||--o{ CONTRACT : "parsed into"
  CONTRACT ||--o{ CLAUSE : contains
  CONTRACT ||--o{ RISK_FINDING : has
  CLAUSE ||--o{ RISK_FINDING : triggers
  RISK_FINDING ||--o{ EVIDENCE : "supported by"
  LEGAL_SOURCE ||--o{ SECTION : contains
  SECTION ||--o{ EVIDENCE : quoted
  SECTION ||--o{ CLAUSE_SECTION_LINK : linked
  CLAUSE ||--o{ CLAUSE_SECTION_LINK : linked
  SECTION ||--o{ LEGAL_CHANGE : affected
  CONTRACT ||--o{ AGENT_RUN : "context of"

  CONTRACT {
    int id PK
    string title
    string doc_type
    string jurisdiction
  }
  CLAUSE {
    int id PK
    int contract_id FK
    int clause_number
    string clause_label
    string heading
    text text
    string clause_type
    json clause_types
  }
  LEGAL_SOURCE {
    int id PK
    string title
    string short_name
    string source_type
    string jurisdiction
    string status
    string retrieved_on
    string url
  }
  SECTION {
    int id PK
    int source_id FK
    string section_number
    string heading
    text text
  }
  RISK_FINDING {
    int id PK
    int contract_id FK
    int clause_id FK
    string rule_id
    string risk_level
    string category
    text reason
    string evidence_status
  }
  EVIDENCE {
    int id PK
    int finding_id FK
    int section_id FK
    text quote
    string verification_status
  }
  CLAUSE_SECTION_LINK {
    int id PK
    int clause_id FK
    int section_id FK
    string link_type
    float confidence
  }
  LEGAL_CHANGE {
    int id PK
    string title
    int affected_section_id FK
    bool processed
  }
  AGENT_RUN {
    int id PK
    int run_id
    int contract_id FK
    string step
    string status
    json detail
  }
  DOCUMENT {
    int id PK
    string filename
    string file_hash
  }
  USER {
    int id PK
    string email
  }
```

`clause_section_links` is the first building block of the Legal Impact Graph: it is what lets a legal change find the clauses it may affect.

## 7. Legal change impact (implemented, simple version)

```mermaid
flowchart LR
  A["Contract analysed"] --> B["Clause linked to Section<br/>clause_section_links"]
  C["New legal change recorded<br/>for a section"] --> D["Find links to that section"]
  B --> D
  D --> E["Legal Change Alert<br/>Clause X of Contract Y may be affected"]
```

## 8. Planned: Legal Impact Graph and judicial authority (future work)

```mermaid
flowchart LR
  CT["Contract"] --> CLZ["Clause"]
  CLZ --> SEC["Section"]
  SEC -.-> PR["Legal principle"]
  PR -.-> JU["Judgment"]
  JU -.-> CO["Court and date"]
  JU -.->|"follows, distinguishes, overrules"| JU2["Later judgment"]
  SEC -.->|"versions over time"| V["Act version history"]
```

Dashed items are **not implemented**. Today the system links Contract, Clause and Section only.

## 9. Implemented vs planned

| Capability | Status |
|---|---|
| Clause extraction and multi-label classification | Implemented |
| Hybrid statute retrieval (BM25 + dense) | Implemented |
| Rule-based risk engine with verbatim evidence | Implemented |
| LangGraph research agent with trace | Implemented |
| Prompt-injection guard, cautious wording checks | Implemented |
| Legal change to affected clause alert (simple) | Implemented (mock changes) |
| Judicial hierarchy and case relationships | Planned |
| Temporal versioning of laws | Planned |
| Full Legal Impact Graph | Planned |
| Semantic contract comparison | Planned |
| Multi-jurisdiction adapters | Planned |
