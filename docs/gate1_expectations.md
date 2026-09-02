# Gate 1 — the ten hand-picked services, and what we expect

Sec. 11, Day 1–2 deliverable ("a side list for Day 4: 5 obviously single-domain
specs and 5 obviously mixed ones, with a written note on why you picked each").
Gate 1, at the end of Day 4, requires the five cohesive services to score
**clearly above** the five mixed ones on `ILSC_mean`.

Machine-readable copy: [`results/gate1_candidates.csv`](../results/gate1_candidates.csv).
Browsing sheet these came from: [`results/gate1_shortlist.csv`](../results/gate1_shortlist.csv)
(regenerate with `python src/gate1_select.py`).

---

## How these were chosen — and what was deliberately *not* used

Each pick is justified below by the service's **stated business capability** —
what its own documentation says it is for. That criterion is independent of all
six ILSC features, which is the whole point.

Three signals were available and rejected as selection criteria:

- **Path structure** is feature **f3**. Choosing "mixed" services because they
  expose many distinct path roots, then testing whether ILSC separates them,
  would make Gate 1 pass by construction. It is also simply wrong here: the AWS
  RPC-over-HTTP specs give every operation its own path, so *Amazon Kinesis*
  shows 27 distinct path roots while doing exactly one thing.
- **Operation names (f2), parameters (f4), schema names (f5)** — same
  circularity.
- **Tag count alone.** `tags` are the author's own grouping and are *not* an
  ILSC feature, so they are shown on the sheet and used as evidence. But a raw
  count misleads in both directions: *Mtaa* carries 5 tags and is single-purpose
  (they are four levels of one address hierarchy), while every Google service
  carries the single tag `projects`, which is a URL artefact rather than a
  statement of capability. Tags are read, not counted.

Provider spread was checked afterwards, not used to select: the ten span nine
providers, so Gate 1 cannot be satisfied by one vendor's house style.

---

## A. Expected COHESIVE — one business capability

| # | Service | Provider | Src | Ops | Author tags |
|---|---|---|---|--:|---|
| C1 | Xero Payroll AU API | xero.com | S2 | 29 | `PayrollAu` |
| C2 | G Suite Vault | googleapis.com | S1 | 28 | `matters` |
| C3 | Cloud Spanner | googleapis.com | S1 | 28 | `projects` |
| C4 | Mtaa API Documentation | mtaa-api.herokuapp.com | S2 | 5 | 4 levels of one hierarchy |
| C5 | KeyVaultManagementClient | azure.com | S1 | 12 | `Vaults` |

**C1 · Xero Payroll AU API** — `S2__xero.com__xero-payroll-au__2.9.4__openapi.yaml`
Its own description: "This is the Xero Payroll API for orgs in Australia
region." One capability, payroll, for one jurisdiction. Every operation touches
an employee, a pay run, a payslip or a leave record — one entity family, one
business process. Xero publishes *separate* specs for Files, Assets and Bank
Feeds, so the vendor has already done the decomposition for us.

**C2 · G Suite Vault** — `S1__googleapis.com-vault-v1-swagger.yaml`
"Archiving and eDiscovery for G Suite." Everything is a *matter* and its
subordinate holds, saved queries and exports. A single legal-discovery workflow
expressed end to end.

**C3 · Cloud Spanner** — `S1__googleapis.com-spanner-v1-swagger.yaml`
"Cloud Spanner is a managed, mission-critical, globally consistent [database]."
Instances, databases, sessions, transactions — the object graph of exactly one
managed database product. The `projects` tag is a URL artefact; the description
carries the justification.

**C4 · Mtaa API Documentation** — `S2__mtaa-api.herokuapp.com__1.0__openapi.yaml`
"A simple REST API to access Tanzania's location information." Five operations
that walk one strict administrative hierarchy: regions → districts → wards →
streets. The most unambiguously single-purpose service in the shortlist, and a
useful small case for the hand-worked example in the Model section.

**C5 · KeyVaultManagementClient** — `S1__azure.com-keyvault-2018-02-14-swagger.yaml`
Management-plane CRUD over one Azure resource type, the key vault. Twelve
operations, one entity.

---

## B. Expected MIXED — several unrelated capabilities in one contract

| # | Service | Provider | Src | Ops | Author tags |
|---|---|---|---|--:|---|
| M1 | NeutrinoAPI | neutrinoapi.com | S1 | 26 | 6 named business domains |
| M2 | The SureVoIP RESTful API | surevoip.co.uk | S2 | 28 | 19 |
| M3 | Paylocity API | paylocity.com | S2 | 30 | 16 |
| M4 | Yunbi | yunbi.com | S1 | 22 | 16 |
| M5 | EtMDB REST API v1 | etmdb.com | S1 | 27 | 18 |

**M1 · NeutrinoAPI** — `S1__neutrinoapi.com-3.3.5-swagger.yaml` — **the exemplar.**
The author's own tags are: `Data Tools`, `E-commerce`, `Geolocation`,
`Imaging`, `Security and Networking`, `Telephony`. The provider *declares* six
unrelated business domains inside one contract. Concretely it offers profanity
filtering, bank-card BIN lookup, email verification, code syntax highlighting,
unit conversion and phone validation. No shared entity exists. If ILSC does not
rank this at the bottom, the metric is not measuring what we claim.

**M2 · The SureVoIP RESTful API** — `S2__surevoip.co.uk__9dcb0dc8__openapi.yaml`
Tags span `calls`, `faxes` and `announcements` (telephony) alongside `billing`
and `charges` (finance), `customers` and `contacts` (CRM), plus `areacodes`
(reference data). Three or four business capabilities behind one contract — the
classic "god service".

**M3 · Paylocity API** — `S2__paylocity.com__2__openapi.yaml`
Payroll-adjacent, but the contract mixes employee records with `Client
Credentials` (authentication), `Company Codes` and `Company-Specific Schema`
(tenant configuration), `Custom Fields` (metadata), and `Direct Deposit`
(payment instructions). Instructive precisely because it is the *low-cohesion*
counterpart to C1: same industry, opposite interface design.

**M4 · Yunbi** — `S1__yunbi.com-v2-swagger.yaml`
A crypto exchange bundling public market data (`depth`, `k`, `markets`,
`trades`), private account state (`members`, `addresses`), wallet movements
(`deposit`, `deposit_address`, `deposits`) and order management (`order`,
`orders`). Four capabilities with different consumers and different security
postures.

**M5 · EtMDB REST API v1** — `S1__etmdb.com-1.0.0-swagger.yaml`
A film database whose contract spans cinemas and showtimes (`cinema`,
`cinema-schedule`), corporate records (`company`, `company-credits`), people
(`filmography`) and titles. Distinct entities joined only by belonging to the
same industry.

---

## What Gate 1 checks

1. Compute `ILSC_mean` for all ten (Day 4, `sanity_check.csv`).
2. Sort descending. **All five C-services must sit above all five M-services.**
3. **M1 (NeutrinoAPI) should be at or near the bottom.** It is the strongest
   case in the set: the vendor itself labels six unrelated domains.
4. **C4 (Mtaa, 5 ops) and C5 (KeyVault, 12 ops) are the size controls.** If they
   score high *because* they are small rather than because they are coherent,
   that is size sensitivity, not cohesion — check `ILSC_norm` against the null
   model before accepting the gate.

**If separation is weak,** the proposal's order applies: suspect tokenization
first (print the tokens and look), then reweight — raise path and schema, lower
name. Fix before the Exp. 1 big run, never after.

**A caveat to record either way.** Ten services chosen by one annotator are a
sanity check, not evidence. Gate 1 protects against gross implementation error;
it is not a validation result and must not be reported as one. The validation
claims rest on Exp. 2 (perturbation) and Exp. 3 (pair-level code correlation).
