# CurioPilot — Product Requirements Document

## 1. Overview

### 1.1 Product Name
**CurioPilot** — Autonomous Knowledge Discovery Agent

### 1.2 Elevator Pitch
A locally‑run AI agent that autonomously browses the web daily, discovers articles relevant to your interests, reads and summarizes them, and maintains a persistent knowledge graph so it never surfaces redundant content. It produces a ranked daily briefing of genuinely novel knowledge, and over time becomes an increasingly personalized research companion that understands what you know and what you do not.

### 1.3 Problem Statement
Staying current in fast‑moving fields like AI requires daily reading across dozens of sources (Hacker News, ArXiv, Reddit, blogs, Hugging Face). The current experience is:

- Manual and time‑consuming: scrolling through feeds, opening tabs, skimming articles
- Redundant: reading yet another “intro to LangGraph” article when you already know the topic well
- Unstructured: no way to query “what have I learned about X over the past month?”
- No gap detection: no system identifies what you have not explored yet

### 1.4 Solution
An agent pipeline that automates the full cycle: **discover → filter → read → summarize → deduplicate → rank → brief → remember**. The key innovation is the novelty scoring engine backed by a persistent knowledge graph that makes the system smarter with every run.

### 1.5 Constraints

| Constraint | Requirement |
| --- | --- |
| Cost | Zero. No paid APIs, no subscriptions. All open‑source. |
| Hardware | Must run on a single GPU with 16 GB VRAM (RTX 4070 Ti Super). |
| Privacy | Fully local inference. No data sent to cloud LLM providers. |
| Runtime | Full pipeline should complete in under 30 minutes for a typical daily run (~50–100 new articles filtered down to ~5–15 briefing items). |

---

## 2. User Personas

### 2.1 Primary Persona
**Self** — A computer engineering graduate actively learning AI agent development. Wants to stay current on AI agents, LLMs, frameworks, and research without spending 2+ hours daily reading feeds manually. Values depth over breadth and wants a system that adapts to growing expertise.

### 2.2 Secondary Persona (future)
Any technical professional who wants a private, self‑hosted alternative to algorithmic news feeds for staying current in their domain.

---

## 3. User Stories

| ID | Story | Priority |
| --- | --- | --- |
| US‑01 | As a user, I want to define my topics of interest in a simple config file so the agent knows what to look for. | Must Have |
| US‑02 | As a user, I want the agent to crawl my configured sources and find new articles I have not seen before. | Must Have |
| US‑03 | As a user, I want each article filtered for relevance to my interests before the agent spends time reading it. | Must Have |
| US‑04 | As a user, I want the agent to read relevant articles and produce structured summaries with key concepts extracted. | Must Have |
| US‑05 | As a user, I want the agent to score each article’s novelty against what I have already read, so I do not see redundant content. | Must Have |
| US‑06 | As a user, I want a daily briefing document (Markdown) that ranks articles by novelty and relevance. | Must Have |
| US‑07 | As a user, I want the agent to remember every article it has processed so it never re‑visits the same URL. | Must Have |
| US‑08 | As a user, I want to see how my knowledge graph has grown after each run (new concepts, new connections). | Should Have |
| US‑09 | As a user, I want the agent to suggest knowledge gaps — topics adjacent to what I know but have not explored. | Should Have |
| US‑10 | As a user, I want to query my accumulated knowledge (e.g., “What have I learned about MCP?”) and get a synthesized answer. | Should Have |
| US‑11 | As a user, I want to run the agent manually via CLI or schedule it to run automatically. | Must Have |
| US‑12 | As a user, I want to add or remove sources without modifying code. | Must Have |
| US‑13 | As a user, I want to see a terminal progress indicator while the pipeline runs. | Should Have |
| US‑14 | As a user, I want to view past briefings in an organized archive. | Should Have |
| US‑15 | As a user, I want an interactive mode where I can say “tell me more about article 3” and the agent deep‑dives. | Nice to Have |
| US‑16 | As a user, I want to export my knowledge graph to Obsidian‑compatible Markdown with backlinks. | Nice to Have |

---

## 4. Functional Requirements

### 4.1 Configuration System

**FR‑01**: The system shall read user configuration from a `config.yaml` file at the project root.

**FR‑02**: The configuration shall support at least the following top‑level keys:

```yaml
# config.yaml
interests:
  primary:
    - "AI agents"
    - "LangGraph"
    - "multi-agent systems"
    - "function calling"
    - "MCP (Model Context Protocol)"
  secondary:
    - "quantized LLMs"
    - "local inference"
    - "prompt engineering"
  excluded:
    - "cryptocurrency"
    - "web3"

sources:
  - name: "Hacker News"
    scraper: "hackernews_api"          # uses official Firebase API
    max_articles: 30
    request_delay_seconds: 2

  - name: "Reddit r/LocalLLaMA"
    scraper: "reddit_json"             # JSON listing / API-based
    url: "https://www.reddit.com/r/LocalLLaMA/top/?t=day"
    max_articles: 20
    request_delay_seconds: 3

  - name: "Hugging Face Daily Papers"
    scraper: "huggingface_scrape"      # Playwright DOM scraping
    url: "https://huggingface.co/papers"
    max_articles: 15
    request_delay_seconds: 3

  - name: "ArXiv cs.AI"
    scraper: "arxiv_feed"              # Atom feed/API-based
    query: "cat:cs.AI"
    max_articles: 20
    request_delay_seconds: 2

models:
  filter_model: "qwen2.5:7b-instruct-q8_0"
  reader_model: "qwen2.5:14b-instruct-q4_K_M"
  embedding_model: "nomic-embed-text"

ollama:
  base_url: "http://localhost:11434"
  timeout_seconds: 120
  max_retries: 3

scoring:
  relevance_threshold: 6              # 0–10, articles below this are skipped
  novelty_weight: 0.6                 # weight for novelty in final ranking
  relevance_weight: 0.4               # weight for relevance in final ranking
  max_briefing_items: 15              # max articles in daily briefing
  near_duplicate_threshold: 0.92      # cosine similarity
  related_threshold: 0.75             # cosine similarity
  vector_novelty_weight: 0.5          # weight inside novelty
  graph_novelty_weight: 0.5           # weight inside novelty

chunking:
  max_tokens_per_chunk: 28000         # configurable, below model context

paths:
  briefings_dir: "./briefings"
  database_dir: "./data"
  graph_path: "./data/knowledge_graph.json"
```

**FR‑03**: The system shall validate the config at startup and report clear errors for missing or malformed fields, including invalid scraper names, model identifiers, or path values.

### 4.2 Source Discovery & Crawling Pipeline

**FR‑04**: The system shall support multiple source access modes via dedicated scraper modules:

- API‑based sources (e.g., Hacker News Firebase API)
- Feed‑based sources (e.g., ArXiv Atom feeds)
- HTML scraping using Playwright (e.g., Hugging Face Papers, generic sites)

**FR‑05**: For each configured source, the system shall obtain a list of article entries containing at minimum: `title`, `url`, and optionally `snippet` (preview text) and `score` / `upvotes` (if available on the source).

**FR‑06**: Each source type shall have a dedicated scraper module implementing a common interface:

```python
class BaseScraper(ABC):
    @abstractmethod
    async def extract_articles(self) -> list[ArticleEntry]:
        """Extract article entries from this source."""
        ...
```

**FR‑07**: Source scraper implementations shall include at least:

- `HackerNewsApiScraper` — uses the official Firebase API
- `RedditJsonScraper` — uses JSON listings / lightweight API
- `ArxivFeedScraper` — uses Atom / RSS feeds
- `HuggingFaceScraper` — uses Playwright to scrape `huggingface.co/papers`
- `GenericScrapeScraper` — generic HTML scraper for simple pages

**FR‑08**: For each configured source, the system shall enforce a configurable politeness delay (`request_delay_seconds`) between network requests (API calls, feed fetches, or page loads).

**FR‑09**: The system shall deduplicate extracted URLs against the SQLite `visited_urls` table before proceeding. Only unseen URLs pass to the relevance filtering phase.

**FR‑10**: The system shall handle source‑level failures gracefully (timeouts, blocked pages, changed layouts, non‑200 responses) by logging the error and continuing to the next source without crashing the pipeline.

### 4.3 Relevance Filtering

**FR‑11**: The system shall send each new article’s `title + snippet` (or `title` alone if no snippet is available) to the filter model with a structured prompt asking: “Given the user’s interests [list], rate this article’s relevance from 0–10 and provide a one‑sentence justification.”

**FR‑12**: The model response shall be parsed into a Pydantic model:

```python
class RelevanceScore(BaseModel):
    score: int = Field(ge=0, le=10)
    justification: str
```

**FR‑13**: Articles scoring below `relevance_threshold` (configurable, default 6) shall be discarded. Their URLs are still logged in SQLite to avoid re‑processing in future runs.

**FR‑14**: The relevance filter shall use the lighter model (7B) for speed.

**FR‑15**: For correctness and VRAM safety, relevance scoring requests shall be executed sequentially (one article per Ollama request, concurrency = 1). Ollama may internally batch or queue requests, but the application will not send concurrent filter requests.

**FR‑16**: The system shall include retry and timeout handling for Ollama calls using the config values `ollama.timeout_seconds` and `ollama.max_retries`. On repeated failure, the article shall be skipped with a logged warning.

### 4.4 Deep Reading & Summarization

**FR‑17**: For each article that passes relevance filtering, the system shall navigate to the full article URL. For HTML pages, it shall use Playwright (headless Chromium) to render and extract content; for API / feed‑hosted content, it may use direct HTTP where appropriate.

**FR‑18**: The system shall extract the article’s main body text, stripping navigation, ads, sidebars, and boilerplate, using a combination of Playwright DOM inspection, Readability‑style heuristics (largest content block detection), and per‑source selectors where configured.

**FR‑19**: If the extracted text exceeds the configured `chunking.max_tokens_per_chunk` threshold (based on an approximate tokenization for the reader model), the system shall chunk the text and summarize in a map‑reduce pattern (summarize chunks, then summarize the summaries).

**FR‑20**: The reader model (14B) shall produce a structured summary:

```python
class ArticleSummary(BaseModel):
    title: str
    source_name: str
    url: str
    date_processed: datetime
    key_concepts: list[str]           # 3–8 extracted concepts/topics
    summary: str                      # 3–5 sentence summary
    novel_insights: str               # what is genuinely new/interesting
    technical_depth: int              # 1–5 scale
    related_topics: list[str]         # connections to broader field
```

**FR‑21**: Structured output shall be enforced via Pydantic parsing with retry logic (up to 2 retries on malformed JSON or schema mismatches).

**FR‑22**: The system shall ensure that the 7B filter model is not occupying VRAM when the 14B reader model is loaded by explicitly controlling Ollama model lifecycle (see Section 6.2).

### 4.5 Novelty Scoring Engine

**FR‑23**: The system shall compute a **novelty score** (0.0–1.0) for each article summary by combining two signals: vector similarity‑based semantic novelty and graph‑based structural novelty.

**Signal 1 — Vector Similarity (Semantic Novelty)**:

- Embed the article’s `key_concepts + summary` using the configured embedding model via the Ollama `/api/embeddings` endpoint.
- Query ChromaDB for the top‑k most similar past article embeddings (default k = 5).
- Let `s_max` be the maximum similarity among retrieved neighbors.
  - If `s_max > near_duplicate_threshold` (default 0.92) → near‑duplicate, `vector_novelty ≈ 0.1`.
  - If `related_threshold ≤ s_max ≤ near_duplicate_threshold` (default 0.75–0.92) → related, `vector_novelty` in [0.3–0.6].
  - If `s_max < related_threshold` → genuinely novel, `vector_novelty` in [0.8–1.0].

**Signal 2 — Graph Novelty (Structural Novelty)**:

- Check how many of the article’s `key_concepts` already exist as nodes in the knowledge graph.
- Compute `graph_novelty = 1.0 - (known_concepts / total_concepts)` (with `total_concepts ≥ 1`).
- If the article introduces concepts that bridge two previously disconnected graph clusters (e.g., as detected by community membership or path length changes), apply a 1.3× bonus to `graph_novelty`, capped at 1.0.

**FR‑24**: Final novelty score shall be computed as:

```text
novelty = (vector_novelty * vector_novelty_weight) +
          (graph_novelty * graph_novelty_weight)
```

using the weights from `config.yaml` (`vector_novelty_weight` and `graph_novelty_weight`, default 0.5 each).

**FR‑25**: Final ranking score shall be computed as:

```text
final_score =
    (novelty * novelty_weight) +
    (relevance * relevance_weight / 10.0)
```

using the configuration values `novelty_weight` and `relevance_weight`.

### 4.6 Knowledge Graph Management

**FR‑26**: The knowledge graph shall be implemented using NetworkX with JSON serialization for persistence at the path configured under `paths.graph_path`.

**FR‑27**: Graph structure:

- **Nodes**: Concepts / topics (e.g., “LangGraph”, “state machines”, “MCP servers”)
  - Attributes: `first_seen: datetime`, `last_seen: datetime`, `encounter_count: int`, `familiarity: float (0–1)`
- **Edges**: Relationships between concepts (e.g., “LangGraph” —uses→ “state machines”)
  - Attributes: `relationship_type: str`, `first_seen: datetime`, `source_articles: list[str]`

**FR‑28**: After each pipeline run, the system shall update the graph:

- Add new concept nodes from article `key_concepts`.
- Increment `encounter_count` and update `last_seen` for existing concepts.
- Add edges between co‑occurring concepts (concepts appearing in the same article are connected).
- Update `familiarity` score, e.g., `familiarity = min(1.0, encounter_count * 0.1 + recency_bonus)`.

**FR‑29**: The system shall implement a **knowledge gap detector**:

- Identify nodes with high connectivity to known topics but low `familiarity` scores.
- Identify “bridge” concepts that connect separate clusters but have low encounter counts.
- Report these as “Suggested Explorations” in the daily briefing.

**FR‑30**: If NetworkX + JSON serialization becomes a performance bottleneck at higher node counts (e.g., > 10,000 nodes), the implementation may be migrated to an SQLite‑backed or other persistent store while preserving the public behavior described here.

### 4.7 Daily Briefing Generation

**FR‑31**: The system shall generate a Markdown briefing file saved to `{briefings_dir}/{YYYY-MM-DD}.md`.

**FR‑32**: Briefing format (steady‑state, after memory & novelty phases are implemented):

```markdown
# CurioPilot Daily Briefing -- {date}

**Articles Scanned**: {total} | **Passed Relevance**: {filtered} | **In Briefing**: {final}
**Pipeline Runtime**: {duration}

---

## New Concepts
> Topics appearing for the first time in your knowledge graph.

- **{concept}**: First encountered in "{article_title}"
- ...

## Top Articles

### 1. {title}
**Source**: {source} | **Relevance**: {score}/10 | **Novelty**: {novelty_pct}%
**Why it is new to you**: {explanation referencing knowledge graph state}

{summary}

**Key Concepts**: `concept1`, `concept2`, `concept3`

---

### 2. {title}
...

## Deepening
> Articles on topics you know, but with a new angle.

### {title}
**What you already know**: {existing knowledge summary from graph}
**What is new here**: {novel_insights from summary}

---

## Knowledge Graph Update
- **Nodes added**: {count} ({list})
- **Edges added**: {count}
- **Total knowledge nodes**: {total}
- **Most connected topic**: {topic} ({edge_count} connections)

## Suggested Explorations
> Topics adjacent to your knowledge that you have not explored yet.

1. **{topic}** -- Connected to {known_topic_1} and {known_topic_2}, but you have zero articles on it.
2. ...
```

**FR‑33**: During **Phase 2** (before the memory and novelty engine is implemented), the briefing may omit the “New Concepts”, “Deepening”, “Knowledge Graph Update”, and “Suggested Explorations” sections and instead focus solely on ranked articles and their summaries.

**FR‑34**: The system shall also print a concise terminal summary (top 5 articles with one‑line summaries) for quick scanning without opening the file.

### 4.8 Knowledge Query System

**FR‑35**: The system shall support a `query` CLI command:

```bash
curiopilot query "What have I learned about MCP?"
```

**FR‑36**: The query system shall:

1. Embed the query and retrieve the top‑10 most relevant past article summaries from ChromaDB.
2. Retrieve related nodes and their connections from the knowledge graph.
3. Pass both to the reader model with a synthesis prompt.
4. Return a structured knowledge snapshot with source article references.

### 4.9 URL and History Management

**FR‑37**: The system shall use an SQLite database (`data/curiopilot.db`) with at least the following tables:

```sql
CREATE TABLE visited_urls (
    url TEXT PRIMARY KEY,
    title TEXT,
    source_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    passed_relevance BOOLEAN,
    relevance_score INTEGER
);

CREATE TABLE pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    articles_scanned INTEGER,
    articles_relevant INTEGER,
    articles_briefed INTEGER,
    new_concepts_added INTEGER
);
```

**FR‑38**: URL entries shall be created for all discovered articles, including those that fail relevance filtering, to avoid re‑processing the same URLs in future runs.

### 4.10 LLM and Ollama Integration

**FR‑39**: The system shall communicate with Ollama via its HTTP API (`/api/generate` for text, `/api/embeddings` for embeddings) at the configured `ollama.base_url`.

**FR‑40**: For the relevance filtering phase, the system shall use the configured 7B model; for deep reading, it shall use the configured 14B model. Only one large model shall occupy GPU VRAM at a time.

**FR‑41**: Before switching from the 7B filter model to the 14B reader model, the system shall explicitly instruct Ollama to unload or allow the 7B model to expire (e.g., by using `keep_alive=0` on the last 7B request or an equivalent mechanism), to avoid VRAM exhaustion on the target GPU.

**FR‑42**: The system shall implement configurable retry and timeout behavior for all Ollama requests using `ollama.timeout_seconds` and `ollama.max_retries`.

---

## 5. Non‑Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR‑01 | Full pipeline runtime | < 30 minutes for a typical daily run |
| NFR‑02 | Startup time | < 10 seconds (config load + DB connect) |
| NFR‑03 | Peak VRAM usage | < 12 GB (single large model loaded at any time) |
| NFR‑04 | Failure resilience | Single article or source failure must not crash the pipeline |
| NFR‑05 | Data durability | All state (SQLite, ChromaDB, graph JSON) persists across runs and process restarts |
| NFR‑06 | Extensibility | Adding a new source requires only adding a scraper class and a config entry |
| NFR‑07 | Logging | Structured logging (Python `logging`) with configurable verbosity |

---

## 6. Technical Architecture

### 6.1 Tech Stack

CurioPilot is a Python 3.11 project managed with `uv` (see `pyproject.toml`).

| Component | Technology | Purpose |
| --- | --- | --- |
| Agent / Orchestration Framework | LangGraph | Pipeline orchestration with conditional edges and state management (also used as a learning exercise for LangGraph) |
| Browser Automation | Playwright (async) | Web scraping, article reading, DOM extraction |
| LLM Inference | Ollama | Local model serving and model swapping (7B filter, 14B reader) |
| Structured Output | Pydantic | Enforce response schemas for relevance scores and article summaries |
| Vector Store | ChromaDB | Semantic search over past articles |
| Knowledge Graph | NetworkX | Topic graph with JSON persistence (with future option for SQLite‑backed storage) |
| Relational DB | SQLite (aiosqlite) | URL history, run metadata |
| Embeddings | `nomic-embed-text` via Ollama `/api/embeddings` | Article embedding for novelty detection |
| CLI | Typer | Command‑line interface |
| Progress Display | Rich | Terminal progress bars and formatted output |

**Note**: Although the pipeline could be implemented as a plain async function sequence, LangGraph is intentionally chosen to gain experience with graph‑based agent orchestration and to leave room for future conditional branches and more complex flows.

### 6.2 Models

| Role | Model | Quantization | Approx. VRAM | Loaded When |
| --- | --- | --- | --- | --- |
| Relevance Filter | Qwen 2.5‑7B‑Instruct | Q8_0 GGUF | ~8 GB | Phase 1b / Phase 2 (filter phase) |
| Deep Reader / Briefing | Qwen 2.5‑14B‑Instruct | Q4_K_M GGUF | ~9 GB | Phase 2–3 (deep reading and briefing phases) |
| Embeddings | `nomic-embed-text` | Default | ~300 MB | Used throughout; small footprint |

Ollama handles model loading, but CurioPilot is responsible for ensuring only one large model is active in VRAM at a time (e.g., using per‑request `keep_alive` and explicit unload where necessary).

### 6.3 LangGraph Pipeline Design

Conceptual pipeline (logical steps, independent of exact LangGraph API):

```text
                    [START]
                       │
                 ┌─────▼──────┐
                 │ Load Config │
                 └─────┬──────┘
                       │
                 ┌─────▼──────┐
                 │ Crawl       │──→ for each source (sequential)
                 │ Sources     │      │
                 └─────┬──────┘      ├─ fetch via API / feed / scrape
                       │              ├─ extract articles
                       │              └─ deduplicate vs SQLite
                       │
                 ┌─────▼──────┐
                 │ Filter      │──→ for each article (sequential)
                 │ Relevance   │      │
                 │ (7B model)  │      └─ score + threshold gate
                 └─────┬──────┘
                       │
                 ┌─────▼──────┐
          ┌──────│ Swap Model  │  (Ensure 7B unloaded, load 14B)
          │      └─────┬──────┘
          │            │
          │      ┌─────▼──────┐
          │      │ Deep Read   │──→ for each relevant article
          │      │ (14B model) │      │
          │      └─────┬──────┘      ├─ navigate to article
          │            │              ├─ extract body text
          │            │              ├─ chunk if needed
          │            │              └─ generate ArticleSummary
          │            │
          │      ┌─────▼──────┐
          │      │ Score       │──→ for each summary
          │      │ Novelty     │      │
          │      └─────┬──────┘      ├─ vector similarity (ChromaDB)
          │            │              └─ graph novelty (NetworkX)
          │            │
          │      ┌─────▼──────┐
          │      │ Rank &      │
          │      │ Generate    │──→ compile briefing Markdown
          │      │ Briefing    │
          │      └─────┬──────┘
          │            │
          │      ┌─────▼──────┐
          │      │ Update      │──→ write to ChromaDB
          │      │ Memory      │──→ update knowledge graph
          │      └─────┬──────┘    ──→ log URLs in SQLite
          │            │
          │      ┌─────▼──────┐
          └──────│ Print       │──→ terminal summary
                 │ Summary     │
                 └─────┬──────┘
                       │
                     [END]
```

---

## 7. CLI Interface

The CLI is implemented using Typer and exposed as the `curiopilot` command.

```bash
# Run the full daily pipeline
curiopilot run

# Run with verbose logging
curiopilot run --verbose

# Run in dry-run mode: crawl + filter only, no deep reading or memory updates
curiopilot run --dry-run

# Run only for specific sources
curiopilot run --source "Hacker News" --source "ArXiv cs.AI"

# Query your accumulated knowledge
curiopilot query "What do I know about LangGraph?"

# View knowledge graph stats
curiopilot stats

# List past briefings
curiopilot history

# View a specific past briefing
curiopilot history --date 2026-03-04

# Reset all memory (destructive, requires confirmation)
curiopilot reset --confirm
```

`curiopilot add-source` is considered a stretch / convenience command and is part of later phases (see Section 8).

---

## 8. Milestones & Build Phases

### Phase 1a: Foundation (Crawl MVP)

- Project scaffolding and dependency management (`pyproject.toml`, `uv`).
- Configuration system (`config.yaml`) with validation.
- SQLite URL store and schema setup.
- Hacker News API integration (`HackerNewsApiScraper`).
- Basic CLI with `curiopilot run` that:
  - Loads config.
  - Fetches articles from Hacker News via API.
  - Deduplicates against SQLite.
  - Prints raw article list (title + URL) to the terminal.

**Deliverable**: Agent crawls Hacker News via API, deduplicates URLs, and prints results to terminal (no LLM yet).

### Phase 1b: Relevance Filter

- Ollama integration (7B filter model).
- Relevance filter agent with structured Pydantic output.
- Sequential relevance scoring with retry / timeout handling.
- CLI flag to enable / disable filtering behavior (default enabled once stable).

**Deliverable**: Agent crawls Hacker News, filters by relevance using the 7B model, and prints relevant results to the terminal.

### Phase 2: Deep Reading & Briefing

- Deep reader agent (14B) with article extraction and structured summaries.
- Explicit model lifecycle management between 7B and 14B (Ollama `keep_alive` handling).
- Map‑reduce summarization for long articles based on `chunking.max_tokens_per_chunk`.
- Briefing generator (Markdown output) including:
  - Ranked list of relevant articles with summaries.
  - Terminal summary for quick scanning.
- Briefing archive in the `briefings/` folder.
- Rich terminal progress display (overall pipeline and per‑phase progress).

**Deliverable**: Full pipeline from crawl to Markdown briefing for Hacker News (single source), without novelty‑based ranking or knowledge graph sections yet.

### Phase 3: Memory & Novelty

- ChromaDB vector store integration with Ollama embeddings.
- Knowledge graph (NetworkX) with JSON persistence and update logic.
- Novelty scoring engine combining vector similarity and graph novelty.
- Article ranking by combined relevance + novelty score.
- Knowledge graph update after each run.
- “New Concepts”, “Knowledge Graph Update”, and “Suggested Explorations” sections added to the briefing.
- “Existing knowledge synthesis” step that:
  - Queries past summaries and graph for a topic.
  - Generates “What you already know” snippets used in the “Deepening” section.

**Deliverable**: Briefings now rank by novelty; repeated topics are de‑prioritized. Knowledge graph‑based sections appear in the daily briefing.

### Phase 4: Multi‑Source & Polish

- Additional scrapers: Reddit, ArXiv, Hugging Face Papers.
- Generic / fallback scraper for simple HTML or RSS.
- Knowledge gap detector (implemented via graph analytics).
- `curiopilot stats` and `curiopilot history` commands.
- Enhanced error handling, retry logic, and timeout management for all sources.

**Deliverable**: Production‑quality daily tool with multiple sources and robust error handling.

### Phase 5: Query & Stretch Goals

- `curiopilot query` command with synthesis over past knowledge.
- Interactive deep‑dive mode (e.g., “tell me more about article 3”).
- Obsidian export with Markdown files and backlinks.
- Optional spaced repetition / memory decay for knowledge graph familiarity scores.
- Optional `curiopilot add-source` interactive assistant for editing `config.yaml`.

**Deliverable**: Full feature set with interactive exploration and external knowledge export.

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| Websites block scraping / automated access | Source becomes unavailable | Medium | Prefer official APIs and feeds where available (HN API, ArXiv feeds). For scraped sites, rotate user agents, respect robots.txt and add delays. Provide per‑source backoff and retry. |
| Article text extraction is noisy | Poor summaries | Medium | Invest in robust readability heuristics; allow per‑source CSS selectors in config; fall back to `<article>` / `<main>` tags where present. |
| Local 14B model produces weak summaries | Low briefing quality | Medium | Iterate on prompts; use structured output enforcement; add retry logic for malformed responses; consider alternative local models if needed. |
| Knowledge graph grows unwieldy | Slow novelty scoring and graph ops | Low | Prune low‑value nodes (seen once, never again) after 30 days; periodically compact or migrate to SQLite‑backed storage. |
| Ollama model swap latency | Slow pipeline | Low | Batch all 7B work first, then swap once to 14B; use `keep_alive` judiciously; serialize filter and read phases. |
| ChromaDB index corruption or performance issues | Lost or slow memory | Low | Periodic backup of `data/` directory; rely on ChromaDB’s SQLite durability; provide tools for index rebuild if needed. |
| API quota or rate limit for external sources | Missing data for a run | Low–Medium | Implement respectful rate limiting and exponential backoff; cache recent responses; allow disabling problematic sources in config. |

---

## 10. Success Criteria

| Metric | Target |
| --- | --- |
| Daily pipeline completes without manual intervention | ≥ 95% of runs |
| Briefing contains genuinely novel articles (subjective self‑assessment) | ≥ 80% of briefing items feel “new” after 2 weeks of use |
| No repeated topic dominates briefings after first week | Zero “intro to X” articles after X has been read 3+ times |
| Knowledge graph grows meaningfully | ≥ 50 concept nodes after 2 weeks of daily use |
| Query system returns useful synthesis | Relevant answer with source citations for known topics |
| Total pipeline runtime | < 30 minutes per daily run on target hardware |

