# Discordant pairs — where the interface and the code disagree

*Experiment 3 deliverable. Proposal Sec. 10, Day 11–12: "Identify discordant
pairs (high interface similarity, zero code overlap, or the reverse); write
paragraph-length explanations."*

Selected from [`results/discordance.csv`](../results/discordance.csv) — 102 of
906 joined pairs (11.3%) meet the bounds. The bounds select cases for
explanation; **no reported coefficient depends on them.**

The disagreements fall into three kinds, and only the first two were anticipated.

---

## 1. The interface sees the path; the code sees the data

*High interface similarity, zero code overlap.* This is the case the proposal
predicts by name, and it is the most common kind here.

**`ts-inside-payment-service`: `GET …/inside_payment/money` vs
`GET …/inside_payment/payment`** — interface **0.86**, code **0.00**.

The two operations sit under one path prefix, share four of five path tokens
(f3 = 0.80) and almost the same operation-name tokens (f2 = 0.75). Every lexical
signal says they belong together. In the code they touch `Money` and `Payment`
respectively, with no overlap at all: one reads an account balance, the other
records a settled transaction. The URL expresses the service's *organisation*;
the entity sets express its *data*, and here the two genuinely diverge.

**`ts-assurance-service`: `GET /assurances` vs `GET /assurances/types`** —
interface **0.81**, code **0.00**. The second is a reference-data endpoint
enumerating assurance *types*; the first returns assurance *instances*. A path
hierarchy that reads as "the types belonging to these assurances" is, in the
data model, the boundary between an entity and its enumeration. Four of the six
sharpest Train Ticket discordances in this service are this same endpoint
pairing against its siblings.

**Reading.** Interface similarity is not a defective proxy in these cases; it is
measuring something real that the code-side measure does not see. This is the
substance of the "moderate correlation, complementary signal" framing — the two
views carry partly independent information, which is the more interesting result
and is what §Gate 2 records.

---

## 2. The code sees shared state; the interface sees unrelated verbs

*Low interface similarity, complete code overlap.* Rarer, and confined to
Sock Shop's `user` service — which is also the service carrying most of
`ρ_independent` (F-04).

**`user`: `GET /customers` vs `POST /register`** — interface **0.12**, code
**1.00**.

Both touch exactly `{User}`: registration creates one, the collection endpoint
reads them. The interfaces have nothing in common — different methods,
`customers` against `register`, no shared parameters, no shared schema names
(f2 = f3 = f5 = 0.00). The only reason the metric scores them above zero at all
is f1, the dense embedding, which recovers a little of the shared account
semantics from the structured text. **f1 is doing exactly the job it was added
for**, and this pair is the clearest evidence in the study that the embedding
feature is not redundant with the lexical ones.

**`user`: `DELETE /customers/{id}` vs `GET /login`** — interface **0.16**, code
**1.00**. Both touch `{User, Address, Card}`: login materialises a customer's
attributes to return them, and deletion cascades through the same two
collections to remove them. One reads to authenticate and one destroys; the
shared entity set is a fact about the storage model, not about what the
operations mean to a caller. **Whether these two *ought* to score alike is a
genuine question, not an obvious defect** — a reviewer could reasonably argue
either way, and the paper should present it that way.

---

## 3. Exact-name matching under-credits related types — a limitation, not a finding

Not anticipated, and it depresses `ρ` rather than explaining scatter.

`Sim_code` is the Jaccard of entity **name sets**, so `Assurance` and
`AssuranceType` count as entirely unrelated — Jaccard 0.00 — although one is
plainly the classifier of the other. The same happens with `Assurance` against
`AssuranceTypeBean`, and with `Money` against `Payment` in the payment service.

**This is a property of the code-side measure, not of the metric under test.**
Every case of it pushes a pair toward "code says unrelated" while the interface
says related, which inflates the discordance count and **biases `ρ` downward**.
The reported coefficients are therefore, in this specific respect, conservative.

Two ways to address it, both changes to the extraction rule and so both due
before any re-run (see F-04's point 2):

- **Weight by shared morphology** — credit `Assurance`/`AssuranceType` partial
  overlap on a shared stem. Cheap, but it imports lexical similarity into the
  variable that is supposed to be lexically independent of the interface, which
  would compromise the whole comparison. **Not recommended.**
- **Resolve type relationships from the code** — treat a type and the types it
  embeds or is keyed by as connected, using the field declarations already
  parsed. Defensible, because it reads the relationship out of the source rather
  than out of the name.

Recorded here rather than fixed, because changing `Sim_code` after seeing `ρ`
requires saying so, and the change must be applied to both systems identically
or the D-16 comparison breaks.

---

## What this does not include

**The reliability figures are still owed.** Nothing in this document is affected
by them, but every entity set quoted here is single-annotator and should be read
that way until
[`results/sockshop_reliability_sample.csv`](../results/sockshop_reliability_sample.csv)
and `results/entity_agreement_sample.csv` are filled by a second reader (F-03).

**Two Train Ticket services are absent.** `ts-avatar-service` (Python) and
`ts-news-service` (Go) have no extracted entity sets, so no pair from either
appears above.
