from agent.tools.yfinance_tool import get_stock_snapshot, StockSnapshotInput
from agent.tools.fred import get_macro_snapshot, MacroSnapshotInput
from agent.tools.fmp import get_fmp_fundamentals, FMPInput
from agent.tools.tavily_tool import search_web, TavilySearchInput
from agent.tools.sec_edgar import get_sec_filings, EDGARInput
from agent.tools.ir_fetcher import fetch_ir_page, IRFetchInput

# Central tool registry.
# Maps tool name (string Claude uses) to a tuple of:
# - the function to call
# - the Pydantic input model to validate arguments against
#
# When the agent receives a tool_use block from Claude,
# it looks up the tool name here, validates the arguments
# against the input model, and calls the function.

TOOL_REGISTRY = {
    "get_stock_snapshot": (get_stock_snapshot, StockSnapshotInput),
    "get_macro_snapshot": (get_macro_snapshot, MacroSnapshotInput),
    "get_fmp_fundamentals": (get_fmp_fundamentals, FMPInput),
    "search_web": (search_web, TavilySearchInput),
    "get_sec_filings": (get_sec_filings, EDGARInput),
    "fetch_ir_page": (fetch_ir_page, IRFetchInput),
}

# Expose tool names as a convenience for iteration.
TOOL_NAMES = list(TOOL_REGISTRY.keys())