# scraper/runner.py
# The main controller for our scraper.
# Fetches all year pages, parses them, removes duplicates, saves to CSV.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd
from datetime import datetime
from config.settings import DATA_DIR, DTU_RESULT_PAGES
from scraper.fetcher import fetch_page
from scraper.parser import parse_results

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)


def scrape_all_years(delay: float = 2.0) -> list[dict]:
    """
    Scrapes all DTU result pages year by year.
    Returns combined list of all entries.
    """
    import time

    all_entries = []
    total_pages = len(DTU_RESULT_PAGES)

    logger.info(f"Starting scrape of {total_pages} pages...")
    print(f"\n{'='*60}")
    print(f"  DTU Academic Intelligence — Full Scrape")
    print(f"{'='*60}\n")

    for i, (label, url) in enumerate(DTU_RESULT_PAGES.items(), 1):

        # Skip the "all" page — it duplicates everything
        if label == "all":
            logger.info("Skipping 'all' page to avoid duplicates.")
            continue

        print(f"[{i}/{total_pages}] Scraping: {label} — {url}")

        html = fetch_page(url)

        if not html:
            print(f"  ⚠️  Could not fetch {label}. Skipping.")
            continue

        entries = parse_results(html, year_label=label)
        all_entries.extend(entries)
        print(f"  ✅ Extracted {len(entries)} entries from {label}")

        if i < total_pages:
            print(f"  ⏳ Waiting {delay}s before next request...")
            time.sleep(delay)

    print(f"\n✅ Scrape complete. Total raw entries: {len(all_entries)}")
    return all_entries


def remove_duplicates(entries: list[dict]) -> list[dict]:
    """
    Removes duplicate entries based on title + number + date combination.
    The same result can appear on both 'current' and a year-specific page.
    """
    seen = set()
    unique = []

    for entry in entries:
        # Create a unique key from the fields that identify a result
        key = (
            entry["title"].strip().lower(),
            entry["number"].strip().lower(),
            entry["date"].strip()
        )

        if key not in seen:
            seen.add(key)
            unique.append(entry)

    removed = len(entries) - len(unique)
    logger.info(f"Removed {removed} duplicates. Unique entries: {len(unique)}")
    return unique


def save_to_csv(entries: list[dict]) -> str:
    """
    Saves the result entries to a timestamped CSV file.

    Returns:
        The path to the saved CSV file.
    """
    if not entries:
        logger.error("No entries to save.")
        return ""

    # Make sure the data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Convert list of dicts to a pandas DataFrame
    # A DataFrame is like a spreadsheet in Python
    df = pd.DataFrame(entries)

    # Convert the links list to a string so it saves cleanly in CSV
    df["links"] = df["links"].apply(lambda x: " | ".join(x) if x else "")

    # Reorder columns for readability
    column_order = [
        "session", "title", "number", "date",
        "link_count", "links", "year_page", "scraped_at"
    ]
    df = df[column_order]

    # Sort by date descending (newest first)
    # We use errors="coerce" to handle any malformed dates gracefully
    df["date_parsed"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    df = df.sort_values("date_parsed", ascending=False)
    df = df.drop(columns=["date_parsed"])

    # Create a timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dtu_results_{timestamp}.csv"
    filepath = os.path.join(DATA_DIR, filename)

    # Save to CSV
    df.to_csv(filepath, index=False, encoding="utf-8-sig")

    logger.info(f"Saved {len(df)} entries to: {filepath}")
    return filepath


def print_summary(entries: list[dict]) -> None:
    """
    Prints a clean summary of what was scraped.
    """
    if not entries:
        return

    df = pd.DataFrame(entries)

    print(f"\n{'='*60}")
    print(f"  SCRAPE SUMMARY")
    print(f"{'='*60}")
    print(f"  Total entries      : {len(df)}")
    print(f"  Unique sessions    : {df['session'].nunique()}")
    print(f"  Date range         : {df['date'].min()} → {df['date'].max()}")
    print(f"  Pages scraped      : {df['year_page'].nunique()}")
    print(f"\n  Entries per page:")
    for page, count in df['year_page'].value_counts().items():
        print(f"    {page:<15} : {count} entries")

    print(f"\n  Top 5 sessions by entry count:")
    for session, count in df['session'].value_counts().head(5).items():
        print(f"    {session:<20} : {count} entries")


if __name__ == "__main__":

    # Step 1: Scrape all pages
    all_entries = scrape_all_years(delay=2.0)

    # Step 2: Remove duplicates
    unique_entries = remove_duplicates(all_entries)

    # Step 3: Print summary
    print_summary(unique_entries)

    # Step 4: Save to CSV
    filepath = save_to_csv(unique_entries)

    if filepath:
        print(f"\n✅ Data saved to: {filepath}")
        print(f"   Open it in Excel or VS Code to inspect.")
    else:
        print("\n❌ Failed to save data.")