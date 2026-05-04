---
title: Finance Research Agent
emoji: 📊
colorFrom: gray
colorTo: yellow
sdk: gradio
sdk_version: "6.14.0"
app_file: app.py
pinned: false
license: mit
---
# Finance Research Agent

A single-agent system that produces structured, citation-grounded equity research notes for US-listed stocks. Built on the Anthropic Claude API with six data tools covering price data, macroeconomic indicators, fundamentals, SEC filings, and web search.

Every claim in the output links to its source. The reasoning trace is visible. Made sure nothing is invented.

**Live demo:** [huggingface.co/spaces/Nav772/finance-research-agent](https://huggingface.co/spaces/Nav772/finance-research-agent)

---

## What it does

The agent takes a ticker symbol and produces a research note with seven sections: Snapshot, Bull Case, Bear Case, Recent Catalysts, Key Metrics, Risks, and What to Watch Next. Each section cites the tool output or URL that backs the claim.

The gallery tab loads pre-generated reports for 20 tickers instantly. The live research tab runs the agent in real time, with tool calls and result previews updating as the agent reasons. Reports run 11,000-16,000 characters and take 60-120 seconds on live regen.

---

## Architecture

Single agent, six tools. No multi-agent orchestration. Claude Sonnet handles reasoning; the tools handle data retrieval.

**Tools:**

| Tool | Source | What it fetches |
|---|---|---|
| `get_stock_snapshot` | Yahoo Finance (yfinance) | Price, market cap, P/E, 52-week range, 1-month change |
| `get_macro_snapshot` | FRED | Fed Funds Rate, CPI, unemployment, yield curve, S&P 500 level |
| `get_fmp_fundamentals` | Financial Modeling Prep | Key ratios, recent news with URLs, next earnings date |
| `get_sec_filings` | SEC EDGAR | Recent 10-K, 10-Q, 8-K filings with direct filing URLs |
| `search_web` | Tavily | Analyst commentary, recent news, earnings reactions |
| `fetch_ir_page` | Any URL | Full page content for earnings transcripts and IR materials |

---

## Agent loop

The loop is a standard Messages API cycle with no framework dependencies. Here is what happens on each run:

1. An initial user message is sent with the ticker and instructions.
2. `client.messages.create()` returns either a `tool_use` block or a final text response.
3. On `tool_use`, each requested tool is looked up in a central registry, its arguments are validated against a Pydantic input schema, the function executes, and the result is appended as a `tool_result` in the next `user` message.
4. The API is called again with the updated message history. This repeats until `stop_reason == "end_turn"`.
5. A hard cap of 10 iterations prevents runaway loops. If the agent hits 10 without finishing, it returns whatever it has.

Tool definitions are generated directly from Pydantic input schemas via `model_json_schema()`. The schemas stay in sync with the validation layer automatically. No duplicate definitions.

A typical run on a well-covered ticker takes 4-6 iterations and 7-10 tool calls.

---

## Prompt caching

The system prompt is sent on every iteration of the agent loop. Without caching, a 5-iteration run transmits the system prompt 5 times. Across 20 tickers in the pre-generation pipeline, that is 100+ identical transmissions.

Prompt caching is enabled via `cache_control: {"type": "ephemeral"}` on the system prompt block and the `betas=["prompt-caching-2024-07-31"]` flag. The cache TTL is 5 minutes, which covers a full agent run comfortably.

Verified cache behavior on a typical AAPL run:
- Iteration 1: 1,972 tokens written to cache, 0 read.
- Iteration 2: 0 written, 1,972 read.
- Iteration 3: 346 written (new conversation content), 1,972 read.
- Iteration 4: 4,078 written, 2,418 read.

Cache reads cost roughly 90% less than cache writes. On a 5-iteration run, caching the system prompt reduces its token cost by approximately 80%.

---

## Retry logic

All API calls go through an exponential backoff wrapper in `agent/utils.py`. The wrapper distinguishes between retryable and non-retryable failures:

- **Retryable:** `RateLimitError` (429), `APIStatusError` with status 529 (overloaded), `APIConnectionError`. Backoff schedule: 2s, 4s, 8s. Maximum 3 retries.
- **Non-retryable:** `APIStatusError` with status 400, 401, or 404. These indicate a problem with the request itself. Retrying wastes credits and time. The wrapper raises immediately.

The wrapper also handles the beta client routing. When `betas` is present in kwargs, it calls `client.beta.messages.create()` instead of `client.messages.create()`. This keeps all retry and routing logic in one place.

---

## Tool validation

Every tool has a Pydantic `BaseModel` for inputs and a separate `BaseModel` for outputs. When Claude returns a `tool_use` block, its arguments are validated against the input schema before reaching the function. If Claude hallucinates an argument name or passes the wrong type, Pydantic raises a `ValidationError` at the boundary with a structured error message that gets returned to Claude as a `tool_result`. The agent loop continues rather than crashing.

Output schemas carry a `source` field on every model. This field travels with the data through the agent loop and into the research note, providing the citation trail from raw API response to final claim.

Fields that may be missing from a data source are typed as `Optional`. Yahoo Finance's `info` dict is inconsistent across tickers. FMP's stable API does not expose `return_on_equity` or `revenue_growth_yoy` at the Starter tier. `Optional` fields model this honestly. The agent uses "Not available" rather than inventing values.

---

## Pre-generation pipeline

The gallery loads 20 pre-generated reports from `outputs/` as static JSON. Each report was generated by `scripts/pregenerate.py`, which runs the agent sequentially on all 20 tickers with a 10-second sleep between runs to avoid rate limit cascades.

Pipeline run stats:
- 20/20 tickers succeeded. Zero failures.
- Average run time: 90-120 seconds per ticker.
- Total pipeline time: approximately 48 minutes.
- Report lengths: 11,000-16,000 characters each.

The pipeline uses per-ticker `try/except` so one failure does not stop the run. Results and timing are logged to `outputs/pipeline_log.json`.

---

## Citation grounding

The system prompt instructs Claude to cite every factual claim inline as `[Source: URL]` or `[Source: Tool Name]` when no URL is available. The instruction is a hard constraint, not a suggestion: "Never make a claim without a source. If a tool returns None or empty, say 'Not available' rather than omitting the field or inventing a value."

In practice, bull and bear case points link to SEC filing URLs, earnings call transcript pages, or news articles. Macro context cites FRED series. Key metrics cite the specific tool that returned them. A finance reader can verify any claim in the note in under a minute.

---

## Design decisions

**Why single-agent?** Multi-agent frameworks add coordination overhead that is not justified for a single document output. One agent with well-defined tools is easier to debug, cheaper to run, and produces more coherent outputs than a coordinator farming subtasks to sub-agents. The system prompt controls tool call sequencing: snapshot and macro first, then fundamentals and filings, then web search. This produces consistent report structure without a separate orchestration layer.

**Why citation grounding instead of confidence scoring?** Citations are verifiable by the reader. A confidence score of 0.87 is not. This is the right default for a finance context where hallucinated claims have real consequences. Confidence scoring is the next layer, not the foundation.

**Why pre-generated reports in the gallery?** Cold starts on a free-tier CPU Space take 30-60 seconds before the first request can be served. Pre-generated reports load instantly and ensure the demo is always functional regardless of API availability or Tavily credit balance. The live regen tab demonstrates the agent's reasoning process for visitors who want to see it work.

**Why Pydantic on every tool?** Tool arguments from Claude are unvalidated JSON. Without a schema, a malformed argument propagates silently into the tool function and produces a corrupted result that Claude reasons on top of. Pydantic validates at the boundary. Errors surface at the tool call, not downstream in the output.

**Why a custom agent loop instead of LangChain or an agent framework?** The Messages API loop is 60 lines of Python. Frameworks add abstraction that makes debugging harder and behavior less predictable. For a production finance system where every tool call matters, readable code beats convenience.

---

## References

This system implements patterns from two papers worth reading if you are building production agent systems:

**ReAct: Synergizing Reasoning and Acting in Language Models** (Yao et al., 2023) describes the interleaving of reasoning and tool actions that underlies the agent loop here. The visible reasoning trace in the live regen tab is a direct application of the ReAct pattern. [arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629)

**Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection** (Asai et al., 2023) introduces citation grounding and self-critique as core output requirements rather than optional features. The per-claim citation rule in this system's prompt follows the same principle. [arxiv.org/abs/2310.11511](https://arxiv.org/abs/2310.11511)

---

## Stack

- **Agent:** Anthropic Claude Sonnet via Messages API
- **Orchestration:** Custom agent loop (no LangChain, no CrewAI)
- **Validation:** Pydantic v2
- **Caching:** Anthropic prompt caching (ephemeral, 5-minute TTL)
- **Retry:** Custom exponential backoff (2s, 4s, 8s)
- **Data:** yfinance, fredapi, Financial Modeling Prep, SEC EDGAR, Tavily
- **UI:** Gradio 6
- **Hosting:** Hugging Face Spaces (CPU Basic)

---

## Running locally

```bash
git clone https://github.com/Algo-nav/finance-research-agent
cd finance-research-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with:

ANTHROPIC_API_KEY=your_key
FMP_API_KEY=your_key
TAVILY_API_KEY=your_key
FRED_API_KEY=your_key
EDGAR_USER_AGENT=Your Name your@email.com

Run the UI:

```bash
python app.py
```

Run the pre-generation pipeline:

```bash
python scripts/pregenerate.py
```

---

## Repo structure

agent/
tools/            # Six data tools, one file each
agent.py          # Agent loop
utils.py          # Retry logic
prompts/
research_note.py  # System prompt
outputs/            # Pre-generated reports (JSON)
scripts/
pregenerate.py    # Pipeline to generate all 20 reports
app.py              # Gradio UI

---

Built by [Navneet Danturi](https://www.linkedin.com/in/navneet-danturi/)