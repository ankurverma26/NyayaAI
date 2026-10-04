# Function reference: what every part of the code does

Files are listed in the order a request flows through them. A leading underscore (`_name`) means "internal helper, used only inside that file".
Files not covered at the end of this document: `document_parser.py`, `statutes.py`, `config.py`, `session.py`, `init_db.py` (they were not part of the code reviewed for this reference).

---

## A. Database (`backend/database/models.py`)
Each class is one table. SQLAlchemy turns the classes into SQL tables.

| Class | Purpose |
|---|---|
| `Base` | Parent class for all tables. |
| `User` | Reserved for future logins. Not used yet. |
| `Document` | The uploaded file's record: name, type, SHA-256 hash. (The file itself is not stored.) |
| `Contract` | One analysed contract: title, type (employment, nda, lease...), jurisdiction. |
| `Clause` | One clause of a contract: `clause_number` (1, 2, 3...), `clause_label` (the contract's own "7.2"), heading, text, types, page. |
| `LegalSource` | One Act: title, short name (ICA1872), status, citation, URL, retrieval date. |
| `Section` | One section of an Act: number, heading, text, notes. Its property `citation_str` gives "ICA1872 s.27". |
| `RiskFinding` | One finding: risk level, reason, rule id, which clause, evidence status. |
| `Evidence` | A verbatim quote supporting a finding, plus which section it came from. |
| `AgentRun` | One saved step of an agent run (the trace); `run_id` groups the steps of one run. |
| `LegalChange` | A recorded change to a section (title, affected section, date, processed). |
| `ClauseSectionLink` | Links a clause to a section. This is what lets a legal change find affected clauses. |

## B. Loading statutes (`scripts/load_laws.py`)
- `_sha256(path)`: fingerprint of a file.
- `_text_hash(text)`: fingerprint of a section's text, to see whether it changed.
- `_is_placeholder(data)`: true if any section still contains the word PLACEHOLDER.
- `_validate(data, path)`: checks the JSON has an act name, valid status and sections.
- `load_file(session, path, dry_run)`: reads one JSON file; creates the Act and its sections, or updates changed ones. Running it twice creates no duplicates.
- `load_all(laws_dir, db_url, dry_run)`: loads every JSON file in `data/laws/` and prints a summary.
- `_parse_args()`: command-line options (`--laws-dir`, `--db-url`, `--dry-run`).

`scripts/validate_laws.py`: `validate_file` checks one law file for missing fields, placeholders, duplicate sections and bad dates; `main` runs it on all files and exits with an error if any fail (the demo launcher uses this).
`scripts/add_retrieved_on.py`: `main` adds a retrieval date to files that lack one.
`scripts/list_corpus.py`: `key` sorts section numbers naturally; `main` prints the Markdown table of Acts and sections.

## C. Ingestion (uploading a contract)

### `backend/ingestion/service.py`
- `_infer_doc_type(title, full_text)`: guesses the contract type (employment, nda, lease, loan, service, other) by looking for whole words such as "employee" or "tenant" in the title and the first 600 characters.
- `ingest_contract(session, content, filename, ...)`: the main upload function. Parses the file in memory, saves the Document and Contract, splits it into clauses, labels each clause with types, and saves them. Returns the saved objects.

### `backend/ingestion/clause_splitter.py`
- `ExtractedClause`: a plain container for one split clause.
- `classify_clause_type(heading, text)`: an older quick guess of one label. The real classification is in `clause_classifier.py`.
- `_clean_text(text)`: normalises line endings.
- `_estimate_page_for_clause(clause_text, doc)`: finds which page a clause is on by searching for its first 80 characters.
- `split_into_clauses(doc)`: the splitter. Cuts the text wherever a line starts like "1.", "Clause 5", "Article III". Extracts the heading and the contract's own number (`clause_label`). If there is no numbering it splits on blank lines.

### `backend/analysis/clause_classifier.py`
- `_compiled()`: compiles all the regex patterns once and remembers them.
- `classify_clause(heading, text)`: returns every matching label (for example `["termination", "notice_period"]`), or `["other"]`. Heading patterns are broad; body patterns are specific, so common words do not label everything.

## D. Retrieval (finding statute sections)

### `backend/retrieval/tokenizer.py`
- `stem(token)`: strips simple endings (plural "s", "-ing", "-ed", final "e") so "damages" and "damage" match.
- `tokenize(text)`: lowercases, splits into words and numbers, drops stop words, stems. Keeps "27" and "43a".

### `backend/retrieval/query_expansion.py`
- `ExpandedQuery`: the query plus extra terms, section numbers and Act hints. Its property `dense_text` is the text sent to the embedding model.
- `extract_section_refs(query)`: finds "section 27", "s.43A", "sections 73 and 74".
- `detect_act_hints(query)`: finds Act names such as "contract act" or "IT Act".
- `expand_query(query)`: adds legal synonyms (for example "non-compete" adds "restraint of trade"), then returns the `ExpandedQuery`.

### `backend/retrieval/index_builder.py`
- `SectionRecord`: one section prepared for search. Properties: `citation` ("ICA1872 s.27"), `header` (Act, number, heading), `search_text` (header plus text, used by BM25), `content_hash` (detects edits). Method `chunks()` splits long text into pieces for embedding.
- `chunk_text(text, max_words, overlap)`: cuts text into overlapping blocks of about 180 words, because the embedding model reads only about 256 tokens.
- `default_db_url()`: database address from settings, environment or the default file.
- `_to_sync_url(url)`: converts the async database address (`sqlite+aiosqlite`) to a normal one, since retrieval reads with a synchronous connection.
- `load_sections_from_db(db_url)`: reads every section with its Act, skips placeholders, returns `SectionRecord` objects.
- `Embedder`: the interface any embedding backend must follow (a name and an `encode` method).
- `SentenceTransformerEmbedder`: the real embedder. `_load()` loads the model the first time it is needed, under a lock so two threads never load it together. `encode(texts)` returns normalised vectors.
- `get_default_embedder()`: one shared embedder for the whole program.
- `DenseIndex`: the table of embeddings. `update(records, embedder)` embeds only new or changed sections and reuses the rest. `section_scores(query_vec)` gives each section's cosine similarity (best chunk wins). `save(dir)` and `load(dir, model)` write and read `data/index/`; the cache is ignored if the model changed.
- `build_or_update_index(records, embedder, ...)`: load the cache, update it, save it.

### `backend/retrieval/hybrid_retriever.py`
- `SearchResult`: one result with its scores and which method found it; `to_dict()` converts it for the API.
- `_minmax(x)`: rescales scores to the range 0 to 1 so BM25 and embeddings can be added.
- `HybridRetriever`: the search engine.
  - `dense_available`: true if embeddings can be used.
  - `_bm25_raw(q)`: keyword scores for every section.
  - `_dense_raw(q)`: embedding scores for every section.
  - `_boost_mask(q)`: marks sections whose number the user named, or whose Act they named.
  - `search(query, k, mode, alpha)`: expands the query, computes both scores, scales and combines them (`alpha * dense + (1 - alpha) * BM25`), adds the section-number boost, and returns the top `k`. Modes: `hybrid`, `bm25`, `dense`. Results are cached.

### `backend/retrieval/factory.py`
- `build_retriever(...)`: loads sections, builds or updates the embedding index, returns a `HybridRetriever`. Falls back to keyword-only search if embeddings cannot load.
- `get_retriever()`: the shared retriever used by the API. Built once, protected by a lock.
- `reset_retriever()`: forgets it so it is rebuilt after new laws are loaded.

## E. Risk analysis (`backend/analysis/risk_engine.py`)
- `ClauseInput`: a clause as the engine sees it.
- `FindingDraft`: a finding before it is saved (level, reason, recommendation, evidence); `to_dict()`.
- `load_rules(path)`: reads `risk_rules.json` once.
- `_rx(pattern)` and `_compile(pattern)`: compile a regex once and remember it.
- `detect_restraint_scope(text)`: for a non-compete, returns `post_employment`, `during_only` or `unclear`.
- `extract_duration(text)`: finds "three (3) years" and returns "3 years".
- `_snippet(text, pattern)`: the sentence that triggered a rule, shown on the finding.
- `_doc_type_ok(rule, doc_type)`: some rules apply only to some contract types.
- `_section_matches(act_title, number, expected)`: true if a section is the one a rule points to.
- `_best_quote(text, query)`: picks the most relevant passage of a section. It is cut straight from the stored text, so it is always verbatim.
- `_EvidenceFinder`: `find(rule)` searches for the section a rule points to, checks the quote is verbatim, and returns evidence, or "Source verification required."
- `analyze_clauses(clauses, retriever, doc_type)`: the main function. For every clause it classifies, checks every rule, attaches evidence, then adds "missing clause" findings. Sorts by severity.
- `_first_trigger(text, types)`: a fallback pattern for finding the trigger sentence.
- `summarize(findings)`: counts findings by level and verification status; adds the disclaimer.

`backend/analysis/risk_rules.json` is the rule table: each rule has the clause types it applies to, trigger patterns, level, cautious wording and the statute section to cite.

### `backend/analysis/service.py`
- `analyze_contract(session, contract_id)`: runs analysis for a stored contract; one at a time per contract (a lock stops duplicate findings from double requests).
- `_analyze_contract_unlocked(...)`: the real work. Loads clauses, runs the engine, deletes old findings, saves new findings, evidence and clause-section links.
- `list_issues(session, contract_id)`: reads findings with their evidence for the Issues tab, most severe first.

## F. The agent (`backend/agents/`)

### `state.py`
- `AgentState`: the shared notebook all steps read and write (query, plan, evidence, answer, trace).
- `new_state(...)`: creates a fresh one.

### `guard.py`
- `sanitize_user_text(text, max_len)`: removes control characters and instruction-like phrases ("ignore previous instructions"), and reports what it removed.

### `llm.py`
- `LLMUnavailable`: the error raised when the model cannot be used.
- `LLMClient`: the interface. `chat(system, user)` returns text; `suggest_queries(question)` asks for up to 3 alternative search phrasings.
- `NoLLM`: does nothing, so the system uses templates.
- `OllamaClient`: sends the request to the local Ollama server.
- `get_llm_client(use_llm)`: returns `NoLLM` or `OllamaClient` depending on `USE_LLM` in `.env`.

### `nodes.py`
- `_now()`: current time for trace entries.
- `_log(state, step, status, detail)`: adds one entry to the trace.
- `_node(name)`: wraps a step with timing and error handling, so one failing step cannot crash the whole run.
- `_matches(act, number, expected)`: checks if a section is the expected one.
- `_step(...)`: builds one step of the research plan.
- `_cite_numbers(text)`: finds section numbers mentioned in an LLM answer, to check them.
- `make_nodes(retriever, llm)`: builds the six steps:
  - `router`: cleans the input, decides the intent (question, explain a clause, audit a contract).
  - `planner`: writes the research plan.
  - `retrieve`: runs the plan, at most two searches at a time.
  - `verifier`: keeps only sections that exist, whose quote is verbatim, and that are relevant.
  - `expander`: one retry with broader queries if nothing verified.
  - `reasoner`: builds the evidence and the answer; rejects an LLM answer that cites an unverified section or uses non-cautious words.
- `_safe_run(fn, step)`: runs one search, returns the error instead of raising.
- `_confidence(verified)`: "moderate", "low" or "none".
- `_clip(quote)`: shortens a long quote for display.
- `_evidence_item(e)`: formats one evidence entry.
- `_build_evidence_objects(...)`: groups evidence per claim.
- `_provision_lines(verified)`: formats the list of provisions in an answer.
- `_template_answer(...)`: writes the answer without an LLM.

### `graph.py`
- `route_after_verification(state)`: "answer" if evidence was verified (or one retry was used), else "retry".
- `SequentialGraph`: runs the same steps in order without LangGraph (used for tests, and as a fallback). `invoke(state)` runs it.
- `build_graph(retriever, llm, engine)`: builds the LangGraph workflow: nodes, edges and the conditional retry.
- `run_agent(retriever, query, ...)`: the entry point. Runs the graph and returns the final state.

### `persistence.py`
- `persist_trace(session, state)`: saves each trace step as an `agent_runs` row and returns the run id.

## G. API (`backend/api/`)

### `contracts.py`
- `_validate_upload(file, raw_bytes)`: rejects empty, over 10 MB or wrong-type files.
- `upload_document`: `POST /api/documents/upload`. (`upload_contract_alias` is the older hidden path.)
- `ingest_raw_text`: `POST /api/contracts/text`, for pasted text.
- `list_contracts`, `get_contract`, `get_contract_clauses`: read contracts and clauses.
- `analyze`: `POST /api/contracts/{id}/analyze`. `issues`: `GET .../issues`.
- `get_contract_evidence`: `GET .../evidence`, the raw evidence rows.

### `legal.py`
- `_natural_key(number)`: sorts "10", "43A" in natural order.
- `search`: `POST /api/legal/search`.
- `ask`: `POST /api/legal/ask`. Loads the contract's clauses if one is chosen, runs the agent, saves the trace, returns answer, evidence and trace.
- `get_law`: a statute with its sections.
- `_impacted_clauses(session, change)`: follows `clause_section_links` to find clauses linked to a changed section.
- `list_changes`, `create_change`, `change_impact`: the legal-change feature.
- `run_trace`: the saved trace of one agent run.
- `finding_trace`: builds the "Why this finding?" chain from the database.

### `schemas.py`
Pydantic classes that define the shape of every request and response (for example `AskRequest`, `AskResponse`, `AnalysisSummary`, `IssuesResponse`). FastAPI uses them to validate input, shape output and generate `/docs`. `DISCLAIMER` is imported from the risk engine, so the text exists in one place.

## H. Scripts for testing and measurement
- `search_cli.py`: `main` searches from the command line.
- `analyze_contract_cli.py`: `main` analyses a contract file without the database.
- `agent_cli.py`: `_load_contract` parses a contract file; `main` runs the agent and prints answer and trace.
- `compare_retrievers.py`: `rank_of` finds where the expected section ranked; `evaluate` runs a query set; `main` writes the result tables.
- `memory_check.py`: `PeakMonitor` samples memory in a background thread; `ollama_mb` measures the Ollama process; `main` times each stage and writes `docs/results_memory.md`.

## I. Frontend (`frontend/src/`)
- `main.tsx`: starts React.
- `router.tsx`: `parseRoute` turns a URL into a page; `navigate` changes the URL without reloading; `useLocation` re-renders on URL change; `Link` is a link that navigates without reloading.
- `api.ts`: one function per backend endpoint; `errMsg` turns an error into readable text; `analyzeContract` shares one request if called twice at once.
- `App.tsx`: the layout (header, menu, footer with disclaimer) and choosing the page from the URL.
- `components/Dashboard.tsx`: drag-and-drop upload and the recent-contracts list.
- `components/Analysis.tsx`: the main page. Loads the contract and findings (running the analysis if none exist), shows the summary counts, the clause explorer with search and filters, and three tabs: Issues, Evidence & Citations, Research Trace.
- `components/WhyDrawer.tsx`: the side panel that shows the evidence chain for one finding.
- `components/QAChat.tsx`: the Legal Q&A page; sends questions to `/api/legal/ask` and shows answers with expandable citations and the trace.
- `components/LegalChanges.tsx`: adds a legal change and shows which clauses it may affect.
- `components/ui.tsx`: shared pieces: icons, risk badges, spinner, error box, quote block, trace detail view.

## J. Tests (`tests/`)
Each `test_*` function checks one behaviour. `test_retrieval.py` checks search, indexing and thread safety. `test_analysis.py` checks classification, rules and evidence. `test_agents.py` checks the workflow, the injection guard and LLM output checks. `test_api_legal.py` runs the whole API on a temporary database. The others cover config, health, ingestion and the database.
