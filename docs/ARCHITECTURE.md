# Architecture

## Request path

A ticket arrives by `POST /api/tickets/`. The view saves it and returns `201` immediately,
then hands off to Celery:

```
process_new_ticket
  └─ chain( embed_ticket → triage_ticket → generate_draft )
```

Nothing that touches a model runs inside the request. The API's p95 stays in the tens of
milliseconds even while the worker is doing 400 ms of cross-encoder work per draft.

Chaining rather than firing three independent tasks matters: `triage_ticket` reads the vector
`embed_ticket` wrote, and `generate_draft` reads the queue that triage assigned to scope
retrieval. Running them in parallel would make each one recompute the previous stage.

## Why one database

Vectors live in Postgres via pgvector rather than in a dedicated vector store. The deciding
factor is filtered search: "tickets like this one, in the billing queue, in German, from the
last 30 days" is one query with a `WHERE` clause and an HNSW index. Split across two systems
it becomes either over-fetch-then-filter (wrong results near the limit) or a sync problem.

At this corpus size (~20k tickets, ~1.5k KB chunks) HNSW in Postgres answers in single-digit
milliseconds. The point where a dedicated store wins is roughly 10M+ vectors, and the write-up
in `README.md` under "What I would build next" is where that migration would start.

## Retrieval design

Bi-encoder recall is cheap and imprecise; cross-encoder scoring is precise and expensive.
Running recall at k=25 and reranking down to k=5 buys most of the precision of full
cross-encoding at ~4% of the cost. The numbers are tunable via `RAG_CANDIDATE_K` / `RAG_TOP_K`.

Search over *tickets* additionally fuses lexical results. Pure vector search reliably fails on
identifiers — order numbers, SKUs, error codes carry no semantic content. Postgres full-text
search catches those, and Reciprocal Rank Fusion (`k=60`) merges the two rankings without
needing the scores to be on a comparable scale.

## The feedback loop

`TriageResult` rows are append-only. Three things follow from that:

1. Accuracy is computable at any point in time by joining prediction to the ticket's current
   label, so a bad deploy shows up as a step change rather than being silently overwritten.
2. `model_version` is stored per row, so two versions running side by side are directly
   comparable on the same traffic.
3. When an agent hits "Reroute", the correction updates the ticket's label — which feeds the
   next centroid recomputation. The model gets better as a by-product of agents doing their job.

## Failure modes considered

| Failure | Handling |
|---|---|
| KB has no answer | Grounding gate returns before any LLM call; agent sees why, with the score |
| LLM hallucinates a citation | Citation validator marks the draft ungrounded; UI shows a warning band |
| Model is unsure of the queue | Below 0.70 confidence nothing is auto-applied; ticket is held |
| OpenAI is down / rate limited | `tenacity` exponential backoff, then the task retries twice |
| Embedding model cold start | Baked into the Docker image; also `lru_cache`d per process |
| Repeated identical text | Redis-cached embeddings keyed by SHA-1, 24h TTL |
| Analytics slow at scale | All aggregation in Postgres; rollups warmed every 5 min by Celery beat |

## Observability

`django-prometheus` middleware exports request latency histograms, DB connection stats and
cache hit rates at `/metrics`. Application logs are single-line JSON. The two numbers worth
alerting on are the fraction of drafts marked ungrounded (KB coverage decaying) and triage
accuracy over a rolling window (model or traffic drift).
