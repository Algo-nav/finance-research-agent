import os
from typing import Optional
from pydantic import BaseModel, Field
import yfinance as yf

class StockSnapshotInput(BaseModel):
    """Input schema for the Stock Snapshot Tool."""
    ticker: str = Field(
        description="The stock ticker symbol, e.g. AAPL, MSFT, NVDA. Must be a valid US-listed equity ticker."
    )
    period: str = Field(
        default="1mo",
        description="Price history period to fetch. Use '1mo' for one month, '3mo' for three months. Defaults to '1mo'."
    )

class StockSnapshotOutput(BaseModel):
    """Structured output for the Stock Snapshot Tool."""
    ticker: str
    company_name: Optional[str]
    current_price: Optional[float]
    currency: Optional[str]
    market_cap: Optional[float]
    pe_ratio: Optional[float]
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]
    revenue_ttm: Optional[float]       # trailing twelve months revenue
    price_change_1mo_pct: Optional[float]  # percentage price change over the period
    sector: Optional[str]
    industry: Optional[str]
    summary: Optional[str]             # business description from Yahoo Finance
    source: str = Field(
        default="Yahoo Finance via yfinance",
        description="Data source for citation grounding."
    )

def get_stock_snapshot(input: StockSnapshotInput) -> "StockSnapshotOutput":
    """
    Fetches a price and fundamentals snapshot for a US-listed equity.
    Returns a structured output with citation source attached.
    """
    ticker_obj = yf.Ticker(input.ticker)

    # info is a dict of company metadata and fundamentals.
    # We call it once and reuse it. Calling it multiple times
    # is wasteful — it makes a network request each time.

    info = ticker_obj.info

    # Price history over the requested period.
    # We use this to compute the percentage price change,
    # which is not reliably available in info.

    history = ticker_obj.history(period=input.period)

    # Coompute the price and change over the period, if we have history data.
    # history is a pandas DataFrame with a 'Close' column.
    # We take the first close (start of period) and last close (most recent).
    # If history is empty for any reason, we return None rather than crashing.

    if not history.empty and len(history) >= 2:
        start_price = history["Close"].iloc[0]
        end_price = history["Close"].iloc[-1]
        price_change_pct = ((end_price - start_price) / start_price) * 100
        price_change_pct = round(price_change_pct, 2)
    else:
        price_change_pct = None

    # Build and return the validated output.
    # .get() on a dict returns None if the key is missing,
    # which is exactly what our Optional fields expect.

    return StockSnapshotOutput(
    ticker=input.ticker.upper(),
    company_name=info.get("longName"),
    current_price=info.get("currentPrice"),
    currency=info.get("currency"),
    market_cap=info.get("marketCap"),
    pe_ratio=info.get("trailingPE"),
    fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
    fifty_two_week_low=info.get("fiftyTwoWeekLow"),
    revenue_ttm=info.get("totalRevenue"),
    price_change_1mo_pct=price_change_pct,
    sector=info.get("sector"),
    industry=info.get("industry"),
    summary=info.get("longBusinessSummary"),
    source="Yahoo Finance via yfinance"
)

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()

    # Test with a single ticker before wiring into the agent.
    # If this works cleanly, the tool is ready.
    test_input = StockSnapshotInput(ticker="AAPL", period="1mo")
    result = get_stock_snapshot(test_input)

    # .model_dump() converts the Pydantic model to a plain dict.
    # json.dumps with indent=2 makes it readable in the terminal.
    print(json.dumps(result.model_dump(), indent=2))
