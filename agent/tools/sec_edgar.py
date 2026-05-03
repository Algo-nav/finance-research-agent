import os
import requests
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

EDGAR_BASE_URL = "https://data.sec.gov"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
TICKER_TO_CIK_URL = "https://www.sec.gov/files/company_tickers.json"

class EDGARInput(BaseModel):
    """Input schema for the SEC EDGAR filings tool."""
    ticker: str = Field(
        description="The stock ticker symbol, e.g. AAPL, MSFT. Must be a US-listed equity."
    )
    filing_types: list[str] = Field(
        default=["10-K", "10-Q", "8-K"],
        description="List of SEC filing types to fetch. Defaults to 10-K, 10-Q, and 8-K."
    )
    max_filings: int = Field(
        default=5,
        description="Maximum number of recent filings to return per type. Defaults to 5."
    )

class SECFiling(BaseModel):
    """A single SEC filing with citation metadata."""
    ticker: str
    cik: str
    form_type: str
    filed_date: str
    description: Optional[str]
    url: str                    # direct link to filing on EDGAR
    source: str = "SEC EDGAR"

class EDGAROutput(BaseModel):
    """Structured output for the SEC EDGAR filings tool."""
    ticker: str
    cik: str
    filings: list[SECFiling]
    source: str = "SEC EDGAR"

def _get_headers() -> dict:
    """
    EDGAR requires a User-Agent header on every request.
    Without it, requests are blocked with a 403.
    """
    user_agent = os.getenv("EDGAR_USER_AGENT")
    if not user_agent:
        raise ValueError("EDGAR_USER_AGENT not found in environment. Check your .env file.")
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov"
    }

def _ticker_to_cik(ticker: str) -> str | None:
    """
    Converts a ticker symbol to an EDGAR CIK number.
    EDGAR maintains a public JSON file mapping all tickers to CIKs.
    CIK must be zero-padded to 10 digits for API calls.
    """
    try:
        response = requests.get(
            TICKER_TO_CIK_URL,
            headers={
                "User-Agent": os.getenv("EDGAR_USER_AGENT", ""),
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov"
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # The JSON is a dict of index -> {cik_str, ticker, title}.
        # We scan all entries for a matching ticker.
        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                # Zero-pad the CIK to 10 digits — EDGAR API requirement.
                return str(entry["cik_str"]).zfill(10)

        return None

    except Exception as e:
        print(f"Warning: CIK lookup failed for {ticker}: {e}")
        return None
    
def get_sec_filings(input: EDGARInput) -> EDGAROutput:
    """
    Fetches recent SEC filings for a ticker from EDGAR.
    Returns structured filing metadata with direct citation URLs.
    """
    ticker = input.ticker.upper()
    headers = _get_headers()

    # Step 1: resolve ticker to CIK.
    cik = _ticker_to_cik(ticker)
    if not cik:
        print(f"Warning: Could not resolve CIK for ticker {ticker}.")
        return EDGAROutput(ticker=ticker, cik="unknown", filings=[])

    # Step 2: fetch the company's submission history from EDGAR.
    # This endpoint returns metadata for all filings — no need to paginate
    # for our use case since we only want the most recent few.
    try:
        response = requests.get(
            f"{EDGAR_BASE_URL}/submissions/CIK{cik}.json",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Warning: EDGAR submissions fetch failed for {ticker}: {e}")
        return EDGAROutput(ticker=ticker, cik=cik, filings=[])
    
    # Step 3: extract recent filings matching our requested types.
    recent = data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])

    filings = []
    type_counts = {ft: 0 for ft in input.filing_types}

    for i, form in enumerate(forms):
        if form not in input.filing_types:
            continue
        if type_counts[form] >= input.max_filings:
            continue

        accession = accession_numbers[i].replace("-", "")
        primary_doc = descriptions[i] if i < len(descriptions) else ""

        # Build the direct EDGAR URL for this filing.
        url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession}/{primary_doc}"
        )

        filings.append(SECFiling(
            ticker=ticker,
            cik=cik,
            form_type=form,
            filed_date=dates[i],
            description=primary_doc,
            url=url,
        ))

        type_counts[form] += 1

    return EDGAROutput(ticker=ticker, cik=cik, filings=filings)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_input = EDGARInput(
        ticker="AAPL",
        filing_types=["10-K", "10-Q", "8-K"],
        max_filings=2
    )
    result = get_sec_filings(test_input)

    print(f"Ticker: {result.ticker}")
    print(f"CIK:    {result.cik}")
    print(f"Filings found: {len(result.filings)}")
    print()

    for filing in result.filings:
        print(f"  {filing.form_type} | Filed: {filing.filed_date}")
        print(f"  URL: {filing.url}")
        print()