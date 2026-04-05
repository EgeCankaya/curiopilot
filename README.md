# CurioPilot

**Your local AI research assistant.** CurioPilot scrapes the sources you care about, uses local LLMs to filter and summarize articles by relevance to your interests, and presents curated daily briefings in a clean React UI. All data stays on your machine — no cloud APIs, no telemetry.

## How it works

```
Sources (RSS, APIs, scrapers)
        ↓
   Scrape & Deduplicate
        ↓
   Filter by relevance (Ollama 7B)
        ↓
   Deep-read & summarize (Ollama 14B)
        ↓
   Novelty scoring (ChromaDB vectors)
        ↓
   Daily briefing → React UI / Email digest
```

The pipeline is orchestrated as a [LangGraph](https://github.com/langchain-ai/langgraph) state graph with checkpoint/resume, concurrent scraper batches, HTML pre-fetching, and batched vector operations. Failed articles land in a dead-letter queue for inspection.

## Features

- **12 built-in scrapers** — Hacker News, Reddit, Lobsters, GitHub Trending, Arxiv, HuggingFace, Substack, Bluesky, Mastodon, YouTube RSS, Podcasts, and a generic web scraper
- **Two-stage LLM filtering** — fast 7B model for relevance, 14B model for deep reading and summarization
- **Novelty detection** — ChromaDB embeddings surface genuinely new information, not rehashes
- **Knowledge graph** — builds a persistent NetworkX graph of entities and relationships across articles
- **Bookmarks & collections** — save and organize articles you want to revisit
- **Briefing comparison** — compare briefings across dates to spot trends
- **Obsidian export** — push articles into your Obsidian vault
- **Email digest** — receive daily briefings via SMTP email
- **Desktop app** — native window via PyWebView with embedded server
- **Keyboard-driven UI** — full keyboard navigation with shortcuts modal
- **Dark mode** — CSS variable theming with light/dark toggle
- **Fully local** — SQLite + ChromaDB + JSON files, no external services beyond Ollama

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the frontend)
- **[Ollama](https://ollama.com/)** running locally with your chosen models pulled (e.g. `ollama pull gemma3:4b` and `ollama pull gemma3:12b`)
- **[uv](https://docs.astral.sh/uv/)** (recommended) or pip

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/EgeCankaya/curiopilot.git
cd curiopilot
uv sync

# 2. Install frontend dependencies and build
cd frontend && npm install && npm run build && cd ..

# 3. Edit config.yaml with your interests and sources
#    (see Configuration section below)

# 4. Run the discovery pipeline
curiopilot run

# 5. Launch the UI
curiopilot app          # Desktop app (PyWebView)
# or
curiopilot serve        # Headless API server on port 19231
cd frontend && npm run dev  # Dev server on port 5173
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `curiopilot run` | Run the full discovery pipeline |
| `curiopilot run --dry-run` | Pipeline dry run (no writes) |
| `curiopilot serve` | Start the API server (port 19231) |
| `curiopilot app` | Launch desktop app |
| `curiopilot query "topic"` | Query the knowledge base |

## Configuration

All behavior is driven by `config.yaml`:

```yaml
interests:
  primary:
    - AI agents
    - LangGraph
    - multi-agent systems
  secondary:
    - local LLMs
    - RAG
    - prompt engineering
  excluded:
    - cryptocurrency

sources:
  - name: Hacker News
    scraper: hackernews_api
    max_articles: 30
  - name: r/LocalLLaMA
    scraper: reddit_json
    subreddit: LocalLLaMA
    max_articles: 20
  # ... add as many as you like

models:
  filter: gemma3:4b
  reader: gemma3:12b
  embedding: nomic-embed-text

scoring:
  relevance_threshold: 5
  novelty_weight: 0.6
  relevance_weight: 0.4
```

See `config.yaml` for the full set of options including Ollama timeouts, circuit breaker settings, concurrency limits, email configuration, and path overrides.

## Architecture

```
frontend/src/          React 19 + TypeScript + Tailwind CSS v4
       ↕               HTTP/JSON
src/curiopilot/api/    FastAPI server
       ↕               reads/writes
data/                  SQLite + ChromaDB + JSON
```

| Directory | Purpose |
|-----------|---------|
| `src/curiopilot/api/` | FastAPI app, route modules, schemas |
| `src/curiopilot/pipeline/` | LangGraph orchestration |
| `src/curiopilot/scrapers/` | 12 source scrapers (registry pattern) |
| `src/curiopilot/agents/` | LLM filter, reader, novelty, query, briefing agents |
| `src/curiopilot/storage/` | SQLite stores, knowledge graph, taxonomy |
| `src/curiopilot/llm/` | Ollama client + circuit breaker |
| `src/curiopilot/export/` | Obsidian vault export |
| `frontend/src/` | React SPA |

## Development

```bash
# Backend
uv sync
curiopilot serve

# Frontend (separate terminal)
cd frontend
npm install
npm run dev      # Vite dev server with API proxy

# Tests
pytest
pytest tests/test_scrapers.py  # Single file
```

## License

MIT
