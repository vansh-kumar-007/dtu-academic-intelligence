# scraper/fetcher.py
# Downloads raw HTML from any DTU result page URL.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import logging
import time
from config.settings import DTU_RESULT_PAGES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_page(url: str) -> str | None:
    """
    Downloads a single page and returns its HTML.
    """
    try:
        logger.info(f"Fetching: {url}")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        logger.info(f"✅ Success — {len(response.text)} characters")
        return response.text

    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout: {url}")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection error: {url}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTP error {e}: {url}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error {e}: {url}")
        return None


def fetch_all_pages(delay: float = 2.0) -> dict[str, str]:
    """
    Fetches all DTU result pages defined in settings.
    Waits between requests to be respectful to the server.

    Args:
        delay: Seconds to wait between each request.

    Returns:
        Dictionary of { year_label: html_content }
    """
    results = {}

    for label, url in DTU_RESULT_PAGES.items():
        html = fetch_page(url)
        if html:
            results[label] = html
        else:
            logger.warning(f"Skipping {label} — could not fetch.")

        # Be polite — wait between requests
        # Hitting a server too fast can get you blocked
        logger.info(f"Waiting {delay} seconds before next request...")
        time.sleep(delay)

    logger.info(f"Fetched {len(results)} out of {len(DTU_RESULT_PAGES)} pages.")
    return results


if __name__ == "__main__":
    pages = fetch_all_pages()
    print(f"\n✅ Successfully fetched {len(pages)} pages:")
    for label in pages:
        print(f"  - {label}: {len(pages[label])} characters")