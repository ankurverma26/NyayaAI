# Review 2: 10-slide outline

Aim for about 8 minutes: slides 1 to 3 in 2 minutes, the live demo (slides 5 to 6) in 5 minutes, the rest in 2 minutes. Put the live demo between slides 4 and 7. Use diagrams from `architecture.md`.

## 1. Title
NyayaAI: Indian Legal Reasoning and Contract Intelligence Platform. Team names and roll numbers, supervisor Mr. Bhupesh Pandey, department, college.

## 2. Problem
- General chatbots invent statute sections and citations.
- Legal databases are costly and do not review contracts.
- Plain vector search misses exact section numbers.
- Students and small practitioners have no accessible, verifiable tool.

## 3. Objectives
Six objectives from the synopsis, each with a tick where delivered (see `results.md` section 1). Show the ticks only for what is delivered.

## 4. Architecture (diagram)
System architecture diagram. Say: "The LLM is not the authority; the statute database is."

## 5. Live demo, part 1: contract review
Upload, flagged clause 7, "Why this finding?", evidence tab. Use `demo_script.md` from 0:30 to 3:00.

## 6. Live demo, part 2: agent, Q&A, legal change
Research trace, one question, "Source verification required." example, legal change alert. Use `demo_script.md` from 3:00 to 5:00.

## 7. How it works: Agentic RAG
- State machine diagram: router, planner, retriever, verifier, reasoner, with one retry.
- Hybrid retrieval pipeline diagram (BM25 + embeddings + section-number boost).
- Evidence rule: verbatim quote from stored text, or "Source verification required."

## 8. Results
- 114 automated tests passing.
- Retrieval comparison table (12 queries), stated honestly: BM25 12/12, dense 11/12, hybrid 11/12 on statute-style queries. Add the plain-language table once you have run it.
- Peak backend memory 453 MB (about 6% of 8 GB), measured on a larger machine.
- Rules fire as designed on 3 sample contracts.

## 9. Limitations and future scope
Left: honest limitations (small corpus, rule-based, statute-only, synthetic samples). Right: roadmap (judicial hierarchy, temporal versioning, Legal Impact Graph, contract comparison, multi-jurisdiction). Use the "implemented vs planned" table.

## 10. Conclusion and questions
- What was built: an evidence-grounded contract review platform that runs locally, with no paid services.
- What makes it different: verification before generation, an auditable trace, cautious wording, and a path to legal change impact.
- Thank you. Disclaimer: legal information for research and education, not legal advice.

## Speaker tips
- One person drives the demo; another speaks.
- Say "potential issue", not "illegal".
- If asked about accuracy, say it is validated functionally and that independent evaluation is future work.
- Know the one miss in the retrieval table (liquidated damages, s.74 ranked second).
