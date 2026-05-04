# Finance Research Agent — Build Log

**Project:** Demo #1 — Finance Research Agent (v1)
**Hugging Face:** huggingface.co/Nav772
**GitHub:** github.com/Algo-nav
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

### Folder Structure

```
finance-research-agent/
├── agent/
│   ├── __init__.py
│   ├── agent.py
│   └── tools/
│       ├── __init__.py
│       ├── yfinance_tool.py
│       ├── fred.py
│       ├── fmp.py
│       ├── tavily_tool.py
│       ├── sec_edgar.py
│       └── ir_fetcher.py
├── prompts/
│   └── research_note.py
├── outputs/
├── scripts/
│   ├── verify_keys.py
│   └── pregenerate.py
├── app.py
├── requirements.txt
├── README.md
└── v2-ideas.md
```

### Tools Built

**1. `yfinance_tool.py` — Stock Snapshot**
- Input: ticker, period (default 1mo)
- Output: price, market cap, P/E, 52-week range, 1-month price change, sector, business summary
- Source field: "Yahoo Finance via yfinance"
- Key pattern learned: `Optional` fields for unreliable data sources, `.get()` over dict access

**2. `fred.py` — Macro Snapshot**
- Input: lookback months (default 3)
- Output: five macro indicators (FEDFUNDS, CPIAUCSL, UNRATE, T10Y2Y, SP500) with latest value, date, and trend direction
- Source field: "FRED (Federal Reserve Bank of St. Louis)"
- Key pattern learned: nested Pydantic models, per-series try/except so one failure does not kill the batch
- Issue resolved: swapped `get_series_latest_release` to `get_series` for consistent FEDFUNDS access

**3. `fmp.py` — FMP Fundamentals**
- Input: ticker, news limit (default 5)
- Output: key ratios (P/E, P/B, debt/equity, margins, EPS), recent news with citation URLs, next earnings date
- Source field: "Financial Modeling Prep"
- Key pattern learned: `_get()` helper centralizes HTTP error handling; multiple nested output models in one schema
- Issue resolved: migrated from `api/v3` to `stable` base URL; corrected field name mappings from raw API response

**4. `tavily_tool.py` — Web Search**
- Input: query, max results (default 5), days (default 30)
- Output: list of search results with title, URL, content snippet (500 chars), relevance score, published date
- Source field: "Tavily Web Search"
- Key pattern learned: `score` field as signal for claim reliability; `search_depth="advanced"` for content extraction
- Note: Tavily free tier gives 1000 credits; advanced search uses more credits per call

**5. `sec_edgar.py` — SEC Filings**
- Input: ticker, filing types (default 10-K/10-Q/8-K), max filings (default 5)
- Output: CIK, list of filings with form type, date, and direct EDGAR URL
- Source field: "SEC EDGAR"
- Key patterns learned: two-step CIK lookup (ticker to CIK via company_tickers.json), accession number formatting (dashes removed for URL construction), EDGAR requires `User-Agent: Name Email` header
- `EDGAR_USER_AGENT` added to `.env`

**6. `ir_fetcher.py` — IR Page Fetcher**
- Input: URL, max length (default 8000 chars)
- Output: page title, cleaned text (HTML stripped), content length, truncation flag, source URL
- Source field: the URL itself (changes per call)
- Key patterns learned: BeautifulSoup for HTML stripping, removing script/style/nav/footer tags before text extraction, SEC-aware User-Agent switching
- Issue resolved: SEC Archives endpoint requires EDGAR User-Agent, not browser User-Agent

### Patterns Established (Apply to All Tools)

- Pydantic `BaseModel` for every input and output
- `Optional[field]` for any data that may be missing from the source
- `source` field on every output schema for citation grounding
- `try/except` per operation, return partial results not crashes
- `if __name__ == "__main__"` test block in every tool file
- `load_dotenv()` at top of every tool file

### API Issues Resolved

| Issue | Resolution |
|---|---|
| FMP 403 on all endpoints | Migrated base URL from `api/v3` to `stable` |
| FMP ratios all null | Corrected field name mappings from raw API response |
| FRED FEDFUNDS 500 error | Swapped `get_series_latest_release` to `get_series` |
| EDGAR Archives 403 | SEC-aware User-Agent switching in IR fetcher |
| IR fetcher returning XBRL data | Known issue: EDGAR primary document URLs point to XBRL files. Parked in `v2-ideas.md` |

### Commits

| Hash | Message |
|---|---|
| d92c965 | Initial project setup: structure, dependencies, key verification |
| 335c429 | Add yfinance tool: StockSnapshotInput/Output schemas and get_stock_snapshot function |
| f08855d | Add FRED macro tool: five indicators with latest value and trend direction |
| 9f6ae93 | Add FMP tool: key ratios, news with citation URLs, next earnings date |
| 6246428 | Add Tavily tool: web search with citation URLs, relevance scores, content snippets |
| d5be4ef | Add SEC EDGAR tool: CIK lookup, filing metadata, direct citation URLs |
| e45b0d6 | Add IR page fetcher: HTML stripping, SEC User-Agent handling, citation URL passthrough |

---

## Week 2 — Agent Loop

**Goal:** Wire all six tools into the Claude Agent SDK, write the system prompt, run first end-to-end research note.

### Files Built

**`agent/tools/__init__.py` — Tool Registry**

Central registry mapping tool names to `(function, PydanticInputModel)` tuples. When the agent receives a `tool_use` block from Claude, it looks up the tool name here, validates arguments against the input model, and executes the function. All six tools registered.

```python
TOOL_REGISTRY = {
    "get_stock_snapshot": (get_stock_snapshot, StockSnapshotInput),
    "get_macro_snapshot": (get_macro_snapshot, MacroSnapshotInput),
    "get_fmp_fundamentals": (get_fmp_fundamentals, FMPInput),
    "search_web": (search_web, TavilySearchInput),
    "get_sec_filings": (get_sec_filings, EDGARInput),
    "fetch_ir_page": (fetch_ir_page, IRFetchInput),
}
```

**`prompts/research_note.py` — System Prompt**

Instructions covering: tool sequencing (snapshot and macro first, then fundamentals and filings, then web search), output format (seven sections), citation rules (every claim must cite a source, format as `[Source: URL]`), and hard constraints (no invented data, 10 tool call cap, write for finance professionals).

**`agent/agent.py` — Agent Loop**

Three functions:

- `build_tool_definitions()`: generates Claude-compatible JSON tool schemas from Pydantic input models via `model_json_schema()`. Schemas stay in sync with validation automatically.
- `execute_tool()`: looks up tool by name, validates input with Pydantic, executes function, returns result as JSON string.
- `run_research_agent(ticker)`: the main loop. Calls `client.messages.create()`, checks `stop_reason`, executes tool calls if `tool_use`, returns final text if `end_turn`, hard stops at 10 iterations.

### Key Concepts Learned

**The Messages API loop**
- `client.messages.create()` returns either a text response or a `tool_use` block
- Tool results are appended as `user` turn messages (not assistant)
- The loop repeats until `stop_reason == "end_turn"` or iteration cap is hit
- Conversation history grows with each iteration: user, assistant, user (tool results), assistant, repeat

**Tool definitions**
- Claude reads the `description` field of each tool to decide when to call it
- Input schema generated from Pydantic `model_json_schema()` — no duplication
- `execute_tool()` validates Claude's arguments before they reach the function

**Running as a module**
- `python -m agent.agent` from project root (not `python agent/agent.py`)
- `-m` flag adds project root to Python path, resolving package imports correctly

### First End-to-End Run (AAPL)

- Iterations: 4
- Tool calls: 7
- Output length: 13,999 characters
- Tool call sequence: snapshot + macro + fundamentals + filings (iteration 1), two web searches for analyst commentary (iteration 2), one targeted web search for China/risks (iteration 3), final note compiled (iteration 4)
- Citation grounding: every bull/bear case point, every catalyst, every metric cited to source URL or tool name
- "Not available" correctly used for Return on Equity (not in FMP stable endpoint) rather than inventing a value
- CEO transition (Tim Cook to John Ternus, September 1 2026) surfaced from web search and integrated coherently across multiple sections

### Commits

| Hash | Message |
|---|---|
| 8d81855 | Week 2: agent loop, tool registry, system prompt - first end-to-end run complete |

---

## Week 3 — Reliability and Pre-generation Pipeline

**Goal:** Retry logic, prompt caching, and all 20 reports pre-generated and committed.

### Files Built

**`agent/utils.py` — Retry Logic**

Wraps `client.messages.create()` with exponential backoff retry handling.

- Retries on: `RateLimitError`, `APIConnectionError`, `APIStatusError` with 529 status.
- Raises immediately on: 400, 401, 404 and other non-retryable status codes.
- Backoff schedule: 2s, 4s, 8s (BASE_DELAY=2, MAX_RETRIES=3).
- Routes beta feature calls (prompt caching) through `client.beta.messages.create()` automatically when `betas` key is present in kwargs.

Key pattern learned: distinguishing retryable (transient) from non-retryable (client error) failures. Retrying a 400 wastes time and credits; retrying a 429 is correct behavior.

**`agent/agent.py` — Prompt Caching**

System prompt restructured from a plain string to a cached content block:

```python
CACHED_SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}
    }
]
```

- Beta flag: `betas=["prompt-caching-2024-07-31"]` required to activate caching.
- Cache TTL: 5 minutes (ephemeral). Sufficient for a single agent run.
- Verified working: iteration 1 shows cache write tokens, iterations 2+ show cache read tokens.
- `max_tokens` increased from 4096 to 8096 to accommodate full research note output.

Cache verification results (AAPL run):
- Iteration 1: 1,972 tokens written, 0 read.
- Iteration 2: 0 written, 1,972 read.
- Iteration 3: 346 written, 1,972 read.
- Iteration 4: 4,078 written, 2,418 read.

**`scripts/pregenerate.py` — Pre-generation Pipeline**

Runs the agent on all 20 tickers sequentially, saves each report as JSON to `outputs/`, logs timing and success/failure per ticker.

- Sequential execution with 10-second sleep between tickers to avoid rate limit cascades.
- Per-ticker try/except: one failure does not stop the pipeline.
- Output format: `{ticker, generated_at, report}` saved as `{ticker_lower}_report.json`.
- Pipeline run log saved to `outputs/pipeline_log.json`.

### Pre-generation Run Results

- 20/20 tickers succeeded. Zero failures.
- Average run time: 90-120 seconds per ticker.
- Total pipeline time: approximately 48 minutes.
- Report lengths: 11,000-16,000 characters per report.
- All reports committed to `outputs/` in the GitHub repo.

### Tickers Generated

AAPL, MSFT, NVDA, GOOGL, META, AMZN, TSLA, JPM, BAC, BRK-B, UNH, JNJ, XOM, CAT, WMT, COST, TSM, ASML, PLTR, ARM.

### Issues Resolved

| Issue | Resolution |
|---|---|
| `max_tokens` too low, agent hit limit mid-response | Increased from 4096 to 8096 |
| `betas` parameter on wrong client method | Routed beta calls through `client.beta.messages.create()` in utils.py |
| `datetime.utcnow()` deprecation warning | Replaced with `datetime.now(timezone.utc)` |

### Commits

| Hash | Message |
|---|---|
| 711fa2e | Week 3: retry logic with exponential backoff and prompt caching |
| a42708b | Week 3: pre-generation pipeline, 20 reports generated and committed |

---

## Week 4 — Gradio UI

**Goal:** Build `app.py` with gallery mode (pre-generated reports) and live regen mode (agent runs in real time with visible reasoning trace).

### Files Built

**`app.py` — Full Gradio UI**

Two-tab Gradio Blocks application.

**Gallery tab:**
- Dropdown of all 20 tickers.
- Live snapshot cards (yfinance call on ticker select): Current Price, Market Cap, P/E, 52-Week Range, 1-Month Change, Sector.
- Pre-generated research note rendered as markdown below the cards.
- Source attribution on cards: "Yahoo Finance via yfinance. Live data."
- No API calls for the report itself. Instant load from `outputs/` JSON files.

**Live Research tab:**
- Ticker text input and Run Research button.
- Reasoning trace panel (left column): updates in real time as tool calls execute. Shows tool name, input preview, and result preview per call.
- Research note panel (right column): populates when agent finishes.
- Live snapshot cards appear above both columns when research completes.
- Generator-based streaming via Python `yield` so UI updates incrementally.

**Design:**
- Dark charcoal header (`#0f1923`) with gold accent line (`#c8a96e`).
- DM Serif Display for title. DM Mono for labels and reasoning trace. DM Sans for body.
- Warm off-white background (`#f8f7f4`).
- Run Research button: dark charcoal, inverts to gold on hover.

### Key Concepts Learned

**Gradio Blocks vs Interface**
- `gr.Interface` is single input/output. `gr.Blocks` supports complex layouts, multiple tabs, custom event wiring.
- `gr.Tabs` and `gr.Tab` for tab structure.
- `.change()` for dropdown events, `.click()` for button events.

**Gradio streaming with generators**
- Functions that `yield` instead of `return` push incremental updates to the UI.
- Each `yield` fires a UI update. Used to show reasoning trace updating per tool call.
- Yield tuples when multiple outputs need updating simultaneously.

**Gradio CSS in v6**
- `css` parameter belongs in `gr.Blocks()` constructor.
- Gradio CSS variables (`--body-background-fill` etc.) must be overridden to force light mode.
- `gr.themes.Base().set()` is the reliable way to control theme colors.

### Issues Resolved

| Issue | Resolution |
|---|---|
| Agent preamble text leaking into report | Strip text before first markdown heading on load and in agent loop |
| Dark mode overriding light theme | Ongoing. `gr.themes.Base().set()` with explicit colors. WIP. |
| Button color not applying | Targeted `button.primary` selector with higher specificity |
| `css` parameter warning in Gradio 6 | Moved `css` to `gr.Blocks()` constructor |

### Commits

| Hash | Message |
|---|---|
| a345ebf | Week 4: Gradio UI - gallery tab with live snapshot cards and live regen tab |
| latest | Week 4: UI cleanup - preamble stripping, snapshot cards on live tab, dark mode WIP |

---

## Week 5 — Planned

1. Resolve dark mode override issue definitively.
2. Deploy to Hugging Face Spaces.
3. Configure Space secrets (API keys).
4. Test cold start and gallery load on Space.
5. Fix any deployment-specific issues.

---

## Open Issues and Decisions Pending

| Item | Status |
|---|---|
| Dark mode CSS override | WIP. Gradio 6 theme variables not fully overriding system dark mode. |
| EDGAR filing URLs return XBRL data in IR fetcher | Parked in v2-ideas.md |
| FMP `return_on_equity` and `revenue_growth_yoy` null | Accept as v1 limitation |
| Tavily credits | Monitor remaining credits before live regen testing |
| README copy | Write at week 8 with positioning-doc voice rules |
| Hugging Face Space deployment | Week 5 |
