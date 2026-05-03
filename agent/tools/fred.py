import os
from typing import Optional
from pydantic import BaseModel, Field
from fredapi import Fred
from dotenv import load_dotenv

# Load .env so os.getenv() finds the key when running this file directly
# When imported by the agent, load_dotenv() will have already been called
# at the top level. Calling it again here is harmless — it is idempotent.
load_dotenv()

# The five macro indicators we want to track for v1.
# Defined as a module-level constant so we can reuse it later.
MACRO_SERIES = {
    "FEDFUNDS": "Federal Funds Rate (%)",
    "CPIAUCSL": "Consumer Price Index (All Urban Consumers)",
    "UNRATE":   "Unemployment Rate (%)",
    "T10Y2Y":   "10Y-2Y Treasury Spread (bps)",
    "SP500":    "S&P 500 Index Level",
}

class MacroSnapshotInput(BaseModel):
    """Input schema for the Macro Snapshot Tool."""
    lookback_months: int = Field(
        default=3,
        description="Number of months of history to fetch per series. Used to compute trend direction. Defaults to 3."
    )

class MacroIndicator(BaseModel):
    """A single macro indicator with its latest value and trend."""
    series_id: str
    label: str
    latest_value: Optional[float]
    latest_date: Optional[str]
    trend: Optional[str]   # "rising", "falling", or "flat"
    source: str = "FRED (Federal Reserve Bank of St. Louis)"

class MacroSnapshotOutput(BaseModel):
    """Structured output for the FRED macro snapshot tool."""
    indicators: list[MacroIndicator]
    source: str = "FRED (Federal Reserve Bank of St. Louis)"

def get_macro_snapshot(input: MacroSnapshotInput) -> MacroSnapshotOutput:
    """
    Fetches the latest values and short-term trend for five key macro indicators from FRED.
    Returns a structured output with citation source attached.
    """
    # Initialize the FRED client with the API key from the environment.
    # If the key is missing this raises a clean error immediately,
    # rather than failing silently on the first API call.
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY not found in environment. Check your .env file.")

    fred = Fred(api_key=api_key)

    indicators = []

    for series_id, label in MACRO_SERIES.items():
        try:
            # fetch the series as a pandas Series (date index, float values).
            # limit to recent observations to keep the call fast.
            series = fred.get_series(series_id)

            # Drop any NaN values at the tail — FRED sometimes has
            # unreleased future periods with null values.
            series = series.dropna()

            if series.empty:
                indicators.append(MacroIndicator(
                    series_id=series_id,
                    label=label,
                    latest_value=None,
                    latest_date=None,
                    trend=None,
                ))
                continue

            # Latest value and its date.
            latest_value = round(float(series.iloc[-1]), 4)
            latest_date = str(series.index[-1].date())

            # Trend: compare latest value to value ~3 months ago.
            # input.lookback_months is approximate — FRED series have
            # different release frequencies (monthly, weekly, daily).
            # We use a fixed lookback of N observations as a proxy.
            lookback = input.lookback_months * 4  # ~4 obs per month as safe default
            if len(series) >= lookback:
                older_value = float(series.iloc[-lookback])
                diff = latest_value - older_value
                if abs(diff) < 0.01:
                    trend = "flat"
                elif diff > 0:
                    trend = "rising"
                else:
                    trend = "falling"
            else:
                trend = None

            indicators.append(MacroIndicator(
                series_id=series_id,
                label=label,
                latest_value=latest_value,
                latest_date=latest_date,
                trend=trend,
            ))

        except Exception as e:
            # One failed series should not kill the entire macro snapshot.
            # Append a partial result and keep going.
            indicators.append(MacroIndicator(
                series_id=series_id,
                label=label,
                latest_value=None,
                latest_date=None,
                trend=None,
            ))
            print(f"Warning: failed to fetch {series_id}: {e}")

    return MacroSnapshotOutput(indicators=indicators)

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()  # ensure .env is loaded when running this file directly

    test_input = MacroSnapshotInput(lookback_months=3)
    result = get_macro_snapshot(test_input)

    for indicator in result.indicators:
        print(f"{indicator.series_id} | {indicator.label}")
        print(f"  Latest: {indicator.latest_value} ({indicator.latest_date})")
        print(f"  Trend:  {indicator.trend}")
        print(f"  Source: {indicator.source}")
        print()

