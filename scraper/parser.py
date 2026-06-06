# scraper/parser.py
# Reads raw HTML from a DTU result page and extracts all result entries.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_results(html: str, year_label: str = "unknown") -> list[dict]:
    """
    Parses one DTU result page and returns a list of result entries.

    Each entry has:
        - session   : Exam session e.g. "Nov-25(O-25)"
        - title     : Result title e.g. "IMS(ECO) III Sem"
        - number    : Notification number e.g. "1946"
        - date      : Result date e.g. "20/05/2026"
        - links     : List of result PDF/page URLs
        - year_page : Which page this came from e.g. "2024"
        - scraped_at: When we scraped it
    """
    if not html:
        logger.error("Empty HTML passed to parser.")
        return []

    soup = BeautifulSoup(html, "lxml")

    # Find the main results table
    table = soup.find("table", {"id": "AutoNumber1"})

    if not table:
        logger.error(f"Results table not found on page: {year_label}")
        return []

    rows = table.find_all("tr")
    logger.info(f"[{year_label}] Found {len(rows)} rows in table.")

    entries = []
    current_session = "-------"

    for row in rows:
        cells = row.find_all("td")

        # We expect 4 columns: EXAM | DETAILS | NO. | DATE
        if len(cells) < 2:
            continue

        # --- Column 0: Session ---
        session_text = cells[0].get_text(strip=True)

        # --- Column 1: Details/Title ---
        detail_cell = cells[1]
        detail_text = detail_cell.get_text(separator=" ", strip=True)

        # --- Column 2: Notification Number (if exists) ---
        number_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""

        # --- Column 3: Date (if exists) ---
        date_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        # Skip header rows and empty rows
        if not detail_text or detail_text.upper() in ["DETAILS", "EXAM.", "EXAM"]:
            continue

        # Update session tracker
        if session_text and not all(c == '-' for c in session_text) and session_text.upper() != "EXAM.":
            current_session = session_text

        # Extract all links from the detail cell
        links = []
        for a_tag in detail_cell.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("http"):
                links.append(href)
            elif href:
                links.append(f"https://exam.dtu.ac.in/{href}")

        entry = {
            "session":    current_session,
            "title":      detail_text,
            "number":     number_text,
            "date":       date_text,
            "links":      links,
            "link_count": len(links),
            "year_page":  year_label,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        entries.append(entry)

    logger.info(f"[{year_label}] Extracted {len(entries)} entries.")
    return entries


def parse_all_pages(pages: dict[str, str]) -> list[dict]:
    """
    Parses multiple fetched pages and combines all results.

    Args:
        pages: Dictionary of { year_label: html_content }

    Returns:
        Combined list of all result entries across all pages.
    """
    all_entries = []

    for label, html in pages.items():
        entries = parse_results(html, year_label=label)
        all_entries.extend(entries)

    logger.info(f"Total entries across all pages: {len(all_entries)}")
    return all_entries


if __name__ == "__main__":
    from scraper.fetcher import fetch_page
    from config.settings import DTU_RESULT_PAGES

    # Test with just the current page first
    html = fetch_page(DTU_RESULT_PAGES["current"])

    if html:
        results = parse_results(html, year_label="current")

        print(f"\n{'='*60}")
        print(f"  SAMPLE — First 5 entries")
        print(f"{'='*60}\n")

        for entry in results[:5]:
            print(f"  Session : {entry['session']}")
            print(f"  Title   : {entry['title']}")
            print(f"  Number  : {entry['number']}")
            print(f"  Date    : {entry['date']}")
            print(f"  Links   : {entry['link_count']}")
            print()

        print(f"  Total entries: {len(results)}")