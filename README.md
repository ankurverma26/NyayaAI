# NyayaAI: Indian Legal Reasoning and Contract Intelligence Platform

B.Tech (AI and ML) mini project, Galgotias College of Engineering and Technology, Greater Noida (AKTU).

**Team:** Ankur Verma (2500971530036), Prateek Sharma (2500971530149), Prince Kumar Jha (2500971530151), Yuvraj Gupta (2500971530227)
**Supervisor:** Mr. Bhupesh Pandey

NyayaAI reads a contract (PDF, DOCX or TXT), splits it into clauses, and checks them against a small corpus of Indian statutes. Every finding comes with a verbatim quote from the stored statute text, or says **"Source verification required."** when no source can be verified. It runs locally on a normal laptop: no GPU and no paid APIs.

> This is an academic project. It provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.

## What it does

| Feature | Status |
|---|---|
| Contract ingestion: PDF, DOCX, TXT, clause splitting and multi-label classification | Done |
| Hybrid statute retrieval: BM25 + sentence embeddings + section-number boost | Done |
| Rule-based risk engine (for example, non-compete after employment under Indian Contract Act s.27, penalty clauses under s.74) | Done |
| LangGraph research agent: router, planner, retriever, evidence verifier, reasoner, with a visible trace | Done |
| "Why this finding?" evidence chain for each finding | Done |
| Legal Q&A with citations | Done |
| Legal change alerts (a change to a section flags the clauses linked to it) | Done (changes are entered manually) |
| Optional local LLM (Ollama) for wording of answers | Done, optional |
| Judicial hierarchy, law versioning, contract comparison | Planned (see `docs/limitations_and_future_scope.md`) |

## How it works

```
Contract -> parse -> clauses -> classify -> risk rules -> retrieve statute sections -> verify quote -> finding
Question -> router -> planner -> retriever -> evidence verifier -> reasoner -> cited answer + trace
```

Statute text comes only from the database (loaded from `data/laws/*.json`). The optional LLM can only reword evidence that has already been verified. If its answer cites a section that was not verified, or uses non-cautious wording such as "illegal", the answer is rejected and a template answer is used instead. Diagrams are in `docs/architecture.md`.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy (async), SQLite |
| Retrieval | rank-bm25, sentence-transformers (`all-MiniLM-L6-v2`), cosine similarity with NumPy |
| Agent | LangGraph |
| Optional LLM | Ollama (`qwen2.5:3b`) |
| Frontend | React 19, Vite, TypeScript, Tailwind CSS 4, Axios |
| Testing | pytest, pytest-asyncio |

## Requirements

- Python 3.11 (the tested version; the pinned packages do not support 3.12 or newer)
- Node.js 18 or newer
- Git
- Internet for the first run only (downloads the embedding model, about 90 MB)
- Ollama (optional)

## Setup (Windows PowerShell)

1. **Get the code**
   ```powershell
   git clone https://github.com/ankurverma26/NyayaAI
   cd NyayaAI
   ```
2. **Create and activate a virtual environment with Python 3.11**
   ```powershell
   # Option A: uv (downloads Python 3.11 for you)
   uv venv .venv --python 3.11
   # Option B: if Python 3.11 is installed
   py -3.11 -m venv .venv

   .venv\Scripts\Activate.ps1
   python --version        # must print Python 3.11.x
   ```
   If PowerShell blocks the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
3. **Install PyTorch (CPU build) first**
   ```powershell
   uv pip install torch                                        # uv (the Windows wheel is CPU-only)
   python -m pip install torch --index-url https://download.pytorch.org/whl/cpu   # plain pip
   ```
4. **Install the other packages** (use the same tool as in step 3)
   ```powershell
   uv pip install -r requirements.txt
   python -m pip install -r requirements.txt
   ```
5. **Create the settings file**
   ```powershell
   Copy-Item .env.example .env
   ```
   The defaults work (`USE_LLM=false`).
6. **Check and load the statutes**
   ```powershell
   python scripts/validate_laws.py
   python scripts/load_laws.py
   ```
7. **Start the backend**
   ```powershell
   uvicorn backend.main:app --reload
   ```
   Health check: http://localhost:8000/health. API docs: http://localhost:8000/docs
8. **Start the frontend** (second terminal)
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
   Open http://localhost:5173

**Shortcut:** `scripts\run_demo.bat` runs steps 6 to 8 and opens the browser.

### Try it
1. Upload `data/sample_contracts/employment_agreement_demo.txt` on the dashboard.
2. Open the flagged non-compete clause and click **Why this finding?**
3. Ask a question in **Legal Q&A**, for example "Is a 3-year non-compete after resignation valid?"
4. In **Legal Changes**, add a change for the section shown in the hint and see which clauses are affected.

## Optional: local LLM with Ollama

1. Install Ollama from https://ollama.com and run `ollama pull qwen2.5:3b`.
2. In `.env` set `USE_LLM=true`, then restart the backend.
3. The first question after loading the model is slow. The trace shows whether the LLM was used (`used_llm`) and why a template answer was used instead, if so.

Everything works with `USE_LLM=false`.

## Tests

```powershell
pytest -q
```
114 tests, about 10 seconds. They cover clause classification, risk rules, retrieval (including thread safety), the agent workflow, the prompt-injection guard, the statute loader and the API.

## Project structure

```
NyayaAI/
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # settings from .env
│   ├── api/                     # contracts.py, legal.py, statutes.py, schemas.py
│   ├── ingestion/               # document_parser.py, clause_splitter.py, service.py
│   ├── analysis/                # clause_classifier.py, risk_rules.json, risk_engine.py, service.py
│   ├── retrieval/               # tokenizer.py, query_expansion.py, index_builder.py,
│   │                            # hybrid_retriever.py, factory.py
│   ├── agents/                  # state.py, guard.py, llm.py, nodes.py, graph.py, persistence.py
│   ├── database/                # models.py, session.py, init_db.py
│   ├── legal/, jurisdictions/india/   # reserved for future jurisdiction support
├── data/
│   ├── laws/                    # statute JSON files (source of truth)
│   ├── sample_contracts/        # employment, NDA, rental samples
│   └── judgments/               # empty, reserved for future case law
├── frontend/src/                # App.tsx, router.tsx, api.ts, types.ts, components/
├── scripts/                     # load_laws, validate_laws, search_cli, analyze_contract_cli,
│                                # agent_cli, compare_retrievers, memory_check, run_demo.bat, ...
├── tests/
├── docs/                        # architecture, results, demo script, limitations, slides outline
├── .env.example
├── requirements.txt
└── pytest.ini
```

## API

Interactive documentation: http://localhost:8000/docs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/api/documents/upload` | Upload a contract (multipart) |
| POST | `/api/contracts/text` | Ingest contract text |
| GET | `/api/contracts` | List contracts |
| GET | `/api/contracts/{id}` | Contract with its clauses |
| GET | `/api/contracts/{id}/clauses` | Clauses |
| POST | `/api/contracts/{id}/analyze` | Run the risk analysis |
| GET | `/api/contracts/{id}/issues` | Findings with evidence |
| GET | `/api/contracts/{id}/evidence` | Evidence rows |
| GET | `/api/statutes`, `/api/statutes/{id}` | Loaded statutes |
| POST | `/api/legal/search` | Hybrid statute search |
| POST | `/api/legal/ask` | Ask the research agent |
| GET | `/api/legal/laws/{id}` | A statute with its sections |
| GET, POST | `/api/legal/changes` | List or add legal changes |
| GET | `/api/legal/changes/{id}/impact` | Clauses affected by a change |
| GET | `/api/analysis/{run_id}/trace` | Saved agent trace |
| GET | `/api/analysis/findings/{id}/trace` | Evidence chain for one finding |

## Statutes in the corpus

The corpus covers the Indian Contract Act 1872, the Arbitration and Conciliation Act 1996, the Information Technology Act 2000, the Companies Act 2013 and the Specific Relief Act 1963. Each file in `data/laws/` records its source URL, status and retrieval date.

| Act | Short name | Sections | Status | Retrieved on |
|---|---|---|---|---|
| Arbitration and Conciliation Act, 1996 | ACA1996 | s.7, s.8, s.11 | in_force | 2026-10-03 |
| Companies Act, 2013 | CA2013 | s.166 | in_force | 2026-10-03 |
| Indian Contract Act, 1872 | ICA1872 | s.10, s.14, s.23, s.27, s.28, s.56, s.73, s.74, s.124 | in_force | 2026-10-03 |
| Information Technology Act, 2000 | ITA2000 | s.43A, s.72A | in_force | 2026-10-03 |
| Specific Relief Act, 1963 | SRA1963 | s.14, s.16, s.41 | in_force | 2026-10-03 |

Total: 5 Acts, 18 sections. The status comes from each JSON file; regenerate this table with `python scripts/list_corpus.py` after editing the files.


## Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `USE_LLM` | `false` | Use Ollama to word answers |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `DB_URL` | `sqlite+aiosqlite:///./data/nyaya.db` | Database |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `CORS_ORIGIN` | `http://localhost:5173` | Allowed frontend origin |
| `LOG_LEVEL` | `INFO` | Logging level |

To force keyword-only search, set `$env:USE_DENSE="false"` in the terminal before starting the backend.

## Results

See `docs/results.md`. In short: 114 tests pass; peak backend memory 453 MB measured on a 31.4 GB machine (the optional LLM runs in a separate process and is measured separately); on 24 hand-labelled queries BM25 was best on statute-style wording, while hybrid search found the expected section in the top 3 for all 12 plain-language questions (BM25: 8 of 12).

## Limitations

Small statute corpus; statute text only (no case law yet); rule-based risk engine checked on sample contracts we wrote, not validated on independent contracts; no version history of laws; no login. Details in `docs/limitations_and_future_scope.md`.

## Disclaimer

NyayaAI provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional. It uses cautious wording ("potential issue", "requires review") and does not declare contracts legal or illegal.
