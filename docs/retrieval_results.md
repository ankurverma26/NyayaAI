# Retrieval comparison (BM25 vs Dense vs Hybrid)

Queries evaluated: 12 (hand-labelled; small sanity benchmark). Hybrid alpha = 0.5.

| Query | Expected | BM25 rank | Dense rank | Hybrid rank |
|---|---|---|---|---|
| restraint of trade after employment | contract s.27 | 1 | - | 1 |
| agreement restraining a lawful profession or business | contract s.27 | 1 | - | 1 |
| liquidated damages and penalty for breach | contract s.74 | 1 | - | 1 |
| compensation for loss caused by breach of contract | contract s.73 | 1 | - | 1 |
| agreement with unlawful object or consideration | contract s.23 | 1 | - | 1 |
| agreement in restraint of legal proceedings | contract s.28 | 1 | - | 1 |
| contract of indemnity | contract s.124 | 1 | - | 1 |
| compensation for failure to protect sensitive personal data | information technology s.43a | 1 | - | 1 |
| punishment for disclosure of information in breach of lawful contract | information technology s.72a | 1 | - | 1 |
| arbitration agreement must be in writing | arbitration s.7 | 2 | - | 2 |
| judicial authority refers parties to arbitration | arbitration s.8 | 1 | - | 1 |
| appointment of arbitrators | arbitration s.11 | 1 | - | 1 |

| Metric | BM25 | Dense | Hybrid |
|---|---|---|---|
| Hit@1 | 11/12 | 0/12 | 11/12 |
| Hit@3 | 12/12 | 0/12 | 12/12 |
| MRR | 0.96 | 0.00 | 0.96 |
