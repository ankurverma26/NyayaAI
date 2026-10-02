# NyayaAI — Indian Legal Reasoning & Contract Intelligence Platform

> **B.Tech AI/ML mini project.** Agentic RAG platform for Indian law.
> Runs entirely offline on an 8 GB RAM laptop — no GPU, no paid APIs.

---

## Features (planned)

| # | Feature |
|---|---------|
| 1 | Contract ingestion — PDF / DOCX → clause splitting |
| 2 | Hybrid retrieval — BM25 + SentenceTransformers over Indian statute corpus |
| 3 | Rule-based risk engine (e.g., ICA §27 non-compete check) |
| 4 | LangGraph agentic workflow — Plan → Retrieve → Verify → Answer |
| 5 | Visible execution trace in React UI |

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10 or 3.11 | Install from [python.org](https://www.python.org/) |
| Node.js | 18 LTS + | Install from [nodejs.org](https://nodejs.org/) |
| Git | any | |
| Ollama *(optional)* | latest | Only needed when `USE_LLM=true` |

---

## Quick Start (Windows — PowerShell)

> **Why `uv`?** The system Python on this machine is 3.14, which lacks pre-built wheels
> for several packages (`pydantic-core`, `faiss-cpu`, etc.).  `uv` auto-downloads
> CPython 3.11 and resolves all wheels without needing Visual Studio Build Tools.

### 1 · Install uv (if not already installed)

```powershell
# Run once — installs the uv binary
(Invoke-WebRequest -Uri https://astral.sh/uv/install.ps1).Content | powershell -
```

### 2 · Clone and enter the repo

```powershell
git clone <repo-url> NyayaAI
cd NyayaAI
```

### 3 · Create a Python 3.11 virtual environment

```powershell
uv venv .venv --python 3.11
# uv will download CPython 3.11 automatically if not installed
```

### 4 · Install CPU-only PyTorch first

```powershell
uv pip install torch==2.4.1+cpu torchvision==0.19.1+cpu `
    --extra-index-url https://download.pytorch.org/whl/cpu
```

### 5 · Install remaining dependencies

```powershell
uv pip install -r requirements.txt
```

> ⏱ Total install time: ~2–4 minutes (first run, downloads ~700 MB).

### 6 · Configure environment

```powershell
Copy-Item .env.example .env
# Open .env — defaults work out of the box (USE_LLM=false)
```

### 7 · Activate the venv

```powershell
.venv\Scripts\Activate.ps1
```

> If you see an execution-policy error:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 8 · Start the FastAPI backend

```powershell
# From the project root (venv active)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: open <http://localhost:8000/health> — should return:
```json
{"status":"ok","service":"NyayaAI","version":"0.1.0","use_llm":false,"embed_model":"all-MiniLM-L6-v2"}
```

OpenAPI docs: <http://localhost:8000/docs>

### 9 · Start the React frontend (new terminal)

```powershell
cd frontend
npm install        # first time only
npm run dev
```

Open <http://localhost:5173> — shows the backend health status live.


---

## Running Tests

```powershell
# From project root with venv active
pytest -v
```

Expected output: all tests in `tests/` pass.

---

## Project Structure

```
NyayaAI/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # pydantic-settings config
│   ├── api/                 # Route handlers (added incrementally)
│   ├── agents/              # LangGraph workflow nodes
│   ├── retrieval/           # BM25 + FAISS hybrid retrieval
│   ├── legal/               # LegalSource interface
│   ├── analysis/            # Risk engine
│   ├── ingestion/           # PDF/DOCX → clause splitting
│   ├── database/            # SQLAlchemy async ORM
│   ├── models/              # Pydantic schemas
│   ├── utils/               # Shared utilities
│   └── jurisdictions/
│       └── india/           # India-specific legal adapter
├── data/
│   ├── laws/                # ← ONLY source of statute text
│   ├── judgments/
│   └── sample_contracts/
├── frontend/                # Vite + React 18 + Tailwind CSS
├── tests/                   # pytest test suite
├── scripts/                 # Utility scripts
├── docs/                    # Extended documentation
├── .env.example
├── requirements.txt
└── pytest.ini
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_LLM` | `false` | Enable Ollama LLM |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Ollama model tag |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `DB_URL` | `sqlite+aiosqlite:///./data/nyaya.db` | Database URL |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `CORS_ORIGIN` | `http://localhost:5173` | React dev server |
| `LOG_LEVEL` | `INFO` | Python log level |

---

## Legal Disclaimer

NyayaAI is an academic research tool. It does **not** constitute legal advice.
All statute text is sourced exclusively from files in `data/laws/`.
When evidence is unavailable, the system outputs *"Source verification required."*
Language is always cautious: *"potential issue"*, *"requires review"* —
**never** *"this is illegal"*.

---

## License

MIT — see `LICENSE`.
