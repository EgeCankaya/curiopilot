# CurioPilot — Improvement Ideas

A collection of ideas to improve CurioPilot across performance, UX, intelligence, integrations, and infrastructure.

---

## 1. Pipeline & Performance ^^LIKE^^

### Parallel Article Processing

The filter and reader agents currently process articles sequentially. Using `asyncio.Semaphore` with 3-5 concurrent workers could cut pipeline runtime by 60-70% for typical 30-article batches.

### Pipeline Checkpointing & Resume

If the pipeline crashes mid-run (e.g., Ollama goes down during the read phase), the entire batch is lost. Adding persistent state snapshots after each phase would allow resuming from the last successful checkpoint instead of restarting from scratch.

### Circuit Breaker for Ollama

When Ollama is unresponsive, the pipeline waits the full 120s timeout on every single article. A circuit breaker pattern (fail fast after N consecutive timeouts) would save minutes of wasted waiting and surface the problem immediately.

### Incremental Runs

Support a "run since last briefing" mode that only processes sources updated since the last successful run, rather than re-scraping everything. Useful for running the pipeline multiple times per day.

### Dead Letter Queue

Articles that fail during fetch or summarization are silently dropped. A dead letter queue would store failed articles for manual review or automatic retry on the next run.

### Per-Article Timeouts

Add individual article timeouts (e.g., 30s for fetch, 60s for summarization) so one stalled article doesn't block the entire pipeline.

---

## 2. Frontend & UX ^^LIKE^^

### Search UI

The backend already has a `GET /api/search?q=...` endpoint, but there's no search bar in the UI. Adding a search input in the header with instant results would let users find articles across all briefings by keyword or concept.

### Settings Page

Currently all configuration lives in `config.yaml` with no UI. A settings page could expose:

- Interest management (add/remove/reorder primary/secondary/excluded topics)
- Source management (enable/disable sources, adjust max articles)
- Scoring thresholds (relevance cutoff, novelty weight sliders)
- Model selection (pick from available Ollama models)

### Knowledge Graph Visualization

An interactive force-directed graph (using D3.js or vis.js) showing concepts as nodes and relationships as edges. Color-code by familiarity, size by encounter count, and let users click nodes to see related articles. This would make the "suggested explorations" feature much more engaging.

### Stats Dashboard

The `/api/stats` endpoint returns useful data (URLs visited, graph size, most connected topic) that isn't shown anywhere. A dashboard page could display:

- Articles read over time (line chart)
- Top sources by article count
- Concept growth timeline
- Novelty score distribution
- Reading streak / engagement metrics

### Keyboard Navigation

Add keyboard shortcuts for power users:

- `j`/`k` to navigate articles
- `Enter` to open article
- `1`-`5` for interest rating
- `r` to toggle read status
- `w`/`a` to switch between web/analysis views
- `Shift+R` to trigger a pipeline run

### Mobile Responsive Layout

The sidebar is fixed at 300px and the layout assumes desktop. A responsive design with a collapsible sidebar, bottom navigation on mobile, and touch-friendly controls would make CurioPilot usable on tablets and phones.

### Dark/Light Mode Toggle

The UI is forced dark theme. Some users prefer light mode, especially during daytime reading. A theme toggle with system preference detection would improve accessibility.

### Article Bookmarks & Collections

Let users star/bookmark articles and organize them into custom collections (e.g., "Read Later", "Share with Team", "Research: Transformers"). This goes beyond the current read/interest/quality feedback.

### Briefing Comparison View

A side-by-side view comparing two briefings (e.g., today vs. last week) to see how topics evolved, what's new, and what dropped off.

### Reading Progress Indicator

Track how far through each briefing the user has gotten (e.g., "3 of 8 articles read") with a progress bar on the briefing list item.

---

## 3. Knowledge & Intelligence  ^^ LIKE^^

### Concept Disambiguation & Merging

The knowledge graph has no way to merge equivalent concepts (e.g., "ML" and "Machine Learning", "LLM" and "Large Language Model"). An automatic alias/merge system — plus a UI for manual correction — would prevent graph fragmentation and improve novelty scoring.

### Preference Learning from Feedback

User feedback (interest ratings, quality flags) is currently used to adjust graph familiarity, but it could train a lightweight preference model. Over time, the filter agent could learn that the user consistently rates "systems programming" articles 5/5 and "cryptocurrency" articles 1/5, automatically adjusting relevance scoring.

### Cross-Briefing Trend Analysis

Analyze patterns across multiple briefings to surface:

- Trending topics (concepts appearing with increasing frequency)
- Fading topics (concepts that peaked and declined)
- Knowledge gaps (high-interest areas with few articles)
- Seasonal patterns

### Topic Deep-Dive Mode

Let users select a concept from the knowledge graph and trigger a focused pipeline run that specifically searches for articles about that topic, going deeper than the daily breadth-first approach.

### Article Relationship Maps

Show how articles within a briefing relate to each other — shared concepts, contrasting viewpoints, progressive depth. Help users build a coherent mental model rather than reading isolated summaries.

### Spaced Repetition Integration

Extend the knowledge graph's memory decay into a proper spaced repetition system. Surface concepts that are about to be "forgotten" (familiarity approaching zero) and recommend revisiting related articles.

### Quality-Weighted Source Ranking

Track which sources consistently produce high-quality, high-interest articles (based on user feedback) and weight them higher in future pipeline runs. Sources that regularly produce "broken" or "dislike" articles could be flagged or auto-demoted.

---

## 4. New Sources & Integrations ^^LIKE^^

### Additional Scrapers

- **Substack** — Scrape specific Substack newsletters by URL
- **Medium** — Top articles from specific tags or publications
- **YouTube** — Transcripts from educational/tech channels (via yt-dlp + whisper)
- **Bluesky/Mastodon** — Trending posts from followed accounts or hashtags
- **GitHub Trending** — Trending repositories and their READMEs
- **Twitter/X Lists** — Articles shared in curated Twitter lists
- **Lobste.rs** — Community-driven tech news (similar to HN)
- **Podcast RSS** — Transcribe and summarize podcast episodes

### OPML Import

Let users import their existing RSS feed collections via OPML files, automatically creating `generic_scrape` source entries for each feed.

### Newsletter Ingestion

Forward newsletters to a local email parser that extracts article links and feeds them into the pipeline. Many high-quality articles are only shared via newsletters.

### Readwise / Pocket / Instapaper Sync

Two-way sync with read-later services: import saved articles for processing, export curated briefings back.

### Calendar Integration

Automatically schedule briefing reviews on the user's calendar. Flag articles that are time-sensitive (e.g., conference deadlines, release dates).

---

## 5. Data & Export ^^LIKE^^

### Export Formats

- **PDF** — Formatted briefing with article summaries, suitable for printing or sharing
- **Email Digest** — Send daily briefing to a configured email address
- **Markdown** — Already exists as files, but add a "copy to clipboard" button in the UI
- **JSON/CSV** — Machine-readable export of articles, scores, and concepts for external analysis
- **EPUB** — For reading briefings on e-readers

### Annotation System

Let users highlight text in articles and add personal notes. Store annotations alongside feedback and surface them when related concepts appear in future articles.

### Briefing Archive & Search

Full-text search across all historical briefings, not just the current one. Filter by date range, source, topic, or score threshold.

### Data Portability

One-click export/import of the entire knowledge base (SQLite + ChromaDB + knowledge graph + config) for backup, migration, or sharing between machines.

---

## 6. Infrastructure & Reliability ^^LIKE^^

### Scheduled Runs

Built-in cron-like scheduling so the pipeline runs automatically at a configured time (e.g., 6 AM daily). Currently requires an external scheduler.

### Pagination

The briefing list API returns all dates at once. For users running daily for a year, that's 365+ rows. Add cursor-based pagination to the API and infinite scroll to the UI.

### Embedding Versioning

Changing the embedding model in config breaks similarity comparisons with old vectors. Track which model produced each embedding and re-embed on model change (or maintain separate collections).

### Database Migrations

A formal migration system (like Alembic) for SQLite schema changes, rather than the current ad-hoc migration helpers. Important as the schema evolves.

### Backup & Restore

Automated periodic backup of `data/` (SQLite, ChromaDB, knowledge graph) with one-click restore. Data loss from a corrupted graph file would erase the entire learning history.

### Health Check Endpoint

A `GET /api/health` endpoint that verifies Ollama connectivity, database access, and disk space before starting a pipeline run. Surface issues early instead of failing mid-pipeline.

### Run History & Logs

Store and expose pipeline run history with per-phase timing, article counts, and error details. Currently runs are fire-and-forget with no queryable history in the UI.

### Concurrent Run Safety

The current `_run_lock` prevents parallel runs, but the global `_run_state` dict isn't thread-safe. Either make state management robust or add proper queueing for back-to-back runs.

---

## 7. LLM & Agents 

### Prompt Versioning

Store prompt templates as versioned files rather than hardcoded strings. Enable A/B testing different prompts and tracking which version produces better relevance scores.

### Fallback Model Chain

If the primary Ollama model is unavailable (not downloaded, OOM), fall back to a smaller model rather than failing. E.g., 14B → 7B → 3B for the reader agent.

### Batch LLM Calls

Some Ollama models support batched inference. Sending multiple articles in a single prompt (where context window allows) could reduce per-article overhead.

### Token Usage Tracking

Count and log tokens consumed per pipeline run, per agent, and per article. Useful for understanding cost if switching to cloud LLMs, and for optimizing prompt length.

### Configurable System Prompts

Let users customize the filter and reader agent system prompts from the config or settings UI. Power users may want to adjust how strictly the filter scores, or what the reader focuses on in summaries.

### Multi-Model Pipeline

Use different models for different article types — a code-focused model for GitHub/ArXiv papers, a general model for news, a long-context model for lengthy reports.

### Fact-Checking Layer

Cross-reference LLM-generated summaries against the original article text to flag potential hallucinations or inaccuracies before presenting to the user.

### Cloud LLM Option

For users without local GPU, support cloud API backends (OpenAI, Anthropic, Groq) as an alternative to Ollama. Config-driven provider selection with API key management.

---

## 8. Desktop App & Distribution ^^LIKE^^

### System Tray Mode

Minimize to system tray instead of closing. Show a notification badge when a new briefing is ready. Right-click menu for quick actions (run pipeline, open app, quit).

### Desktop Notifications

OS-native notifications when:

- Pipeline completes ("Your daily briefing is ready — 8 new articles")
- A high-novelty article is discovered mid-run
- Pipeline errors occur

### Installer & Auto-Update

Package as a proper Windows installer (NSIS/WiX) and macOS .dmg with auto-update capability. Currently requires Python/Node.js setup.

### Multi-Window Article Tabs

Instead of reusing a single reader window, support tabbed or multiple reader windows so users can have several articles open simultaneously.

### Offline Mode

Cache fetched articles locally so the UI works even when the internet is down. Show cached content with a "stale" indicator.

### Startup on Boot

Optional setting to launch CurioPilot on system startup, run the pipeline, and have the briefing ready by the time the user sits down.

---

## 9. Community & Collaboration

### Shared Briefings

Generate a shareable link or file for a briefing that others can view (without needing CurioPilot installed). Useful for teams that want to share curated reading lists.

### Interest Profile Sharing

Export/import interest profiles so teams can share their topic configurations. A "Data Engineering" profile, a "Frontend Dev" profile, etc.

### Collaborative Knowledge Graph

Multiple users contribute to a shared knowledge graph, pooling their reading and feedback. Concepts marked as "well-understood" by the team get deprioritized for everyone.

### Public Scraper Registry

A community repository of scraper configurations for niche sources (specific blogs, journals, forums). Users can browse and install new sources without writing code.

---

## 10. Analytics & Self-Improvement ^^LIKE^^

### Reading Habit Insights

- Average articles read per briefing
- Most-read vs. least-read sources
- Interest rating distribution over time
- Time-of-day reading patterns
- Concept familiarity growth over weeks/months

### Pipeline Performance Metrics

- Average runtime per phase
- Article drop-off funnel (scraped → deduped → filtered → read → briefed)
- Source reliability scores (% of articles successfully fetched)
- LLM response quality tracking (parse failures, retries)

### A/B Testing Framework

Run two pipeline configurations side-by-side and compare outputs. Useful for tuning scoring weights, trying different models, or testing new scraper configurations.

### Feedback Loop Effectiveness

Measure whether user feedback actually improves future briefings. Track if high-rated topics appear more often and low-rated topics less often over time.