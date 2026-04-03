# CLAUDE.md

CurioPilot is a local AI article curation system: scrape sources, filter/read with Ollama LLMs, present curated briefings in a React UI. All data stays local (SQLite + ChromaDB + JSON).

## Commands

```bash
# Backend (Python)
uv sync                          # Install all dependencies
curiopilot run --dry-run         # Run discovery pipeline (dry run, no writes)
curiopilot run                   # Run full discovery pipeline
curiopilot serve                 # Start headless API server (port 19231)
curiopilot app                   # Launch desktop app (PyWebView + embedded server)
curiopilot query "topic"         # Query the knowledge base
pytest                           # Run all tests
pytest tests/test_scrapers.py    # Run a single test file

# Frontend (from frontend/ directory)
npm run dev      # Vite dev server (port 5173, proxies /api → localhost:19231)
npm run build    # Build SPA to frontend/dist/ (required for desktop/production) ← run after any frontend changes
npm run lint     # ESLint
```

### Local dev setup

1. `uv sync` — backend deps
2. `cd frontend && npm install` — frontend deps
3. `curiopilot serve` — start backend
4. `cd frontend && npm run dev` — start frontend

## Python Conventions

- Every module starts with `from __future__ import annotations`
- Type hints use `X | None` (not `Optional[X]`); Python 3.11+
- Logging: `log = logging.getLogger(__name__)` at module level (structlog wraps stdlib)
- **Async-first**: `aiosqlite` for DB, `httpx.AsyncClient` for HTTP, all FastAPI routes are `async def`
- **Pydantic BaseModel** for all schemas and config; use `@field_validator` / `@model_validator(mode="after")` for validation
- **Tenacity** for retry logic on external calls (Ollama, HTTP scraping)
- **Protocol classes** for interfaces: `ProgressCallback`, `UiBridge` in `api/app.py`
- **Dataclasses** for internal state objects: `RunResult`, `NoveltyResult`, `FilterFailure`
- Stores (`ArticleStore`, `URLStore`) require explicit `.open()` before use and `.close()` after — managed via FastAPI lifespan in `api/app.py`
- Imports organized: stdlib → third-party → local, with blank lines between

## Frontend Conventions

- **React 19** + **TypeScript 5.9** with `"strict": true`
- **Tailwind CSS v4** via `@tailwindcss/vite` plugin; CSS variable theming (`--color-bg-primary`, etc.); dark mode via `.dark` class
- Import alias `@/` maps to `frontend/src/` (configured in `vite.config.ts`)
- **Lucide React** for all icons
- Custom hooks return `{ data, loading, error, refresh? }` pattern
- State management: React hooks only (no Redux/Zustand); state lifted in `App.tsx`
- Types in `frontend/src/types/index.ts` mirror backend `api/schemas.py` — **must stay in sync manually**
- Some types (Graph, Obsidian, Bookmark) defined inline in `frontend/src/lib/api.ts`
- API client: typed wrapper functions around `fetch` in `lib/api.ts` — no axios

## Architecture

```
React SPA (frontend/src/)
    ↕ HTTP/JSON to /api
FastAPI server (src/curiopilot/api/)
    ↕ reads/writes
SQLite + ChromaDB + JSON files (./data/)
```

**Pipeline** (`curiopilot run`): Scrape → Deduplicate → Filter (7B) → Read (14B) → Novelty score → Generate briefing. Orchestrated via LangGraph StateGraph in `pipeline/graph.py` with checkpoint/resume support. Failed articles go to a dead letter queue (DLQ).

| Path | Purpose |
|------|---------|
| `src/curiopilot/api/` | FastAPI app factory, route modules, schemas, deps |
| `src/curiopilot/pipeline/` | LangGraph orchestration, checkpointing |
| `src/curiopilot/scrapers/` | Per-source scrapers (12 types, registry pattern) |
| `src/curiopilot/agents/` | LLM-based filter, reader, novelty, query, briefing agents |
| `src/curiopilot/storage/` | ArticleStore, URLStore, knowledge graph, taxonomy |
| `src/curiopilot/email_digest.py` | SMTP email rendering and delivery for briefings |
| `src/curiopilot/llm/` | Ollama client wrapper + circuit breaker |
| `src/curiopilot/export/` | Obsidian vault export |
| `frontend/src/components/` | React components (organized by domain) |
| `frontend/src/hooks/` | Data-fetching and UI hooks |
| `frontend/src/lib/api.ts` | Typed API client for all backend endpoints |

## Extension Patterns

### Adding a scraper

1. Create `src/curiopilot/scrapers/<name>.py`
2. Subclass `BaseScraper` (from `scrapers/base.py`), implement `async extract_articles() -> list[ArticleEntry]`
3. Decorate class with `@register_scraper("scraper_key")` (from `scrapers/__init__.py`)
4. Add lazy import in `scrapers/__init__.py` → `get_scraper()` function
5. Add `"scraper_key"` to `KNOWN_SCRAPERS` set in `config.py`
6. Add source entry in `config.yaml`

### Adding an API route

1. Create `src/curiopilot/api/routes/<name>.py` with `router = APIRouter(tags=["<name>"])`
2. Inject deps via `Depends(get_article_store)`, `Depends(get_url_store)`, `Depends(get_config)` from `api/deps.py`
3. Add Pydantic request/response models to `api/schemas.py`
4. Import router and mount in `api/app.py` → `_register_routes()` with `prefix="/api"`
5. Add matching TypeScript types to `frontend/src/types/index.ts`
6. Add client function to `frontend/src/lib/api.ts`

### Adding a frontend hook

1. Create `frontend/src/hooks/use<Name>.ts`
2. Return `{ data, loading, error, refresh? }` object
3. Use `fetchJSON<T>()` from `@/lib/api` for data fetching
4. Handle cleanup with local `cancelled` flag in effect cleanup

## API Surface

| Module | Prefix | Key endpoints |
|--------|--------|---------------|
| `briefings` | `/api/briefings` | `GET /` list, `GET /{date}` detail |
| `articles` | `/api/briefings/{date}/articles` | `GET /{num}` full article with body |
| `feedback` | `/api/briefings/{date}` | `GET .../feedback`, `POST .../articles/{num}/feedback` |
| `pipeline` | `/api/run` | `POST /` trigger, `GET /status`, `GET /stream` (SSE) |
| `pipeline` | `/api/dlq` | `GET /` list, `GET /stats`, `DELETE /{url}`, `DELETE /` clear |
| `search` | `/api/search` | `GET ?q=` keyword search |
| `stats` | `/api/stats` | `GET /` aggregate statistics |
| `bookmarks` | `/api/bookmarks` | CRUD bookmarks + `GET/POST/DELETE /collections` |
| `config` | `/api/config` | `GET /` read, `PUT /` update, `GET /models` Ollama models |
| `graph` | `/api/graph` | `GET ?max_nodes=200` knowledge graph visualization |
| `obsidian` | `/api/obsidian` | `GET /status`, `POST /export` |
| `sources` | `/api/sources` | `POST /import-opml` |
| `email` | `/api/email` | `POST /test`, `POST /send-briefing/{date}` |
| `health` | `/api/health` | `GET /health` server + Ollama status |
| `ui` | `/api/ui` | `POST /open-reader` (desktop only) |

## Storage

| Table | Key | Purpose |
|-------|-----|---------|
| `articles` | `(briefing_date, article_number)` | Curated articles with scores and summaries |
| `visited_urls` | `url` | Dedup: every URL ever seen |
| `pipeline_runs` | `run_id` | Run history and stats |
| `article_feedback` | `(briefing_date, article_number)` | User read/interest/quality ratings |
| `dead_letter_queue` | `(url, phase)` | Failed articles with retry count |
| `source_run_history` | `source_name` | Last scrape timestamp per source |
| `collections` | `id` | Bookmark collection names |
| `bookmarks` | `(briefing_date, article_number, collection_id)` | Saved articles |

Also: ChromaDB at `data/chromadb/` (vector embeddings), NetworkX graph at `data/knowledge_graph.json`.

## Gotchas

- **Store lifecycle**: `ArticleStore`/`URLStore` need `.open()` + `.close()`. Managed via FastAPI lifespan in `api/app.py`. Forgetting this causes silent failures.
- **Upsert pattern**: SQLite uses `INSERT OR REPLACE`, not `INSERT ON CONFLICT`.
- **Config path resolution**: `config.paths` are resolved relative to `config.yaml` location (not CWD) via `PathsConfig`.
- **Frontend build required**: Backend serves `frontend/dist/` as SPA with catch-all fallback. Must run `npm run build` before desktop/production use.
- **Type sync**: Frontend types in `types/index.ts` must be manually kept in sync with backend `api/schemas.py`. No code generation.
- **Pipeline locking**: Module-level `asyncio.Lock` in `pipeline.py` — only one run at a time. `POST /api/run` returns 409 if already running.
- **Circuit breaker**: Ollama calls trip after consecutive failures, auto-reset after timeout. Configured in `config.yaml` under `ollama`.
- **ChromaDB**: Uses synchronous `.open()` unlike the async SQLite stores.

## Testing

- `pytest` from repo root; `pytest tests/test_foo.py` for one file
- **pytest-asyncio** for async tests (auto mode)
- **respx** for HTTP mocking (Ollama calls, scraper HTTP)
- **TestClient** from FastAPI for synchronous API route testing
- Async fixtures: create stores with `.open()`, yield, then `.close()`
- Use `tmp_path` for temp directories (DB files, config files)
- Test helpers: `_make_summary()`, `_make_novelty()` to build test data

## Configuration

All runtime behavior driven by `config.yaml` (validated by Pydantic in `src/curiopilot/config.py`):
- `interests` — primary/secondary/excluded topics for LLM relevance scoring
- `sources` — scraper configs (validated against `KNOWN_SCRAPERS` set in `config.py`)
- `models` — Ollama model IDs for filter/reader/embedding
- `ollama` — base URL, timeouts, retries, circuit breaker, concurrency
- `scoring` — relevance threshold, novelty/relevance weights (must sum to 1.0)
- `paths` — briefings dir, database dir, graph path, Obsidian vault path

Runtime data in `./data/` (SQLite, ChromaDB, knowledge graph) and `./briefings/` — both gitignored.
