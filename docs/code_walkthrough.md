# Code walkthrough: where things happen

Use this to learn your own project before the review. For each flow, open the files in order and read the named function.

## 1. Uploading a contract
1. `backend/api/contracts.py` → `upload_document`: checks size and file type, then calls the service.
2. `backend/ingestion/service.py` → `ingest_contract`: parses the file in memory (nothing is saved to disk), guesses the contract type (`_infer_doc_type`), saves the Contract and Clauses.
3. `backend/ingestion/document_parser.py` → `parse_document`: PDF, DOCX or TXT to text with page numbers.
4. `backend/ingestion/clause_splitter.py` → `split_into_clauses`: regex on "1.", "Clause 5", "ARTICLE III"; keeps the contract's own number as `clause_label`.
5. `backend/analysis/clause_classifier.py` → `classify_clause`: keyword rules, one clause can have several types.

## 2. Analysing a contract
1. `backend/api/contracts.py` → `analyze` calls `backend/analysis/service.py` → `analyze_contract`.
2. `backend/analysis/risk_engine.py` → `analyze_clauses`: for each clause, applies the rules in `risk_rules.json` (clause type, trigger patterns, document type). `detect_restraint_scope` decides whether a non-compete applies during or after employment.
3. `_EvidenceFinder.find`: asks the retriever for the statute section a rule points to, then takes a verbatim quote (`_best_quote`) and checks it really occurs in the stored text. If not, the finding says "Source verification required."
4. Findings, evidence and `clause_section_links` are saved to the database.
5. "Why this finding?": `backend/api/legal.py` → `finding_trace` rebuilds the chain from the database.

## 3. Searching statutes (hybrid retrieval)
- `backend/retrieval/query_expansion.py`: adds legal synonyms, detects "section 27" and Act names.
- `backend/retrieval/hybrid_retriever.py` → `HybridRetriever.search`: BM25 score + dense (embedding) score, each scaled to 0 to 1, combined with `alpha = 0.5`; a section-number match gets a boost.
- `backend/retrieval/index_builder.py`: loads sections from the database, splits long sections into chunks, embeds them with MiniLM, caches in `data/index/`, re-embeds only changed sections.
- `backend/retrieval/factory.py` → `get_retriever`: one shared retriever, built once (with a lock).

## 4. Asking a question (agent)
1. `backend/api/legal.py` → `ask` → `backend/agents/graph.py` → `run_agent`.
2. `graph.py` wires the nodes with LangGraph; `route_after_verification` decides to answer or retry once.
3. `backend/agents/nodes.py`: `router` (cleans input, picks the intent), `planner`, `retriever` (2 threads), `evidence_verifier` (exists? verbatim? relevant?), `query_expander` (retry), `reasoner` (builds the answer).
4. `backend/agents/guard.py` → `sanitize_user_text`: removes instruction-like text.
5. `backend/agents/llm.py`: `NoLLM` (templates) or `OllamaClient`. The reasoner rejects an LLM answer that cites an unverified section or uses words like "illegal".
6. `backend/agents/persistence.py` saves the trace to `agent_runs`.

## 5. Legal changes
`backend/api/legal.py` → `create_change` finds the section, then `_impacted_clauses` follows `clause_section_links` to the clauses and contracts that may be affected.

## 6. Frontend
`frontend/src/App.tsx` (layout and routes) · `router.tsx` (URL handling) · `api.ts` (all backend calls) · `components/` (Dashboard, Analysis, WhyDrawer, QAChat, LegalChanges).

## Questions you should be able to answer

| Question | Short answer |
|---|---|
| What is RAG, and what makes this "agentic"? | RAG retrieves sources before answering. Here an agent plans searches, verifies sources, and retries, instead of one fixed retrieve-then-answer step. |
| What is BM25? | A keyword ranking function that rewards rare matching words and penalises very long documents. |
| Why hybrid? | Keywords find exact terms like "section 27"; embeddings find paraphrases. Scores are scaled to 0 to 1 and combined. |
| Did hybrid beat BM25 in your tests? | On statute-style wording no (BM25 12/12, hybrid 11/12). On plain-language questions yes (top-3 hits: hybrid 12/12, BM25 8/12). Small hand-labelled sets, so treat it as indicative. See `docs/results.md`. |
| Why verify evidence? | To prevent invented citations: the quote must exist word for word in the stored text. |
| What does the verifier check? | The section exists, the quote is a substring of its text, and the section is relevant to the query. |
| Why a scope check for non-competes? | Restraints during employment and after it are treated differently, so the rule ranks only post-employment ones highest. |
| What is prompt injection, and how do you handle it? | Text such as "ignore previous instructions" hidden in a contract or question. We remove such phrases and treat all user text as data. |
| What does the LLM do? | Only rewords verified evidence. Everything works without it. |
| What is `clause_section_links` for? | It links clauses to statute sections, which lets a legal change find affected clauses. |
| What are the limits? | Small corpus, rule-based, statute-only, sample contracts written by us. |
| What would you build next? | Case law with court hierarchy, law versions over time, contract comparison. |
