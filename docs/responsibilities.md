# Service responsibilities — the ground-truth reference for the code dig

*Day 1–2, empirical track. Proposal Sec. 11: "a one-pager per system: each
service's intended responsibility in 2–3 sentences from its docs."*

This document is the **reference the code dig is checked against**, not a
product of it. It says what each service is *supposed* to do; the dig records
what its endpoints *actually touch*. Where the two disagree, that is a finding,
and the disagreements are listed in §3.

## Provenance of each half — they are not equally strong

| System | Written from | Strength |
|---|---|---|
| Sock Shop | each service's own repository — `README.md`, `service.go` / `*Controller.java`, and the entity types | **Strong.** The source was read directly. |
| Train Ticket | the OpenAPI surface in `specs/benchmarks/trainticket/` plus the naming conventions of the published system | **Weaker — declared.** See the warning below. |

> **The Train Ticket half is derived from the specification surface, not from
> the FudanSELab *Service Guide*.** The plan called for the wiki; it was not
> retrieved, so these entries were written from paths, operation names and
> schema names instead. That makes them **a restatement of the interface**, and
> a restatement of the interface cannot serve as independent ground truth for a
> study correlating the interface against the code. They are adequate for
> orientation and for the Exp. 2 domain grouping; they are **not** adequate as
> the reference for `ρ_derived`. Before Day 8's Train Ticket extraction is used
> in Exp. 3, either the wiki must be retrieved or these entries must be rewritten
> from the Java sources. Tracked as **F-03** in `FLAGS.md`.

Sock Shop's entries carry no such caveat: they were written from the source.

---

## 1. Sock Shop — 5 services, 27 operations

The reference system for `ρ_independent`. Specifications are hand-written and
independent of the code (D-16), which is why this system carries Exp. 3.

### `user` — Go · 15 operations

Owns customer identity and the two things attached to it: postal addresses and
payment cards. It authenticates (`GET /login`, salted SHA-1 against the stored
hash) and registers accounts, and exposes customers, cards and addresses both as
top-level collections and as sub-resources of a customer. It stores nothing
about orders or carts; other services hold a customer by URL and dereference it.

**Domain model:** `User`, `Address`, `Card`. `Links` is a HATEOAS helper, not a
domain type — see the exclusion list.

### `carts` — Java / Spring Boot · 5 operations

Holds one shopping cart per customer id and the items in it. It supports reading
and destroying a whole cart, and adding, updating and removing individual items;
`POST /items` is an upsert that increments quantity when the item is already
present. It knows an item only as `(itemId, quantity, unitPrice)` — it does not
resolve item ids against the catalogue.

**Domain model:** `Cart`, `Item`.

### `catalogue` — Go · 4 operations

Serves the product catalogue out of a MySQL database: a paged and tag-filtered
list, a single sock by id, a count for that same filter, and the list of tags.
It is entirely read-only over HTTP; the data is seeded by the database image.

**Domain model:** `Sock`, `Tag`. `sock_tag` is the join table between them and
is excluded as a relation with no independent identity.

### `orders` — Java / Spring Boot · 2 operations

Composes an order from resources owned by other services: it dereferences the
customer, address, card and cart-item URLs supplied in the request, calls
`payment` for authorisation, calls `shipping` to raise a shipment, and only then
persists the order. `GET /orders` is **not** implemented in the controller — the
hand-written method is commented out and the route is served by Spring Data
REST's exporter over `CustomerOrderRepository`.

**Domain model:** `CustomerOrder`, and the objects it embeds — `Customer`,
`Address`, `Card`, `Item`, `Shipment`.

### `payment` — Go · 2 operations, 1 after D-07

Authorises a payment amount against a fixed decline threshold and returns a
boolean with a message. It is deliberately stateless and has no database; the
whole service is one comparison. After `/health` is stripped it contributes a
single operation and therefore **no within-service pairs at all**.

**Domain model:** `Authorisation`.

---

## 2. Train Ticket — 34 services, 211 operations

*Derived from the specification surface. Read the warning at the top of this
file before using any of it as ground truth.*

### Booking and orders

| Service | Ops | Responsibility |
|---|--:|---|
| `ts-order-service` | 16 | The order record for standard (high-speed) trips: create, query, modify, pay, and the admin-side listing. Holds the ticket's travel details, seat and price alongside the account that booked it. |
| `ts-order-other-service` | 16 | The same contract again for the *other* train category. A deliberate duplication in the original system: same operations, same fields, a separate store. |
| `ts-preserve-service` | 2 | Orchestrates booking for high-speed trips — validates the account, reserves a seat, creates the order and triggers notification. It writes no store of its own. |
| `ts-preserve-other-service` | 2 | The same orchestration for the other train category. |
| `ts-rebook-service` | 3 | Moves an existing order to a different trip, computing and settling the price difference. |
| `ts-cancel-service` | 3 | Cancels an order and computes the refund due. |
| `ts-execute-service` | 3 | Marks a ticket collected and then executed (boarded) — the state machine at the end of an order's life. |

### Travel and routing

| Service | Ops | Responsibility |
|---|--:|---|
| `ts-travel-service` | 13 | Trips for high-speed trains: the trip record, its route, its train type, and the query that returns trip details for a date and station pair. |
| `ts-travel2-service` | 12 | The same for the other train category. |
| `ts-route-service` | 7 | Routes as ordered station sequences with distances; lookup by id, by endpoints, or in bulk. |
| `ts-route-plan-service` | 4 | Ranks candidate routes for a query — cheapest, quickest, fewest stops. Reads routes and trips, stores nothing. |
| `ts-travel-plan-service` | 5 | The user-facing counterpart of route planning: assembles complete travel options across both travel services. |
| `ts-station-service` | 9 | The station registry — names, ids, and bulk name/id translation used by nearly every other service. |
| `ts-train-service` | 8 | Train types and their capacities and speeds. |
| `ts-basic-service` | 4 | An aggregation helper that assembles the trip, route, train type and price a caller would otherwise fetch separately. |
| `ts-seat-service` | 3 | Allocates seats for a trip and reports remaining ticket counts. |

### Money

| Service | Ops | Responsibility |
|---|--:|---|
| `ts-price-service` | 7 | Price configuration per route and train type. |
| `ts-payment-service` | 4 | Records payments and the money attached to an order. |
| `ts-inside-payment-service` | 9 | The account wallet: balance, top-up, paying an order from balance, and the difference owed after a rebooking. |
| `ts-consign-price-service` | 5 | Pricing rules for luggage consignment. |
| `ts-consign-service` | 6 | Luggage consignment records, queryable by account or by order. |

### Accounts and access

| Service | Ops | Responsibility |
|---|--:|---|
| `ts-user-service` | 7 | The user record — registration, lookup by id or name, deletion. |
| `ts-auth-service` | 6 | Credentials and token issue; deliberately separate from the user record. |
| `ts-verification-code-service` | 2 | Generates and verifies a captcha-style code. |
| `ts-security-service` | 6 | Per-account security configuration and the order-rate checks applied before booking. |
| `ts-contacts-service` | 8 | Passenger contacts (name, document type, document number) attached to an account. |
| `ts-avatar-service` | 1 | Stores a user avatar image. |

### Catering

| Service | Ops | Responsibility |
|---|--:|---|
| `ts-food-service` | 9 | Food orders attached to a trip, and the combined query of what is available for a date, station pair and trip. |
| `ts-train-food-service` | 3 | The menu carried on a given trip. |
| `ts-station-food-service` | 5 | Food stores located at stations, and their menus. |

### Platform

| Service | Ops | Responsibility |
|---|--:|---|
| `ts-config-service` | 6 | Named configuration values, read and written at runtime. |
| `ts-notification-service` | 7 | Sends mail on order events — one operation per event type. |
| `ts-news-service` | 1 | Serves a static news feed. |

---

## 3. Where the interface and the intent already disagree

Recorded now, before the dig, so they cannot be rationalised afterwards. Each is
a candidate discordant pair for Exp. 3 (Fig 4).

**`orders`: `GET /orders` has no implementation of its own.** The controller
method is commented out; Spring Data REST exports the repository instead. The
specification describes an endpoint no hand-written code serves. The entity set
is therefore inferred from `CustomerOrder` and what it embeds, not from a
handler — recorded per-endpoint in `endpoint_entities.csv`.

**`user`: `/customers/{id}/cards` and `/customers/{id}/addresses` share one code
path.** Both are the same endpoint function with a different `Attr` value, and
both call `db.GetUserAttributes`, which loads *addresses and cards together*.
Their code-level entity sets are consequently **identical** while their
interfaces are disjoint on path and schema. This is the cleanest discordant pair
in the system and it is exactly the case the proposal predicts — "the interface
sees the path, the code sees the data".

**`catalogue`: three of four endpoints touch the same two tables.** List, get and
size all run the same `sock ⋈ sock_tag ⋈ tag` join, so their code sets are
identical and only `/tags` differs. Code-side variance in this service is
near-zero, which limits how much it can contribute to ρ.

**`payment` contributes nothing to Exp. 3.** One operation after D-07, hence zero
pairs. The five-service system supplies four services' worth of pairs.

---

## 4. Exclusion list — types that are *not* domain entities

The mirror of the generic-schema exclusion on the interface side (D2 [v3]), kept
so both lists can go in the replication package. Everything here was seen on a
traced code path and deliberately not counted.

| Type | Service | Why excluded |
|---|---|---|
| `Links`, `EmbedStruct`, `addressesResponse`, `cardsResponse`, `usersResponse`, `postResponse`, `GetRequest`, `registerRequest`, `addressPostRequest`, `cardPostRequest` | user | HATEOAS wrappers and transport request/response shapes — no identity, no persistence |
| `Health` | user, catalogue, payment, carts, orders | health-probe payload, not domain |
| `sock_tag` | catalogue | join table; the relation between `Sock` and `Tag`, with no identity of its own |
| `CartResource`, `ItemResource`, `CartDAO`, `ItemDAO`, `FoundItem`, `HasContents`, `Contents`, `Resource`, `FirstResultOrDefault` | carts | DAO and resource-wrapper plumbing around `Cart` and `Item` |
| `NewOrderResource`, `PaymentRequest`, `PaymentResponse` | orders | request/response value objects for outbound calls, not persisted entities |
| `CustomerOrderRepository`, `CartRepository`, `ItemRepository` | orders, carts | base repository interfaces — the rule names these explicitly |
| `HTTPMonitoringInterceptor`, `*Configuration`, `*Config`, `logger`, `tracer`, `span` | all | logging, tracing, configuration |

**The rule applied.** A *domain entity* is a type with identity in the service's
own data model — persisted, or materialised from persistence. Transport DTOs,
wrappers, DAOs, repositories, configuration and observability types are not,
however domain-flavoured their names. Applied uniformly across Go and Java, so
the two languages are not counted by different standards.


---

## 5. Reliability — what has and has not been established

The proposal requires an inter-annotator figure: "re-derive the entity sets for
10 randomly chosen endpoints a second time, independently, and report the
agreement. A single-annotator extraction with no reliability figure is a
standard reviewer objection."

**That figure does not exist yet, and it cannot be self-administered.** The Sock
Shop sets in `results/endpoint_entities.csv` were derived by one reader. A second
pass by the *same* reader measures memory, not reliability, and reporting it as
an agreement figure would be worse than reporting none.

`results/sockshop_reliability_sample.csv` is the blank sheet: 10 endpoints drawn
at `SEED = 42`, with `entities_annotator2` empty and `entities_annotator1`
carried in the last column so it can be hidden while annotating. It needs about
an hour from someone who did not do the first pass.

**Train Ticket has the same requirement and its own sheet.** Run
`python src/entity_extract.py --src <checkout> --sample 10`, fill
`entities_manual` **from the Java sources**, then `--score` it. F-03 applies:
`docs/responsibilities.md` §2 was written from the specifications and must not
be used as the reference.

**What has been established** is narrower and should be described as such: the
extraction rule is written down (§4), applied uniformly across Go and Java, and
every row in `endpoint_entities.csv` carries a `file:line` reference so any
claim in it can be checked against the source. That is auditability, not
reliability, and the paper should not conflate them.
