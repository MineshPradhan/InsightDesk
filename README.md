# InsightDesk

**Support ticket intelligence platform.** Every inbound ticket is embedded, routed to a
queue, prioritised, and answered with a draft grounded in the knowledge base — with the
retrieved passages attached so an agent can check the work before sending.

Built as a portfolio project against a full-stack SWE brief: Django + DRF backend, Next.js
frontend, Postgres/pgvector, Celery + Redis, Docker, GitHub Actions, and a RAG pipeline with
real evaluation rather than a demo notebook.

```
make up      # whole stack on docker compose
make seed    # load both datasets, embed, build the vector index (~6 min)
make test    # backend suite with coverage gate
```

* Console → http://localhost:3000
* API docs → http://localhost:8000/api/docs/
* Metrics → http://localhost:8000/metrics

No API key? Set `LLM_PROVIDER=echo` in `.env` and everything except the final generation step
runs offline.

---

## Why this problem

Support inboxes are the cleanest example of the brief's "collaborate with ops to understand
business logic and automate workflows". The workflow is genuinely manual, the business cares
about a measurable number (time to resolution), and the automation has to be auditable —
nobody ships an LLM that invents refund policy at customers. That constraint is what makes
the RAG design interesting instead of decorative.

## Datasets

| Purpose | Dataset | License | Size |
|---|---|---|---|
| Tickets | [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) · [Kaggle mirror](https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets) | CC-BY-NC-4.0 | ~20k email tickets, EN/DE/FR/ES/PT, labelled with queue, priority, type, tags, agent's first response |
| Knowledge base | [bitext/Bitext-customer-support-llm-chatbot-training-dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset) | CDLA-Sharing-1.0 | 27k intent-labelled Q&A pairs across 27 intents / 11 categories |

`scripts/ingest_tickets.py` loads the first; `scripts/build_kb.py` groups the second by
intent into articles, chunks them sentence-aware, and writes embeddings to pgvector.

The ticket corpus has no timestamps, so ingestion synthesises arrival and resolution times
from a triangular distribution with priority-dependent handle times. That is stated plainly
here because inventing timestamps silently would make every analytics number a lie.

## Architecture

```
Next.js 14 (App Router, TS, Tailwind)
        │  REST
Django 5 + DRF ── Celery ── Redis
        │                     │
   Postgres 16 + pgvector ◄───┘
        │
   ┌────┴──────────────────────────────┐
   │ MiniLM embeddings   (384-d)       │
   │ centroid kNN triage               │
   │ HNSW recall → cross-encoder rerank│
   │ GPT-4o-mini generation            │
   └───────────────────────────────────┘
```

Tickets, vectors and analytics all live in one Postgres. A semantic search can therefore be
filtered by queue, language and date in the same query — no second datastore to keep in sync,
which is the failure mode of bolting a vector DB onto a relational app.

Full write-up: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · schema: [`docs/ERD.md`](docs/ERD.md)

## How triage works

`apps/ml/classifier.py` holds two backends behind one interface:

* **centroid kNN** — mean embedding per queue over all labelled tickets, cosine + temperature
  softmax. No training step, ~5 ms, and it *improves every time an agent hits "Reroute"*,
  because that writes a corrected label back.
* **zero-shot NLI** — `facebook/bart-large-mnli`, used only for cold start when there is no
  labelled history.

Priority comes from urgency cue patterns plus a sentiment signal. Predictions are only
auto-applied above 0.70 confidence; below that the ticket is flagged and waits for a human.
Every inference is written to `TriageResult` and never overwritten, which is what makes
accuracy-over-time and per-model-version comparison possible.

```
python scripts/evaluate_triage.py --sample 1500 --min-accuracy 0.78
```

## How the RAG pipeline stays honest

```
embed → HNSW recall (k=25) → cross-encoder rerank (k=5) → grounding gate → LLM → citation check
```

Three guards, in order:

1. **Grounding gate** — if the best passage scores below `RAG_MIN_SIMILARITY`, no LLM call is
   made at all. The agent gets "nothing in the KB covers this" plus a nudge to write an article.
2. **Constrained prompt** — the model answers only from numbered passages and must cite each
   factual sentence.
3. **Citation validation** — a draft citing `[7]` when five passages were supplied is marked
   ungrounded and surfaced as a warning rather than shipped.

Every draft stores its citations with similarity and rerank scores, so any sentence traces
back to a specific KB chunk.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/tickets/` | Filter by queue, priority, status, language, date, `untriaged=true` |
| `POST` | `/api/tickets/` | Ingest — fires the embed → triage → draft chain |
| `POST` | `/api/tickets/{id}/triage/` | Re-run routing synchronously |
| `POST` | `/api/tickets/{id}/triage/feedback` | Accept or correct — the training signal |
| `POST` | `/api/tickets/{id}/draft/` | Queue a grounded reply |
| `GET` | `/api/tickets/{id}/similar/` | Nearest past tickets and how they were resolved |
| `GET` | `/api/search/?q=&scope=tickets\|kb` | Hybrid FTS + vector search, fused with RRF |
| `GET` | `/api/analytics/{overview,volume,queues,priorities,confusion,deflection}/` | Dashboard data |

OpenAPI schema is generated by drf-spectacular at `/api/schema/`.

## Frontend

Next.js App Router, TypeScript strict, Tailwind with a token set in `tailwind.config.ts`,
SWR for fetching and revalidation, Recharts for the Insights page.

The signature element is the **triage stream**: every arrival as one tick, ordered by time,
height = model confidence, colour = predicted priority. A run of short red ticks means the
model is guessing on urgent work, which is exactly what a support lead needs to see before it
becomes a backlog. Priority is encoded twice — colour plus left-rule weight — so the board
stays readable in greyscale and for colour-blind agents.

`demo/insightdesk-preview.html` is a dependency-free render of the same design with fixture
data. Open it in a browser, no build required.

## Testing, CI, observability

* `pytest` with a 70% coverage gate; `LLM_PROVIDER=echo` stubs generation so CI needs no key
* `ruff` on Python, `eslint` + `tsc --noEmit` on TypeScript
* GitHub Actions: lint → migration drift check → tests → typecheck → build → GHCR image push on `main`
* `django-prometheus` exposes request, DB and cache metrics at `/metrics`
* Structured JSON logs; `/api/healthz/` for load-balancer checks

## Deploying to AWS

The compose file maps onto managed services with no code changes — every dependency is read
from an environment variable:

| Local | AWS |
|---|---|
| `db` (pgvector/pg16) | RDS Postgres 16, `CREATE EXTENSION vector` |
| `redis` | ElastiCache Redis |
| `api` | ECS Fargate service behind an ALB |
| `worker` / `beat` | ECS services, scaled on Redis queue depth |
| `web` | Amplify, or Fargate + CloudFront |
| model cache | S3-backed EFS mount, or baked into the image (the Dockerfile does this) |

## Screenshots

<img width="1840" height="1079" alt="Screenshot_20260728_002854" src="https://github.com/user-attachments/assets/2e17f6cd-defc-45dd-bc9e-77195705a13f" />

<img width="1837" height="1080" alt="Screenshot_20260728_002912" src="https://github.com/user-attachments/assets/702945c5-e903-40f1-bf3b-d0e6a1fd9ba9" />

<img width="1834" height="1079" alt="Screenshot_20260728_002927" src="https://github.com/user-attachments/assets/2190a533-7a4b-4ed7-942e-5bd7ff13debb" />

## Licence

Code MIT. The datasets carry their own terms — CC-BY-NC-4.0 and CDLA-Sharing-1.0 respectively.
Check them before any commercial use.
