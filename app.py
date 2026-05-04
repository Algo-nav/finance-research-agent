import os
import json
import gradio as gr
from dotenv import load_dotenv

load_dotenv()

# Directory where pre-generated reports are stored.
OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

# The 20 tickers in display order for the gallery dropdown.
GALLERY_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA",
    "JPM", "BAC", "BRK-B",
    "UNH", "JNJ",
    "XOM", "CAT",
    "WMT", "COST",
    "TSM", "ASML",
    "PLTR", "ARM",
]

def load_report(ticker: str) -> str:
    """
    Loads a pre-generated report from the outputs directory.
    Returns the report text or an error message if the file is not found.
    """
    filename = f"{ticker.lower().replace('-', '_')}_report.json"
    filepath = os.path.join(OUTPUTS_DIR, filename)

    if not os.path.exists(filepath):
        return f"No pre-generated report found for {ticker}. Try the Live Research tab."

    with open(filepath, "r") as f:
        data = json.load(f)

    # Return just the report text. generated_at is metadata, not display content.
    return data.get("report", "Report file exists but contains no content.")


def get_snapshot_cards_html(ticker: str) -> str:
    """
    Fetches live snapshot data from yfinance and returns
    an HTML block of metric cards for display above the report.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        history = yf.Ticker(ticker).history(period="1mo")

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        market_cap = info.get("marketCap")
        pe = info.get("trailingPE")
        week_high = info.get("fiftyTwoWeekHigh")
        week_low = info.get("fiftyTwoWeekLow")
        company = info.get("longName", ticker)
        currency = info.get("currency", "USD")
        sector = info.get("sector", "N/A")

        # 1-month price change
        if history is not None and not history.empty and len(history) >= 2:
            start = history["Close"].iloc[0]
            end = history["Close"].iloc[-1]
            change_pct = round(((end - start) / start) * 100, 2)
            change_str = f"+{change_pct}%" if change_pct >= 0 else f"{change_pct}%"
            change_color = "#2e7d4f" if change_pct >= 0 else "#c0392b"
        else:
            change_str = "N/A"
            change_color = "#6b6560"

        # Format market cap
        if market_cap:
            if market_cap >= 1_000_000_000_000:
                cap_str = f"${market_cap / 1_000_000_000_000:.2f}T"
            elif market_cap >= 1_000_000_000:
                cap_str = f"${market_cap / 1_000_000_000:.1f}B"
            else:
                cap_str = f"${market_cap / 1_000_000:.0f}M"
        else:
            cap_str = "N/A"

        price_str = f"{currency} {price:,.2f}" if price else "N/A"
        pe_str = f"{pe:.1f}x" if pe else "N/A"
        range_str = f"{week_low:.2f} - {week_high:.2f}" if week_low and week_high else "N/A"

        cards = [
            ("Current Price", price_str, currency),
            ("Market Cap", cap_str, "Yahoo Finance"),
            ("P/E Ratio (TTM)", pe_str, "Yahoo Finance"),
            ("52-Week Range", range_str, "Yahoo Finance"),
            ("1-Month Change", f'<span style="color:{change_color};font-weight:600">{change_str}</span>', "Yahoo Finance"),
            ("Sector", sector, "Yahoo Finance"),
        ]

        cards_html = f"""
        <div style="margin: 1.5rem 0 0.5rem 0;">
            <div style="
                font-family: 'DM Mono', monospace;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: #6b6560;
                margin-bottom: 0.75rem;
            ">{company} ({ticker})</div>
            <div style="
                display: grid;
                grid-template-columns: repeat(6, 1fr);
                gap: 0.75rem;
                margin-bottom: 0.5rem;
            ">
        """

        for label, value, source in cards:
            cards_html += f"""
                <div style="
                    background: #ffffff;
                    border: 1px solid #e2ddd6;
                    border-top: 3px solid #0f1923;
                    padding: 0.85rem 1rem;
                    border-radius: 2px;
                ">
                    <div style="
                        font-family: 'DM Mono', monospace;
                        font-size: 0.65rem;
                        text-transform: uppercase;
                        letter-spacing: 0.06em;
                        color: #6b6560;
                        margin-bottom: 0.35rem;
                    ">{label}</div>
                    <div style="
                        font-family: 'DM Sans', sans-serif;
                        font-size: 1rem;
                        font-weight: 600;
                        color: #0f1923;
                    ">{value}</div>
                </div>
            """

        cards_html += """
            </div>
            <div style="
                font-family: 'DM Mono', monospace;
                font-size: 0.65rem;
                color: #9b9590;
                text-align: right;
                letter-spacing: 0.04em;
            ">Source: Yahoo Finance via yfinance. Live data.</div>
        </div>
        """
        return cards_html

    except Exception as e:
        return f'<div style="color:#c0392b;font-size:0.85rem;">Snapshot unavailable: {e}</div>'


def load_gallery(ticker: str):
    """Returns both the snapshot cards HTML and the report markdown."""
    cards = get_snapshot_cards_html(ticker)
    report = load_report(ticker)
    return cards, report


def run_agent_streaming(ticker: str):
    """
    Generator function that runs the research agent and yields progress updates.
    Each yield pushes an update to the Gradio UI in real time.
    Yields tuples of (reasoning_trace, report_text).
    """
    from agent.agent import build_tool_definitions, execute_tool, CACHED_SYSTEM_PROMPT
    from agent.utils import call_with_retry
    from anthropic import Anthropic
    import json

    ticker = ticker.strip().upper()
    if not ticker:
        yield "Please enter a ticker symbol.", ""
        return

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    tool_definitions = build_tool_definitions()

    messages = [
        {
            "role": "user",
            "content": (
                f"Produce a complete research note for {ticker}. "
                f"Use all available tools to gather data. "
                f"Every claim must be cited."
            )
        }
    ]

    MAX_ITERATIONS = 10
    iteration = 0
    reasoning_lines = []

    reasoning_lines.append(f"Starting research for **{ticker}**...")
    yield "\n".join(reasoning_lines), ""

    while iteration < MAX_ITERATIONS:
        iteration += 1
        reasoning_lines.append(f"\n**Iteration {iteration}/{MAX_ITERATIONS}**")
        yield "\n".join(reasoning_lines), ""

        try:
            response = call_with_retry(
                client,
                model="claude-sonnet-4-5",
                max_tokens=8096,
                system=CACHED_SYSTEM_PROMPT,
                tools=tool_definitions,
                messages=messages,
                betas=["prompt-caching-2024-07-31"],
            )
        except Exception as e:
            reasoning_lines.append(f"API error: {e}")
            yield "\n".join(reasoning_lines), ""
            return

        messages.append({
            "role": "assistant",
            "content": response.content
        })

        if response.stop_reason == "end_turn":
            reasoning_lines.append("Research complete.")
            final_report = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_report = block.text
                    break
            yield "\n".join(reasoning_lines), final_report
            return

        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    # Show the tool call in the reasoning trace.
                    input_preview = json.dumps(block.input)[:80]
                    reasoning_lines.append(
                        f"- Tool: **{block.name}** | Input: `{input_preview}...`"
                    )
                    yield "\n".join(reasoning_lines), ""

                    result = execute_tool(block.name, block.input)

                    # Show a short preview of the result.
                    result_preview = result[:120].replace("\n", " ")
                    reasoning_lines.append(f"  Result preview: `{result_preview}...`")
                    yield "\n".join(reasoning_lines), ""

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({
                "role": "user",
                "content": tool_results
            })

        else:
            reasoning_lines.append(
                f"Unexpected stop reason: {response.stop_reason}. Stopping."
            )
            yield "\n".join(reasoning_lines), ""
            return

    reasoning_lines.append("Reached maximum iterations.")
    yield "\n".join(reasoning_lines), ""


custom_css = """
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap');

/* ---- Base ---- */
.gradio-container {
    max-width: 100% !important;
    margin: 0 auto !important;
    background: #f8f7f4 !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ---- Header ---- */
.app-header {
    background: #0f1923;
    padding: 2.5rem 2rem 2rem 2rem;
    margin-bottom: 1.5rem;
    border-bottom: 3px solid #c8a96e;
}

.app-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2.4rem;
    font-weight: 400;
    color: #f8f7f4;
    letter-spacing: -0.5px;
    margin-bottom: 0.4rem;
}

.app-subtitle {
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    color: #c8a96e;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ---- Tabs ---- */
.tab-nav {
    background: #f8f7f4 !important;
    border-bottom: 1px solid #e2ddd6 !important;
}

button.selected {
    border-bottom: 2px solid #0f1923 !important;
    color: #0f1923 !important;
    font-weight: 600 !important;
}

/* ---- Section headings inside tabs ---- */
.gr-markdown h2 {
    font-family: 'DM Serif Display', serif !important;
    font-size: 1.4rem !important;
    font-weight: 400 !important;
    color: #0f1923 !important;
    border-bottom: 1px solid #e2ddd6;
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
}

.gr-markdown h3 {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    color: #0f1923 !important;
}

/* ---- Report display area ---- */
.gr-markdown {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.93rem !important;
    line-height: 1.7 !important;
    color: #2c2c2c !important;
}

/* ---- Dropdown and inputs ---- */
.gr-dropdown, .gr-textbox {
    border: 1px solid #d1ccc4 !important;
    border-radius: 4px !important;
    background: #ffffff !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ---- Run button ---- */
.gr-button-primary {
    background: #0f1923 !important;
    color: #f8f7f4 !important;
    border: none !important;
    border-radius: 4px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    transition: background 0.2s ease !important;
}

.gr-button-primary:hover {
    background: #c8a96e !important;
    color: #0f1923 !important;
}

/* ---- Reasoning trace panel ---- */
.reasoning-panel .gr-markdown {
    background: #0f1923 !important;
    color: #a8c4a0 !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.8rem !important;
    padding: 1rem !important;
    border-radius: 4px !important;
    min-height: 200px !important;
}

/* ---- Labels ---- */
label {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: #6b6560 !important;
}
"""

def build_app():
    with gr.Blocks(
        title="Finance Research Agent",
        css=custom_css,
        theme=gr.themes.Base(
            font=gr.themes.GoogleFont("DM Sans"),
        )
    ) as app:

        gr.HTML("""
            <div class="app-header">
                <div class="app-title">Finance Research Agent</div>
                <div class="app-subtitle">
                    Citation-grounded equity research &nbsp;|&nbsp;
                    Claude + SEC EDGAR + FRED + FMP + Tavily
                </div>
            </div>
        """)

        with gr.Tabs():
            with gr.Tab("Gallery"):
                gr.Markdown("""
                ## Pre-generated Research Notes
                Select a ticker to load a pre-generated research note.
                Reports cover macro context, bull and bear cases,
                recent catalysts, key metrics, risks, and what to watch next.
                Every claim is cited to its source.
                """)
                with gr.Row():
                    ticker_dropdown = gr.Dropdown(
                        choices=GALLERY_TICKERS,
                        label="Select Ticker",
                        value="AAPL",
                        scale=1,
                    )

                # Live snapshot cards above the report.
                snapshot_cards = gr.HTML(
                    value=get_snapshot_cards_html("AAPL"),
                )

                report_display = gr.Markdown(
                    value=load_report("AAPL"),
                    label="Research Note",
                )

                ticker_dropdown.change(
                    fn=load_gallery,
                    inputs=ticker_dropdown,
                    outputs=[snapshot_cards, report_display],
                )

            with gr.Tab("Live Research"):
                gr.Markdown("""
                ## Live Research
                Enter any US-listed ticker and watch the agent reason in real time.
                The agent calls up to 10 tools, cites every claim, and produces
                a structured research note. Takes 60-120 seconds.
                """)
                with gr.Row():
                    ticker_input = gr.Textbox(
                        label="Ticker Symbol",
                        placeholder="e.g. AAPL, NVDA, JPM",
                        scale=3,
                    )
                    run_button = gr.Button(
                        "Run Research",
                        variant="primary",
                        scale=1,
                    )
                with gr.Row():
                    with gr.Column(scale=1):
                        reasoning_display = gr.Markdown(
                            label="Reasoning Trace",
                            value="Reasoning trace will appear here.",
                        )
                    with gr.Column(scale=2):
                        live_report_display = gr.Markdown(
                            label="Research Note",
                            value="Research note will appear here.",
                        )
                run_button.click(
                    fn=run_agent_streaming,
                    inputs=ticker_input,
                    outputs=[reasoning_display, live_report_display],
                )

    return app


if __name__ == "__main__":
    app = build_app()
    app.launch()