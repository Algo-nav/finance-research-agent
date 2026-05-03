import os
from typing import Optional
from pydantic import BaseModel, Field
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

class TavilySearchInput(BaseModel):
    """Input schema for the Tavily web search tool."""
    query: str = Field(
        description="The search query. Be specific. Example: 'AAPL Apple earnings Q2 2026 analyst reaction'"
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of results to return. Defaults to 5."
    )
    days: int = Field(
        default=30,
        description="Restrict results to content published within this many days. Defaults to 30."
    )

class SearchResult(BaseModel):
    """A single search result with citation data."""
    title: str
    url: str
    content: str        # pre-extracted page snippet from Tavily
    score: float        # Tavily relevance score, 0-1
    published_date: Optional[str]
    source: str = "Tavily Web Search"

class TavilySearchOutput(BaseModel):
    """Structured output for the Tavily web search tool."""
    query: str
    results: list[SearchResult]
    source: str = "Tavily Web Search"

def search_web(input: TavilySearchInput) -> TavilySearchOutput:
    """
    Runs a web search via Tavily and returns structured, citation-ready results.
    Each result includes a URL, content snippet, and relevance score.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not found in environment. Check your .env file.")

    client = TavilyClient(api_key=api_key)

    try:
        response = client.search(
            query=input.query,
            max_results=input.max_results,
            days=input.days,
            include_answer=False,   # we want raw results, not Tavily's own summary
            search_depth="advanced" # advanced uses more credits but returns better content
        )
    except Exception as e:
        # Return empty results rather than crashing the agent loop.
        print(f"Warning: Tavily search failed for query '{input.query}': {e}")
        return TavilySearchOutput(query=input.query, results=[])

    results = []
    for item in response.get("results", []):
        # Skip results with no URL — they cannot be used as citations.
        if not item.get("url"):
            continue

        results.append(SearchResult(
            title=item.get("title", "No title"),
            url=item["url"],
            # content is the pre-extracted snippet. Truncate at 500 chars
            # to keep the agent context manageable. Full page is at the URL.
            content=item.get("content", "")[:500],
            score=item.get("score", 0.0),
            published_date=item.get("published_date"),
        ))

    return TavilySearchOutput(
        query=input.query,
        results=results,
    )

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_input = TavilySearchInput(
        query="Apple AAPL earnings Q2 2026 analyst reaction",
        max_results=5,
        days=30
    )
    result = search_web(test_input)

    print(f"Query: {result.query}")
    print(f"Results: {len(result.results)}")
    print()

    for i, item in enumerate(result.results, 1):
        print(f"[{i}] {item.title}")
        print(f"    URL:   {item.url}")
        print(f"    Score: {item.score}")
        print(f"    Date:  {item.published_date}")
        print(f"    Snippet: {item.content[:150]}...")
        print()