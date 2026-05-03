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

## Week 3 — Planned

1. Retry logic with exponential backoff for Anthropic API rate limits and network timeouts.
2. Prompt caching: cache the system prompt across iterations to reduce API cost by 5-10x.
3. Pre-generation pipeline: `scripts/pregenerate.py` runs all 20 tickers, saves reports as JSON to `outputs/`.

---

## Open Issues and Decisions Pending

| Item | Status |
|---|---|
| EDGAR filing URLs return XBRL data in IR fetcher | Parked in v2-ideas.md. Fix when wiring agent to use filing index pages |
| FMP `return_on_equity` and `revenue_growth_yoy` null | Not exposed in stable Starter tier. Accept as limitation for v1 |
| Tavily free tier (1000 credits) | Sufficient for build and 20-report pre-generation. Monitor usage |
| Gradio vs Streamlit for Space UI | Deferred to week 5-6 when UI phase begins. Gradio recommended per spec |
| Prompt caching implementation | Week 3 |
| GitHub remote setup (Algo-nav) | Pending. Do before week 3 pre-generation run |
