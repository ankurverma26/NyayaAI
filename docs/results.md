# Results

Measured on the project machine (Windows, Python 3.11, CPU only). Statute corpus: 5 Acts, 18 sections copied from India Code.

## 1. Objectives from the synopsis vs. delivered

| Synopsis objective | Status | Evidence |
|---|---|---|
| Contract ingestion and clause chunking | Done | PDF, DOCX and TXT parsing; numbered, headed and fallback paragraph splitting; multi-label classifier |
| Hybrid statutory retrieval (BM25 + dense) | Done | BM25 plus MiniLM embeddings with section-number boost; numpy cosine similarity is used instead of FAISS (the corpus is small) |
| Agentic reasoning workflow (LangGraph) | Done | 6-node graph with retry, verified evidence and execution trace |
| FastAPI REST backend | Done | 18 endpoints with OpenAPI docs at `/docs` |
| React + Tailwind interface | Done | Dashboard, Analysis workspace, Legal Q&A, Legal Changes |
| Zero operating cost, runs on an 8 GB laptop | Done, see caveat in section 3 | No paid APIs or cloud; peak backend memory 453 MB |

## 2. Retrieval comparison (BM25 vs dense vs hybrid)

Two hand-labelled sets of 12 queries each, run on the 18-section corpus. Each query has one expected section. The hybrid weight (alpha = 0.5) was fixed in advance and not tuned on these queries.

**Formal queries** (reuse statute vocabulary, for example "restraint of trade after employment")

| Metric | BM25 | Dense | Hybrid |
|---|---|---|---|
| Hit@1 | 12/12 | 11/12 | 11/12 |
| Hit@3 | 12/12 | 12/12 | 12/12 |
| MRR | 1.00 | 0.96 | 0.96 |

**Plain-language queries** (little shared vocabulary, for example "Can my employer stop me from joining a competitor after I quit?")

| Metric | BM25 | Dense | Hybrid |
|---|---|---|---|
| Hit@1 | 7/12 | 9/12 | 9/12 |
| Hit@3 | 8/12 | 11/12 | 12/12 |
| MRR | 0.67 | 0.84 | 0.85 |

**All 24 queries together**

| Metric | BM25 | Dense | Hybrid |
|---|---|---|---|
| Hit@1 | 19/24 | 20/24 | 20/24 |
| Hit@3 | 20/24 | 23/24 | 24/24 |
| MRR | 0.84 | 0.90 | 0.90 |
| Worst rank of the expected section | not found / 6 | 4 | 3 |

**What the results show**

- On queries that reuse statute wording, keyword search (BM25) is best. Dense and hybrid each missed one first place: "liquidated damages and penalty for breach" ranked Section 73 above the expected Section 74.
- On plain-language questions BM25 falls to 7/12 first places, and for one query it did not find the expected section at all. Hybrid had the expected section in the top 3 for all 12.
- The methods fail on different queries, which is why combining them helps. "If I promise to cover someone's losses, what is that called?": BM25 rank 1, dense rank 4, hybrid rank 1. "The other party broke the contract and I lost money": BM25 rank 6, hybrid rank 1.
- Hybrid is not always best. For "Can my employer stop me from joining a competitor after I quit?" dense ranked the expected section first and hybrid third, because the keyword scores pulled it down.
- Overall, hybrid is the most robust choice: its worst rank was 3, while BM25 and dense each had queries where they ranked the expected section lower or missed it.

**Caveats to state**

- Small and hand-labelled by the team: 24 queries, one expected section each (other sections may also be relevant). Differences of two or three queries are not statistically meaningful.
- The plain-language set was added **after** the formal set showed that statute-style queries could not separate the methods. Say this openly.
- The corpus has only 18 sections. Results may change with a larger corpus.
- Alpha was not tuned. Tuning it on a separate validation set is future work.

## 3. Memory and latency

| Stage | Time (s) | Peak RAM (MB) | RAM after (MB) |
|---|---|---|---|
| Load statute index (model loads lazily) | 0.3 | 78 | 78 |
| Parse + analyse sample contract (first search loads the embedding model) | 6.6 | 433 | 433 |
| Agent Q&A x5 (template answers, no LLM) | 0.4 | 453 | 453 |

**Peak backend process memory: 453 MB (about 6% of 8 GB).** 18 sections indexed; 8 findings on the sample contract.

Caveats to state:
- The test machine has **31.4 GB RAM**, so this does **not** show the system running on an 8 GB machine. It shows the backend needs well under 8 GB. The accurate claim is "peak backend memory 453 MB".
- The embedding model is loaded lazily, so its memory appears in the second row. The first request after start-up takes about 6 s; later requests are fast. Warming the index at start-up (the `lifespan` step in `main.py`) avoids this.
- Not included: the optional Ollama LLM (a 3B model typically needs a few GB; **not measured**), the Node.js dev server and the browser.

## 4. Automated tests

**114 tests, all passing** (10.15 s).

| Area | Tests |
|---|---|
| Clause classifier, risk rules, evidence | 23 |
| Retrieval (including thread safety and real-corpus checks) | 22 |
| Agent workflow, prompt-injection guard, LLM output guard | 19 |
| API: contracts, statutes | 4 |
| API: analysis, ask, search, traces, legal changes | 7 |
| Database models and statute loader | 24 |
| Ingestion (TXT, DOCX, PDF, splitting) | 8 |
| Config and health | 7 |

Security behaviours covered by tests: instruction-like text in a query or a contract clause is treated as data; an LLM answer citing an unverified section or using non-cautious wording is rejected; rule wording never uses "illegal" or "unenforceable".

## 5. Risk detection on the three sample contracts

These contracts were written to exercise the rules, so this is a **functional check, not an accuracy evaluation**.

| Contract | Clauses | Findings |
|---|---|---|
| Employment agreement | 14 | **Critical:** post-employment non-compete (clause 7). **High attention:** one-sided termination (4), non-solicitation after exit (8), liquidated damages (9), uncapped indemnity (10), arbitrator appointed by the Company (11). **Moderate:** confidentiality without data-protection reference (5), arbitration seat unclear (11) |
| NDA | 6 | **High attention:** restriction on competing after the agreement ends (3), foreign governing law and forum (5) |
| Rental agreement | 8 | **High attention:** forfeiture of the deposit as a penalty (6) |

Each finding that maps to a statute shows a verbatim quote from the loaded Act and its law status. Findings with no statute mapped (foreign law, one-sided termination) say so instead of inventing a citation.

## 6. Example output (employment agreement, clause 7)

> **Critical Review: Post-employment non-compete restriction.** This clause appears to restrict the person from working in a competing business after the relationship ends (stated period: 3 years). Post-employment restraints of this kind may raise issues under the restraint-of-trade provision identified below. This is a potential issue that requires professional legal review; it is not a determination about enforceability.
> Evidence: Indian Contract Act s.27 (verbatim quote from the stored statute text), status shown.
