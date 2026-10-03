# Retrieval comparison (BM25 vs Dense vs Hybrid)

Corpus: 18 sections. Hybrid alpha = 0.5. Hand-labelled sanity benchmarks, not a rigorous evaluation.

## Formal (statute vocabulary) queries (12 evaluated)

| Query | Expected | BM25 rank | Dense rank | Hybrid rank |
|---|---|---|---|---|
| restraint of trade after employment | contract s.27 | 1 | 1 | 1 |
| agreement restraining a lawful profession or business | contract s.27 | 1 | 1 | 1 |
| liquidated damages and penalty for breach | contract s.74 | 1 | 2 | 2 |
| compensation for loss caused by breach of contract | contract s.73 | 1 | 1 | 1 |
| agreement with unlawful object or consideration | contract s.23 | 1 | 1 | 1 |
| agreement in restraint of legal proceedings | contract s.28 | 1 | 1 | 1 |
| contract of indemnity | contract s.124 | 1 | 1 | 1 |
| compensation for failure to protect sensitive personal data | information technology s.43a | 1 | 1 | 1 |
| punishment for disclosure of information in breach of lawful contract | information technology s.72a | 1 | 1 | 1 |
| arbitration agreement must be in writing | arbitration s.7 | 1 | 1 | 1 |
| judicial authority refers parties to arbitration | arbitration s.8 | 1 | 1 | 1 |
| appointment of arbitrators | arbitration s.11 | 1 | 1 | 1 |

| Metric | BM25 | Dense | Hybrid |
|---|---|---|---|
| Hit@1 | 12/12 | 11/12 | 11/12 |
| Hit@3 | 12/12 | 12/12 | 12/12 |
| MRR | 1.00 | 0.96 | 0.96 |

## Plain-language queries (12 evaluated)

| Query | Expected | BM25 rank | Dense rank | Hybrid rank |
|---|---|---|---|---|
| Can my employer stop me from joining a competitor after I quit? | contract s.27 | - | 1 | 3 |
| My contract says I must pay five lakh rupees if I resign early | contract s.74 | 5 | 1 | 3 |
| The company leaked my personal details because of poor security | information technology s.43a | 1 | 1 | 1 |
| If the two sides cannot agree, who picks the arbitrator? | arbitration s.11 | 1 | 1 | 1 |
| Does an arbitration clause have to be written down? | arbitration s.7 | 1 | 2 | 1 |
| The other party broke the contract and I lost money, what can I claim? | contract s.73 | 6 | 1 | 1 |
| Can a contract be valid if its purpose is against the law? | contract s.23 | 5 | 1 | 1 |
| If I promise to cover someone's losses, what is that called? | contract s.124 | 1 | 4 | 1 |
| Someone revealed confidential information they got through a contract | information technology s.72a | 1 | 1 | 1 |
| Can parties agree that nobody may go to court over their disputes? | contract s.28 | 2 | 3 | 2 |
| A court tells the parties to go to arbitration instead; which rule allows that? | arbitration s.8 | 1 | 1 | 1 |
| Was my consent valid if I was pressured or lied to? | contract s.14 | 1 | 1 | 1 |

| Metric | BM25 | Dense | Hybrid |
|---|---|---|---|
| Hit@1 | 7/12 | 9/12 | 9/12 |
| Hit@3 | 8/12 | 11/12 | 12/12 |
| MRR | 0.67 | 0.84 | 0.85 |

