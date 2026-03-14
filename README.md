## CurioPilot

CurioPilot is a local, privacy‑preserving research assistant that crawls your configured sources, filters articles by relevance to your interests, and (in later phases) builds a persistent knowledge graph.

### Quickstart

1. **Install dependencies** (from the project root, using `uv` or `pip`):

```bash
uv sync
```

2. **Create a config file** at `config.yaml` (see `docs/PRD.md` for the full schema; the MVP uses a single Hacker News source).

3. **Run the CLI**:

```bash
curiopilot run --dry-run
```

This will load your config, fetch Hacker News stories via API, deduplicate them against the local SQLite database, and print newly discovered articles to the terminal.

