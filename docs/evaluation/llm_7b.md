# NyayaAI: old vs new answers

Model: `qwen2.5:7b`


---

## Q: Is a 3-year non-compete after resignation valid?

Verified evidence: ICA1872 s.27, ICA1872 s.56, ICA1872 s.28 (confidence: moderate)

### OLD (model call only: 27.9s; old guard would reject this and fall back to the template)

```
A 3-year non-compete clause after resignation could be considered a restraint of trade, which is generally void under the Indian Contract Act, 1872 (ICA1872). Section 27 of the ICA1872 states that agreements restraining a person from practicing a lawful profession are void. Additionally, if the non-compete clause becomes impossible or unlawful after the contract is made, it could also be void under Section 56 of the ICA1872. Professional legal review is recommended to ensure the clause is enforceable.
```

### NEW (reasoner step 61.0s; whole pipeline 70.9s incl. retrieval + query suggestion, used_llm=True, note=None)

## Short Answer
**Basis:** ICA1872 s.27 — Agreement in restraint of trade, void
The agreement may be void to the extent it restrains the employee from exercising a lawful profession, trade or business of any kind after resignation, unless certain conditions are met.

## Relevant Legal Provisions
- **ICA1872 s.27** — Agreement in restraint of trade, void (status: in_force)
  > "Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind, is to that extent void."

Also retrieved, not relied on in the explanation: ICA1872 s.56; ICA1872 s.10; ITA2000 s.72A; ICA1872 s.28

## Legal Explanation
- ICA1872 s.27 states that agreements restraining one from practicing a lawful profession, trade, or business are void.
- Exception 1 under ICA1872 s.27 allows for agreements not to carry on a similar business within specified local limits if the buyer continues the same business in those limits.

## Application to the Question
- Facts given: none stated (duration of non-compete, type of business, geographical limit, and whether the good-will is involved).
- Why it matters: The agreement appears to be void as a restraint on trade unless specific conditions are met.
- Interpretation: If the employee sells the good-will of the business, the agreement may be valid only if the local limits appear reasonable.

## Conclusion
The non-compete clause could be invalid due to the general prohibition in ICA1872 s.27. However, it might be valid under Exception 1 if certain conditions are satisfied. More information on the specific terms and context is needed for a thorough review.

Sources: ICA1872 s.27

This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.


---

## Q: What does section 74 say about penalty clauses?

Verified evidence: ICA1872 s.74, ICA1872 s.73, ITA2000 s.72A, ICA1872 s.28, ITA2000 s.43A (confidence: moderate)

### OLD (model call only: 34.7s; accepted by the old guard)

```
Section 74 of the ICA1872 addresses penalty clauses in contracts. If a contract includes a stipulated sum for breach or another penalty, the aggrieved party can claim reasonable compensation up to the amount specified, even if no actual damage is proven. This section ensures that the compensation is not excessive and does not cover remote or indirect losses.

Sources: ICA1872 s.74; ICA1872 s.73; ITA2000 s.72A; ICA1872 s.28; ITA2000 s.43A
```

### NEW (reasoner step 81.5s; whole pipeline 92.1s incl. retrieval + query suggestion, used_llm=True, note=None)

## Short Answer
**Basis:** ICA1872 s.74 — Compensation for breach of contract where penalty stipulated for
Section 74 of the Indian Contract Act, 1872, allows for compensation in cases where a penalty is stipulated in a contract and breached, but this compensation cannot exceed the amount named as the penalty or the reasonable compensation due.

## Relevant Legal Provisions
- **ICA1872 s.74** — Compensation for breach of contract where penalty stipulated for (status: in_force)
  > "When a contract has been broken, if a sum is named in the contract as the amount to be paid in case of such breach, or if the contract contains any other stipulation by way of penalty, the party complaining of the breach is entitled, whether or not actual damage or loss is proved to have been caused thereby, to receive from the party who has …"

Also retrieved, not relied on in the explanation: ICA1872 s.73; ITA2000 s.72A; ICA1872 s.28; ITA2000 s.43A

## Legal Explanation
- **ICA1872 s.74**: If a sum is specified as a penalty for breach of contract, the aggrieved party can claim that amount or reasonable compensation not exceeding it.
- **Explanation to ICA1827 s.74**: A stipulation for increased interest from the date of default may be considered a penalty.

## Application to the Question
- Facts given: none stated (specifics such as the nature and terms of the contract, the amount named as a penalty, or the breach are not provided).
- Why it matters: Section 74 sets out the limits on compensation when a penalty clause is present in a contract.
- Interpretation: The exact amount that can be claimed depends on whether the stipulated sum is considered reasonable and does not exceed the actual loss.

## Conclusion
Section 74 of the Indian Contract Act, 1872, provides guidance on how to handle penalties in contracts. However, without specific details about the contract terms or breach, it's unclear what exact compensation would be due. Further information regarding the nature of the agreement and the specifics of the breach are needed for a more precise assessment.

Sources: ICA1872 s.74

This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.


---

## Q: Can an employer recover Rs. 5,00,000 as liquidated damages if I resign early?

Verified evidence: ICA1872 s.74, ICA1872 s.73, ITA2000 s.43A (confidence: moderate)

### OLD (model call only: 34.6s; accepted by the old guard)

```
The potential issue here is whether the contract between you and your employer includes a clause for liquidated damages in case of early resignation. Section 74 of the Indian Contract Act, 1872, suggests that if such a clause exists, the employer may be entitled to receive reasonable compensation up to the amount stipulated. However, the compensation should not cover remote or indirect losses. Section 73 further clarifies that the compensation is meant to cover direct losses. Therefore, whether the employer can recover Rs. 5,00,000 as liquidated damages would require a review of the specific terms of your contract and a professional legal assessment.

Sources: ICA1872 s.74; ICA1872 s.73; ITA2000 s.43A
```

### NEW (reasoner step 69.2s; whole pipeline 79.2s incl. retrieval + query suggestion, used_llm=True, note=None)

## Short Answer
**Basis:** ICA1872 s.74 — Compensation for breach of contract where penalty stipulated for; ICA1872 s.73 — Compensation for loss or damage caused by breach of contract
The employer may recover Rs. 5,00,000 as liquidated damages if it is stipulated in the contract and reasonable, but this would require a detailed review of the terms and conditions of the agreement.

## Relevant Legal Provisions
- **ICA1872 s.74** — Compensation for breach of contract where penalty stipulated for (status: in_force)
  > "When a contract has been broken, if a sum is named in the contract as the amount to be paid in case of such breach, or if the contract contains any other stipulation by way of penalty, the party complaining of the breach is entitled, whether or not actual damage or loss is proved to have been caused thereby, to receive from the party who has …"
- **ICA1872 s.73** — Compensation for loss or damage caused by breach of contract (status: in_force)
  > "Such compensation is not to be given for any remote and indirect loss or damage sustained by reason of the breach. Compensation for failure to discharge obligation resembling those created by contract.—When an obligation resembling those created by contract has been incurred and has not been discharged, any person injured by the failure to …"

Also retrieved, not relied on in the explanation: ITA2000 s.43A

## Legal Explanation
- **ICA1872 s.74**: This section allows for recovery of a sum named in the contract as compensation for breach, without proving actual damage.
- **ICA1872 s.73**: Compensation is limited to direct loss or damage, and indirect losses are not recoverable.

## Application to the Question
- Facts given: The amount of Rs. 5,00,000 as liquidated damages for early resignation (duration and nature of agreement unspecified).
- Why it matters: The stipulated sum must be reasonable and directly related to the loss incurred.
- Interpretation: Whether the Rs. 5,00,000 is a reasonable compensation would depend on the specific circumstances and could require further review.

## Conclusion
The recovery of Rs. 5,00,000 as liquidated damages appears to be possible under certain conditions but requires detailed examination of the contract terms and the actual loss incurred. Professional legal review would help clarify if this amount is reasonable and enforceable in this case.

Sources: ICA1872 s.74; ICA1872 s.73

This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.


---

## Q: What law applies to an arbitration agreement?

Verified evidence: ACA1996 s.8, ACA1996 s.7, ACA1996 s.11, ICA1872 s.23 (confidence: moderate)

### OLD (model call only: 32.9s; accepted by the old guard)

```
The Arbitration and Conciliation Act 1996 (ACA1996) requires that an arbitration agreement be in writing. For an application to be entertained under ACA1996 s.8, an original arbitration agreement or a certified copy must be provided. ACA1996 s.11 outlines the process for appointing arbitrators, including the method for selecting a presiding arbitrator. The Indian Contract Act 1872 (ICA1872) s.23 states that the consideration or object of an agreement must be lawful and not forbidden by law or defeat any legal provision. These provisions require professional legal review to ensure compliance with all relevant laws.

Sources: ACA1996 s.8; ACA1996 s.7; ACA1996 s.11; ICA1872 s.23
```

### NEW (reasoner step 1133.8s; whole pipeline 1140.5s incl. retrieval + query suggestion, used_llm=False, note=LLM unavailable; template used (Ollama call failed: HTTPConnectionPool(host='localhost', port=11434): Read timed out. (read timeout=150)))

Question: What law applies to an arbitration agreement?

Provisions retrieved from the local statute corpus that appear relevant:

1. ACA1996 s.7 — Arbitration agreement (status: in_force)
   "(3) An arbitration agreement shall be in writing. (4) An arbitration agreement is in writing if it is contained in— (a) a document signed by the parties;"
2. ACA1996 s.8 — Power to refer parties to arbitration where there is an arbitration agreement (status: in_force)
   "(2) The application referred to in sub-section (1) shall not be entertained unless it is accompanied by the original arbitration agreement or a duly certified copy thereof:"
3. ACA1996 s.11 — Appointment of arbitrators (status: in_force)
   "(3) Failing any agreement referred to in sub-section (2), in an arbitration with three arbitrators, each party shall appoint one arbitrator, and the two appointed arbitrators shall appoint the third arbitrator who shall act as the presiding arbitrator."
4. ICA1872 s.23 — What considerations and objects are lawful, and what not (status: in_force)
   "The consideration or object of an agreement is lawful, unless— it is forbidden by law; or is of such a nature that, if permitted, it would defeat the provisions of any law;"

These provisions are potentially relevant. Whether and how they apply to specific facts requires professional legal review; this is not a determination of legality or enforceability.

This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.


---

## Q: What is a contract of indemnity?

Verified evidence: ICA1872 s.124, ICA1872 s.73, ICA1872 s.10, ICA1872 s.23, ICA1872 s.74 (confidence: moderate)

### OLD (model call only: 33.7s; accepted by the old guard)

```
A contract of indemnity is an agreement where one party promises to protect another from financial loss due to the promisor's actions or the actions of others. This type of contract is considered valid if it meets the general criteria for a contract, such as being made by competent parties and having a lawful object. The compensation for loss or damage from a breach of contract should consider the means available to mitigate the inconvenience caused by the non-performance. If a penalty is stipulated in the contract, the complaining party may receive reasonable compensation up to the amount specified, even if actual damage is not proven.

Sources: ICA1872 s.124; ICA1872 s.73; ICA1872 s.10; ICA1872 s.23; ICA1872 s.74
```

### NEW (reasoner step 69.4s; whole pipeline 78.6s incl. retrieval + query suggestion, used_llm=True, note=None)

## Short Answer
**Basis:** ICA1872 s.124 — 'Contract of indemnity' defined; ICA1872 s.23 — What considerations and objects are lawful, and what not
A contract of indemnity is a promise by one party to save another from loss caused by certain actions, either their own or those of others. However, the specific details and implications of such a contract require further review based on the given facts.

## Relevant Legal Provisions
- **ICA1872 s.124** — 'Contract of indemnity' defined (status: in_force)
  > "A contract by which one party promises to save the other from loss caused to him by the conduct of the promisor himself, or by the conduct of any other person, is called a 'contract of indemnity'."
- **ICA1872 s.23** — What considerations and objects are lawful, and what not (status: in_force)
  > "The consideration or object of an agreement is lawful, unless— it is forbidden by law; or is of such a nature that, if permitted, it would defeat the provisions of any law;"

Also retrieved, not relied on in the explanation: ICA1872 s.73; ICA1872 s.10; ICA1872 s.56

## Legal Explanation
- **Definition**: ICA1872 s.124 defines a contract of indemnity as an agreement where one party promises to save another from loss caused by certain actions.
- **Considerations for Validity**: ICA1872 s.23 outlines that the object or consideration of such agreements must be lawful, meaning it cannot involve injury to others or be opposed to public policy.

## Application to the Question
- **Facts given**: None stated.
- **Why it matters**: The definition and validity criteria for a contract of indemnity are crucial in understanding its nature and potential legal issues.
- **Interpretation (interpretation)**: Whether a particular agreement qualifies as an indemnity contract depends on whether the promised actions or losses fall within the defined scope, and if the consideration is lawful.

## Conclusion
A contract of indemnity involves one party promising to compensate another for specific losses. However, determining its applicability requires knowing the exact circumstances and ensuring that all legal criteria are met. Professional review would help clarify any potential issues.

Sources: ICA1872 s.124; ICA1872 s.23

This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.


---

## Q: Does the GDPR apply to my startup's customer contracts?

Verified evidence: none (confidence: none)

### OLD (model call only: 0.0s; no verified evidence: the LLM is not called)

```
(template only)
```

### NEW (reasoner step 61.2s; whole pipeline 63.3s incl. retrieval + query suggestion, used_llm=True, note=None)

## Short Answer
**Basis:** ICA1872 s.10 — What agreements are contracts; ITA2000 s.72A — Punishment for disclosure of information in breach of lawful contract
The retrieved provisions do not directly address whether the GDPR applies to your startup's customer contracts. The Indian Contract Act and Information Technology Act provisions relate more to contract validity and data protection penalties, respectively, rather than GDPR applicability.

## Provisions Retrieved (only loosely related)
- **ICA1872 s.10** — What agreements are contracts (status: in_force)
  > "All agreements are contracts if they are made by the free consent of parties competent to contract, for a lawful consideration and with a lawful object, and are not hereby expressly declared to be void."
- **ITA2000 s.72A** — Punishment for disclosure of information in breach of lawful contract (status: verify_current_status; verify current status on India Code)
  > "Save as otherwise provided in this Act or any other law for the time being in force, any person including an intermediary who, while providing services under the terms of lawful contract, has secured access to any material containing personal information about another person, with the intent to cause or knowing that he is likely to cause wrongful …"

Also retrieved, not relied on in the explanation: ICA1872 s.28

## Legal Explanation
- ICA1872 s.10: This section defines what agreements are considered contracts under Indian law but does not address the GDPR or its application.
- ITA2000 s.72A: This section deals with penalties for disclosing personal information in breach of a lawful contract, which is somewhat related to data protection but does not directly cover the GDPR.

## Application to the Question
- Facts given: none stated
- Why it matters: The provisions do not provide clear guidance on whether the GDPR applies to customer contracts in India.
- Interpretation: The GDPR is an EU regulation and its applicability in India may depend on specific circumstances, such as the nature of your startup's business and its interactions with individuals within the EU. A review by a legal expert familiar with both Indian law and GDPR would be beneficial.

## Conclusion
The retrieved provisions do not directly address whether the GDPR applies to your startup's customer contracts. The applicability of the GDPR in India is complex and may depend on various factors, including the nature of your business and its interactions with EU individuals. A legal review by an expert familiar with both Indian law and GDPR would provide clarity.

> **Evidence strength: low.** The retrieved provisions are only loosely matched to your request, so treat this explanation as tentative and check the source text.

Sources: ICA1872 s.10; ITA2000 s.72A

This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.
