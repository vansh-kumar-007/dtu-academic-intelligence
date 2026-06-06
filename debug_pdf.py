# debug_pdf.py — temporary diagnostic file
# Shows us exactly what pdfplumber sees inside the PDF table rows

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import requests
import pdfplumber
import io

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

url = "https://exam.dtu.ac.in/result_2026/O25_BTECH_III_R5_ME_1943.pdf"

print("Downloading PDF...")
response = requests.get(url, headers=HEADERS, timeout=30)
pdf_bytes = response.content
print(f"Downloaded: {len(pdf_bytes)} bytes\n")

with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")

    # Look at first 2 pages only
    for page_num in range(min(2, len(pdf.pages))):
        page = pdf.pages[page_num]
        tables = page.extract_tables()

        print(f"{'='*60}")
        print(f"PAGE {page_num + 1} — {len(tables)} tables found")
        print(f"{'='*60}")

        for t_idx, table in enumerate(tables):
            print(f"\n  Table {t_idx + 1} — {len(table)} rows")
            print(f"  First 8 rows:")
            for r_idx, row in enumerate(table[:8]):
                print(f"    Row {r_idx}: {row}")