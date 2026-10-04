# Limitations and future scope

## Limitations (state these openly)

**Legal data**
- The corpus is small: 5 Acts, 18 sections, chosen for employment-contract issues. Questions outside it return "Source verification required."
- Only **statute text** is used. There is no case law, no judicial hierarchy and no live court data.
- No version history: each Act has one status and a retrieval date. The system does not yet reason about what the law said when a contract was signed.
- Some statuses need manual confirmation (for example the IT Act while the Digital Personal Data Protection Act is phased in).

**Analysis**
- The risk engine is **rule-based** (13 risk rules, 6 missing-clause rules). It finds what the rules describe and will miss unusual wording. It is not a trained model.
- The three sample contracts were written by us to exercise the rules. The system has not been validated on independent real contracts or reviewed by a lawyer, so no accuracy figure is claimed.
- The clause splitter relies on numbering and headings. Scanned PDFs (no OCR) and unnumbered contracts split less reliably.
- "Verified evidence" means the section exists, the quote is verbatim from stored text and the section is relevant. It does **not** mean the legal conclusion is correct.
- The Legal Change feature uses manually entered (mock) changes, and its link between clauses and sections comes only from the rule mappings.

**Retrieval and AI**
- The retrieval benchmark is small (24 hand-labelled queries over 18 sections): BM25 won on statute-style queries and hybrid on plain-language ones. The weight between the two (alpha 0.5) was not tuned.
- The optional local LLM (Ollama) path was tested with a fake LLM but not end to end on a real model, and its memory use was not measured.
- English only.

**Engineering**
- No authentication or per-user isolation yet (the `users` table is reserved).
- SQLite only, and no database migrations (the database is recreated when the schema changes).
- Memory was measured on a 31.4 GB machine; the backend peaked at 453 MB.

## Future scope (roadmap)

| Phase | Work | Builds on |
|---|---|---|
| 3 | **Judicial authority engine:** ingest judgments; court hierarchy; relationships such as follows, distinguishes and overrules, recorded only when supported by evidence | `legal_sources` already has court, date and citation fields |
| 3 | **Conflict detection** between clauses, statutes and judgments | evidence objects already have a `conflicts` field |
| 4 | **Temporal versioning:** Act versions with effective dates; analyse a contract under the law in force when it was signed | `legal_sources.version`, `effective_date` |
| 4 | **Legal Impact Graph:** contract, clause, section, legal principle, judgment; automatic re-analysis when a legal change is added | `clause_section_links`, `legal_changes` |
| 5 | **Semantic contract comparison** (changed obligations, liability, termination) | clause classifier and risk rules |
| 5 | **Multi-jurisdiction adapters** (UK, US, EU) behind a common legal-source interface | jurisdiction field already on sources and contracts |
| Any | Larger corpus; OCR for scanned PDFs; Hindi support | ingestion pipeline |
| Any | Independent evaluation with law students or lawyers; ML-assisted clause classification | sample contracts and test harness |
| Any | Authentication, PostgreSQL, migrations; deployment | models already PostgreSQL-ready |

## Responsible-use statement

NyayaAI provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional. Findings are review priorities, not legal determinations.
