import os
import json
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Add project root to path so agent imports resolve correctly.
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import run_research_agent

TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA",
    "JPM", "BAC", "BRK-B",
    "UNH", "JNJ",
    "XOM", "CAT",
    "WMT", "COST",
    "TSM", "ASML",
    "PLTR", "ARM",
]

# Seconds to wait between tickers.
# Gives the API breathing room and avoids rate limit cascades.
SLEEP_BETWEEN_TICKERS = 10

# Output directory for pre-generated reports.
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "outputs"
)

def save_report(ticker: str, report: str) -> str:
    """Saves a report as JSON to the outputs directory. Returns the file path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    payload = {
        "ticker": ticker,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": report,
    }

    filename = f"{ticker.lower().replace('-', '_')}_report.json"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2)

    return filepath

def run_pipeline(tickers: list[str] = None) -> None:
    """
    Runs the research agent on each ticker and saves reports to outputs/.
    Pass a subset of tickers to run a partial pipeline.
    """
    target_tickers = tickers or TICKERS
    total = len(target_tickers)

    print(f"\n{'='*60}")
    print(f"Pre-generation pipeline starting.")
    print(f"Tickers: {total}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Sleep between tickers: {SLEEP_BETWEEN_TICKERS}s")
    print(f"{'='*60}\n")

    results = {
        "success": [],
        "failed": [],
    }
    for i, ticker in enumerate(target_tickers, 1):
        print(f"\n[{i}/{total}] Starting {ticker}...")
        start_time = time.time()

        try:
            report = run_research_agent(ticker)
            filepath = save_report(ticker, report)
            elapsed = round(time.time() - start_time, 1)

            print(f"[{i}/{total}] {ticker} complete. "
                  f"Length: {len(report)} chars. "
                  f"Time: {elapsed}s. "
                  f"Saved: {filepath}")

            results["success"].append({
                "ticker": ticker,
                "elapsed_seconds": elapsed,
                "report_length": len(report),
                "filepath": filepath,
            })

        except Exception as e:
            elapsed = round(time.time() - start_time, 1)
            print(f"[{i}/{total}] {ticker} FAILED after {elapsed}s: {e}")
            results["failed"].append({
                "ticker": ticker,
                "error": str(e),
                "elapsed_seconds": elapsed,
            })

        # Sleep between tickers except after the last one.
        if i < total:
            print(f"Sleeping {SLEEP_BETWEEN_TICKERS}s before next ticker...")
            time.sleep(SLEEP_BETWEEN_TICKERS)

    # Print summary.
    print(f"\n{'='*60}")
    print(f"Pipeline complete.")
    print(f"Success: {len(results['success'])}/{total}")
    print(f"Failed:  {len(results['failed'])}/{total}")

    if results["failed"]:
        print("\nFailed tickers:")
        for item in results["failed"]:
            print(f"  {item['ticker']}: {item['error']}")

    # Save the pipeline run log.
    log_path = os.path.join(OUTPUT_DIR, "pipeline_log.json")
    with open(log_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nRun log saved to: {log_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    # To run a single ticker for testing:
    # To run the full 20:
    # run_pipeline()

    # Start with a single ticker to confirm the pipeline works
    # before committing to the full 20-ticker run.
    run_pipeline()
