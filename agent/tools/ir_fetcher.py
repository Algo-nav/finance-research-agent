import os
import requests
from typing import Optional
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Maximum characters of page text to return.
# Beyond this, the content adds noise without adding signal.
# The agent has the URL if it needs more.
MAX_CONTENT_LENGTH = 8000

class IRFetchInput(BaseModel):
    """Input schema for the IR page fetcher tool."""
    url: str = Field(
        description="The full URL of the investor relations page, earnings transcript, or press release to fetch."
    )
    max_length: int = Field(
        default=MAX_CONTENT_LENGTH,
        description="Maximum characters of cleaned text to return. Defaults to 8000."
    )

class IRFetchOutput(BaseModel):
    """Structured output for the IR page fetcher tool."""
    url: str
    title: Optional[str]
    content: str            # cleaned text, HTML stripped
    content_length: int     # actual length returned
    truncated: bool         # whether content was cut at max_length
    source: str             # always the URL itself - this IS the citation

def fetch_ir_page(input: IRFetchInput) -> IRFetchOutput:
    """
    Fetches a web page and returns clean text with HTML stripped.
    Used for earnings transcripts, IR pages, and press releases.
    """
    edgar_user_agent = os.getenv("EDGAR_USER_AGENT", "")
    is_sec_url = "sec.gov" in input.url

    headers = {
        "User-Agent": edgar_user_agent if is_sec_url else (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(
            input.url,
            headers=headers,
            timeout=15,     # IR pages are sometimes slow
            allow_redirects=True
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Return a partial result rather than crashing the agent loop.
        return IRFetchOutput(
            url=input.url,
            title=None,
            content=f"Failed to fetch page: {e}",
            content_length=0,
            truncated=False,
            source=input.url
        )

    # Parse HTML with BeautifulSoup.
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract page title if present.
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Remove script and style tags entirely.
    # Their text content is noise — JS code and CSS rules.
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Extract clean text. get_text() concatenates all remaining text nodes.
    # separator="\n" preserves paragraph breaks.
    # strip=True removes leading/trailing whitespace from each chunk.
    raw_text = soup.get_text(separator="\n", strip=True)

    # Collapse excessive blank lines.
    # IR pages often have many consecutive empty lines after tag removal.
    lines = [line for line in raw_text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    # Truncate if needed.
    truncated = len(clean_text) > input.max_length
    if truncated:
        clean_text = clean_text[:input.max_length]

    return IRFetchOutput(
        url=input.url,
        title=title,
        content=clean_text,
        content_length=len(clean_text),
        truncated=truncated,
        source=input.url     # the URL itself is the citation
    )

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Test with a real EDGAR filing URL from the SEC EDGAR tool output.
    # This is AAPL's most recent 10-Q.
    test_input = IRFetchInput(
    url="https://finance.yahoo.com/markets/stocks/articles/wall-street-splits-apple-q2-162103245.html",
    max_length=2000
    )
    result = fetch_ir_page(test_input)

    print(f"URL:      {result.url}")
    print(f"Title:    {result.title}")
    print(f"Length:   {result.content_length} chars")
    print(f"Truncated: {result.truncated}")
    print(f"Source:   {result.source}")
    print()
    print("--- Content Preview ---")
    print(result.content[:1000])