# Memory and latency results

- Machine RAM: 31.4 GB | dense embeddings: on
- Sections indexed: 18 | findings on sample contract: 8
- Process RSS before loading anything: 46 MB

| Stage | Time (s) | Peak RAM (MB) | RAM after (MB) |
|---|---|---|---|
| Load statute index + embedding model | 0.3 | 78 | 78 |
| Parse + analyse sample contract | 6.6 | 433 | 433 |
| Agent Q&A x5 (templates, no LLM) | 0.4 | 453 | 453 |

**Peak backend process memory: 453 MB (6% of 8 GB).**
Ollama was not running during this test (LLM disabled, USE_LLM=false). Re-run with Ollama loaded to include it.
