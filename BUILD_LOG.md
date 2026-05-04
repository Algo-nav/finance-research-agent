# Finance Research Agent — Build Log

**Project:** Demo #1 — Finance Research Agent (v1)
**Hugging Face:** huggingface.co/spaces/Nav772/finance-research-agent
**GitHub:** github.com/Algo-nav/finance-research-agent
**Working mode:** Heavy teaching (12-14 week target)

---

## Week 1 — Environment Setup and Tool Layer

**Goal:** Local environment configured, all six data tools built, tested, and committed.

### Environment

- Project folder: `~/Desktop/Projects-2.0/finance-research-agent`
- Python 3.12.10, virtual environment via `venv`
- VS Code with interpreter pointed at project venv
- `.env` file for secrets (gitignored), `requirements.txt` committed
- Git initialized, first commit at clean foundation

### Packages Installed

- `anthropic` - Claude API and Agent SDK
- `python-dotenv` - environment variable loading
- `yfinance` - Yahoo Finance data
- `fredapi` - FRED macroeconomic data
- `tavily-python` - web search with content extraction
- `requests` - HTTP for SEC EDGAR and IR fetcher
- `pydantic` - input/output validation on every tool
- `gradio` - UI framework for Hugging Face Space
- `beautifulsoup4` - HTML stripping for IR page fetcher

### Tools Built

**1. `yfinance_tool.py`** - price, market cap, P/E, 52-week range, 1-month change, sector
**2. `fred.py`** - five macro indicators with latest value and trend direction
**3. `fmp.py`** - key ratios, recent news with citation URLs, next earnings date
**4. `tavily_tool.py`** - web search with relevance scores and content snippets
**5. `sec_edgar.py`** - CIK lookup, filing metadata, direct EDGAR URLs
**6. `ir_fetcher.py`** - HTML fetching and stripping, SEC-aware User-Agent handling

### Patterns Established

- Pydantic BaseModel for every input and output
- Optional fields for unreliable data sources
- source field on every output schema for citation grounding
- try/except per operation, return partial results not crashes
- if __name__ == "__main__" test block in every tool file

### API Issues Resolved

| Issue | Resolution |
|---|---|
| FMP 403 on all endpoints | Migrated base URL from api/v3 to stable |
| FMP ratios all null | Corrected field name mappings from raw API response |
| FRED FEDFUNDS 500 error | Swapped get_series_latest_release to get_series |
| EDGAR Archives 403 | SEC-aware User-Agent switching in IR fetcher |
| IR fetcher returning XBRL data | Parked in v2-ideas.md |

### Commits

| Hash | Message |
|---|---|
| d92c965 | Initial project setup: structure, dependencies, key verification |
| 335c429 | Add yfinance tool |
| f08855d | Add FRED macro tool |
| 9f6ae93 | Add FMP tool |
| 6246428 | Add Tavily tool |
| d5be4ef | Add SEC EDGAR tool |
| e45b0d6 | Add IR page fetcher |

---

## Week 2 — Agent Loop

**Goal:** Wire all six tools into the Claude Agent SDK, write the system prompt, run first end-to-end research note.

### Files Built

- `agent/tools/__init__.py` - central tool registry mapping names to (function, PydanticInputModel) tuples
- `prompts/research_note.py` - system prompt with tool sequencing, output format, citation rules
- `agent/agent.py` - agent loop with build_tool_definitions(), execute_tool(), run_research_agent()

### Key Concepts Learned

- Messages API loop: tool_use and tool_result blocks alternate in conversation history
- Tool results go in the user turn, not the assistant turn
- Pydantic schemas generate Claude-compatible JSON tool definitions via model_json_schema()
- Run with python -m agent.agent from project root, not python agent/agent.py

### First End-to-End Run (AAPL)

- Iterations: 4, Tool calls: 7, Output: 13,999 characters
- Every claim cited. No invented data. "Not available" used correctly for missing fields.

### Commits

| Hash | Message |
|---|---|
| 8d81855 | Week 2: agent loop, tool registry, system prompt - first end-to-end run complete |

---

## Week 3 — Reliability and Pre-generation Pipeline

**Goal:** Retry logic, prompt caching, and all 20 reports pre-generated and committed.

### Files Built

- `agent/utils.py` - exponential backoff retry logic (2s, 4s, 8s). Retries on 429/529/connection errors. Raises immediately on 400/401/404.
- `agent/agent.py` updated - prompt caching via cache_control ephemeral block and betas flag
- `scripts/pregenerate.py` - sequential pipeline, 10s sleep between tickers, per-ticker try/except

### Cache Verification (AAPL run)

- Iteration 1: 1,972 tokens written, 0 read
- Iteration 2: 0 written, 1,972 read
- Iteration 3: 346 written, 1,972 read
- Iteration 4: 4,078 written, 2,418 read

### Pre-generation Results

- 20/20 tickers succeeded. Zero failures.
- Average: 90-120 seconds per ticker. Total: ~48 minutes.
- Report lengths: 11,000-16,000 characters each.

### Commits

| Hash | Message |
|---|---|
| 711fa2e | Week 3: retry logic with exponential backoff and prompt caching |
| a42708b | Week 3: pre-generation pipeline, 20 reports generated and committed |

---

## Week 4 — Gradio UI

**Goal:** Build app.py with gallery mode and live regen mode with visible reasoning trace.

### Files Built

**app.py - Two-tab Gradio Blocks application**

Gallery tab: dropdown of 20 tickers, live yfinance snapshot cards, pre-generated report in markdown, preamble stripping on load.

Live Research tab: ticker input, Run Research button, real-time reasoning trace (left column), research note (right column), live snapshot cards on completion. Generator-based streaming via yield.

Design: dark charcoal header (#0f1923), gold accent (#c8a96e), DM Serif Display title, DM Mono labels, DM Sans body, warm off-white background (#f8f7f4).

### Issues Resolved

| Issue | Resolution |
|---|---|
| Agent preamble leaking into report | Strip text before first markdown heading |
| Dark mode overriding theme | Use gr.themes.Base().set() with explicit colors |
| Button color not applying | Targeted button.primary with higher specificity |

### Commits

| Hash | Message |
|---|---|
| a345ebf | Week 4: Gradio UI - gallery tab with live snapshot cards and live regen tab |
| latest | Week 4: UI cleanup - preamble stripping, snapshot cards on live tab, dark mode WIP |

---

## Week 5 — Deployment

**Goal:** Resolve dark mode, deploy to Hugging Face Spaces, configure secrets, verify live.

### Dark Mode Fix

Root cause: Gradio 6 applies dark mode via JavaScript after CSS loads. CSS overrides alone cannot win.

Fix: gr.themes.Base().set() with explicit hex values for all color tokens. Theme system applies before and after JS, immune to system dark mode. Verified working in both light and dark system mode.

### Hugging Face Space Deployment

- Space: huggingface.co/spaces/Nav772/finance-research-agent
- SDK: Gradio. Hardware: CPU Basic (free tier). Visibility: Public.
- README.md updated with Space metadata header.
- pydantic version conflict resolved: pinned to <=2.12.5 to satisfy Gradio MCP extras.
- Five secrets configured: ANTHROPIC_API_KEY, FMP_API_KEY, TAVILY_API_KEY, FRED_API_KEY, EDGAR_USER_AGENT.
- Gallery tab: live, loading pre-generated reports with snapshot cards.
- Live Research tab: agent running end-to-end on Space with real API keys.

### Issues Resolved

| Issue | Resolution |
|---|---|
| Dark mode text invisible | Replaced CSS overrides with gr.themes.Base().set() |
| HF Space build error: pydantic conflict | Pinned pydantic to <=2.12.5 in requirements.txt |
| Force push required on first deploy | HF Space initialized with its own commit |

### Commits

| Hash | Message |
|---|---|
| 5936f74 | Week 5: resolve dark mode - use gr.themes.Base for color control |
| bf9be2a | Fix pydantic version conflict for Hugging Face Space deployment |

---

## Open Issues and Decisions Pending

| Item | Status |
|---|---|
| EDGAR filing URLs return XBRL data | Parked in v2-ideas.md |
| FMP return_on_equity and revenue_growth_yoy null | Accept as v1 limitation |
| Tavily credits | Monitor. Live regen on Space uses real credits per run |
| README copy | Write with positioning-doc voice rules before public promotion |
| LinkedIn post announcing demo | Marketing chat, not this chat |
