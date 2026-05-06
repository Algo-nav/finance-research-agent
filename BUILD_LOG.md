# Build Log

---

## Demo #1 — Finance Research Agent (v1)

**Status: COMPLETE**
**Hugging Face:** huggingface.co/spaces/Nav772/finance-research-agent
**GitHub:** github.com/Algo-nav/finance-research-agent
**Shipped:** May 2026

---

### What was built

A single-agent finance research system that produces structured, citation-grounded research notes for 20 US-listed equities. Built on the Anthropic Claude API with six data tools, a Gradio UI with gallery and live regen tabs, and a pre-generation pipeline for all 20 tickers.

**Tools:** yfinance, FRED, Financial Modeling Prep, SEC EDGAR, Tavily, IR page fetcher.

**Key technical decisions:**
- Single agent, custom Messages API loop. No LangChain, no multi-agent frameworks.
- Pydantic input/output schemas on every tool for validation and citation grounding.
- Prompt caching on the system prompt (ephemeral, 5-minute TTL). Cache reads reduce system prompt token cost by ~90% on iterations 2+.
- Exponential backoff retry logic (2s, 4s, 8s). Retries on 429/529/connection errors. Raises immediately on 400/401/404.
- Hard cap of 10 iterations per agent run.
- Pre-generation pipeline: 20/20 tickers succeeded, 0 failures, ~48 minutes total.
- Report lengths: 11,000-16,000 characters each.
- ReAct and Self-RAG papers cited in README as architectural references.

---

### Weeks summary

| Week | Goal | Status |
|---|---|---|
| 1 | Environment setup, all six tools built and tested | Complete |
| 2 | Agent loop, tool registry, system prompt, first end-to-end run | Complete |
| 3 | Retry logic, prompt caching, pre-generation pipeline (20/20) | Complete |
| 4 | Gradio UI: gallery tab, live regen tab, snapshot cards, streaming | Complete |
| 5 | Dark mode fix, Hugging Face Space deployment, README, secrets | Complete |

---

### Commit history

| Hash | Message |
|---|---|
| d92c965 | Initial project setup: structure, dependencies, key verification |
| 335c429 | Add yfinance tool |
| f08855d | Add FRED macro tool |
| 9f6ae93 | Add FMP tool |
| 6246428 | Add Tavily tool |
| d5be4ef | Add SEC EDGAR tool |
| e45b0d6 | Add IR page fetcher |
| 8d81855 | Week 2: agent loop, tool registry, system prompt |
| 711fa2e | Week 3: retry logic and prompt caching |
| a42708b | Week 3: pre-generation pipeline, 20 reports committed |
| a345ebf | Week 4: Gradio UI |
| 5936f74 | Week 5: dark mode fix |
| bf9be2a | Fix pydantic version conflict for HF Space deployment |
| d1a1417 | Add README with architecture and design decisions |

---

### Open issues carried to v1.1

| Item | Status |
|---|---|
| EDGAR filing URLs return XBRL data in IR fetcher | Parked in v2-ideas.md |
| FMP `return_on_equity` and `revenue_growth_yoy` null | Accept as v1 limitation |
| Tavily credits | Monitor on live Space. Each live regen call uses credits |

---

## Demo #2 — Planned

**Status: Not started**

Candidates: Capital Call Document Intelligence Agent, fixed income/crypto extension of Demo #1, confidence scoring layer on top of Demo #1 citation grounding.

Decision deferred until LinkedIn post for Demo #1 is live and TDS submission is in progress.

---
