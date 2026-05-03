import os
import requests
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

FMP_BASE_URL = "https://financialmodelingprep.com/stable"

class FMPInput(BaseModel):
    """Input Schema for the FMP Fundamental Tool."""
    ticker: str = Field(
        description="The stock ticker symbol, e.g. AAPL, MSFT. Must be a US-listed equity."

    )
    news_limit: int = Field(
        default=5,
        description="Number of recent news items to fetch. Defaults to 5."
    )

class KeyRatios(BaseModel):
    """Core valuation and profitability ratios."""
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    debt_to_equity: Optional[float]
    return_on_equity: Optional[float]
    profit_margin: Optional[float]
    operating_margin: Optional[float]
    revenue_growth_yoy: Optional[float]
    eps_diluted: Optional[float]
    source: str = "Financial Modeling Prep"

class NewsItem(BaseModel):
    """A single news item with citation URL."""
    title: str
    url: str
    published_date: Optional[str]
    source: str = "Financial Modeling Prep (FMP)"

class EarningsEvent(BaseModel):
    """Next scheduled earnings event."""
    date: Optional[str]
    eps_estimated: Optional[float]
    revenue_estimated: Optional[float]
    source: str = "Financial Modeling Prep"

class FMPOutput(BaseModel):
    """Structured output for the FMP fundamentals tool."""
    ticker: str
    ratios: Optional[KeyRatios]
    recent_news: list[NewsItem]
    next_earnings: Optional[EarningsEvent]
    source: str = "Financial Modeling Prep"


def _get(endpoint: str, params: dict) -> dict | list | None:
    """
    Internal helper for FMP GET requests.
    Centralizes error handling so the main function stays clean.
    Returns parsed JSON or None on failure.
    """
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise ValueError("FMP_API_KEY not found in environment. Check your .env file.")

    params["apikey"] = api_key

    try:
        response = requests.get(
            f"{FMP_BASE_URL}/{endpoint}",
            params=params,
            timeout=10  # never hang the agent loop indefinitely
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Warning: FMP request failed for {endpoint}: {e}")
        return None
    
def get_fmp_fundamentals(input: FMPInput) -> FMPOutput:
    """
    Fetches key ratios, recent news, and next earnings date from FMP.
    Returns a structured output with citation sources attached.
    """
    ticker = input.ticker.upper()

    # --- Key Ratios ---
    # FMP returns a list, most recent entry is index 0.
    ratios_data = _get(f"ratios", params={"symbol": ticker})
    
    ratios = None

    if ratios_data and isinstance(ratios_data, list) and len(ratios_data) > 0:
        r = ratios_data[0]
        ratios = KeyRatios(
            pe_ratio=r.get("priceToEarningsRatio"),
            pb_ratio=r.get("priceToBookRatio"),
            debt_to_equity=r.get("debtToEquityRatio"),
            return_on_equity=r.get("returnOnEquityTTM"),
            profit_margin=r.get("netProfitMargin"),
            operating_margin=r.get("operatingProfitMargin"),
            revenue_growth_yoy=r.get("revenueGrowthTTM"),
            eps_diluted=r.get("netIncomePerShare"),
        )

    # --- Recent News ---
    news_data = _get(
    f"news/stock",
    params={"symbols": ticker, "limit": input.news_limit}
    )
    recent_news = []

    if news_data and isinstance(news_data, list):
        for item in news_data:
            # Skip items with no URL — they cannot be used as citations.
            if not item.get("url"):
                continue
            recent_news.append(NewsItem(
                title=item.get("title", "No title"),
                published_date=item.get("publishedDate"),
                url=item["url"],
            ))

    # --- Next Earnings ---
    earnings_data = _get(
        f"earnings",
        params={"symbol": ticker, "limit": 1}
    )
    next_earnings = None

    if earnings_data and isinstance(earnings_data, list) and len(earnings_data) > 0:
        e = earnings_data[0]
        next_earnings = EarningsEvent(
            date=e.get("date"),
            eps_estimated=e.get("estimatedEPS"),
            revenue_estimated=None,  # not in this endpoint, available in calendar endpoint
        )

    return FMPOutput(
        ticker=ticker,
        ratios=ratios,
        recent_news=recent_news,
        next_earnings=next_earnings,
    )

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()

    test_input = FMPInput(ticker="AAPL", news_limit=5)
    result = get_fmp_fundamentals(test_input)

    print(f"Ticker: {result.ticker}")
    print()

    print("--- Key Ratios ---")
    if result.ratios:
        print(json.dumps(result.ratios.model_dump(), indent=2))
    else:
        print("No ratios returned.")
    print()

    print("--- Recent News ---")
    if result.recent_news:
        for item in result.recent_news:
            print(f"  {item.published_date} | {item.title}")
            print(f"  URL: {item.url}")
            print()
    else:
        print("No news returned.")

    print("--- Next Earnings ---")
    if result.next_earnings:
        print(json.dumps(result.next_earnings.model_dump(), indent=2))
    else:
        print("No earnings data returned.")


