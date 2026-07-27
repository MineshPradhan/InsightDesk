# Data model

```
┌──────────────────────────────────────┐
│ Ticket                               │
│──────────────────────────────────────│
│ PK id                    uuid        │
│ UQ external_id           varchar(64) │
│    subject               varchar(512)│
│    body                  text        │
│    language              varchar(8)  │◄── idx
│    channel               varchar(32) │
│    customer_email        email       │
│    queue                 enum        │◄── idx  (ground truth)
│    priority              enum        │◄── idx
│    tags                  text[]      │
│    status                enum        │◄── idx
│    agent_response        text        │
│    received_at           timestamptz │◄── idx
│    first_response_at     timestamptz │
│    resolved_at           timestamptz │
│    csat                  smallint    │
└──────────────────────────────────────┘
      │1              │1                │1
      │               │                 │
      ▼1              ▼N                ▼N
┌───────────────┐ ┌──────────────────┐ ┌────────────────────┐
│TicketEmbedding│ │ TriageResult     │ │ ReplyDraft         │
│───────────────│ │──────────────────│ │────────────────────│
│ FK ticket  1:1│ │ FK ticket        │ │ FK ticket          │
│ vector(384)   │ │ predicted_queue  │ │ text               │
│ model_name    │ │ predicted_prio   │ │ citations   jsonb  │
│               │ │ queue_confidence │ │ retrieval_scores   │
│ HNSW cosine   │ │ prio_confidence  │ │ model              │
└───────────────┘ │ sentiment        │ │ prompt_tokens      │
                  │ model_version    │ │ completion_tokens  │
                  │ latency_ms       │ │ latency_ms         │
                  │ accepted_by_agent│ │ grounded    bool   │
                  │ (append-only)    │ │ agent_rating       │
                  └──────────────────┘ │ was_sent    bool   │
                                       └────────────────────┘

┌─────────────────────┐        ┌──────────────────────┐
│ KBArticle           │1      N│ KBChunk              │
│─────────────────────│───────►│──────────────────────│
│ PK id               │        │ FK article           │
│ UQ slug             │        │ chunk_index          │
│    title            │        │ text                 │
│    body             │        │ vector(384)          │
│    category    idx  │        │ UQ (article, index)  │
│    intent      idx  │        │ HNSW cosine          │
│    source_url       │        └──────────────────────┘
└─────────────────────┘
```

## Index strategy

| Index | Table | Why |
|---|---|---|
| HNSW `vector_cosine_ops` | TicketEmbedding, KBChunk | ANN recall; `m=16, ef_construction=64` is the accuracy/build-time knee for this corpus |
| `(status, priority)` | Ticket | The inbox's default sort — open work, most urgent first |
| `(queue, received_at)` | Ticket | Per-queue volume series on the Insights page |
| `(model_version, created_at)` | TriageResult | Accuracy comparison between two model versions |
| GIN on FTS | Ticket | Lexical half of hybrid search (added in the search migration) |

## Design notes

**Why `TriageResult` is a table, not columns on `Ticket`.** Storing the prediction on the
ticket means each new run destroys the last one. Keeping runs as rows makes accuracy a query,
lets two model versions be compared on identical traffic, and turns "the model got worse after
Tuesday's deploy" from a hunch into a chart.

**Why `citations` is JSONB, not a join table.** Citations are written once, read as a whole,
and never queried across drafts. A join table would add a migration and a join for no query
that anyone actually runs. If citation-level analytics ever become a requirement, that is the
moment to normalise it — not before.

**Why `queue` and `predicted_queue` are separate.** The first is what a human decided, the
second is what the model guessed. Collapsing them would make the training signal unrecoverable
the moment an agent corrects a route.
