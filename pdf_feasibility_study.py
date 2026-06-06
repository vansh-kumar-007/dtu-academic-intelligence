# pdf_feasibility_study.py
# Investigates whether DTU result PDFs contain student-level data.
# This is a ONE-TIME investigation script. Not part of the main app.

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import requests
import pdfplumber
import fitz  # PyMuPDF
import pandas as pd
import io
from config.settings import DATA_DIR

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def download_pdf_to_memory(url: str) -> bytes | None:
    """Downloads a PDF and returns it as bytes (no disk write needed)."""
    try:
        print(f"  Downloading: {url}")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        print(f"  Downloaded: {len(response.content)} bytes")
        return response.content
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return None


def analyze_with_pdfplumber(pdf_bytes: bytes, label: str) -> dict:
    """
    Analyzes a PDF using pdfplumber.
    Good at extracting text and tables from machine-readable PDFs.
    """
    result = {
        "tool": "pdfplumber",
        "label": label,
        "pages": 0,
        "has_text": False,
        "has_tables": False,
        "table_count": 0,
        "sample_text": "",
        "sample_tables": [],
        "contains_roll_number": False,
        "contains_name": False,
        "contains_sgpa": False,
        "contains_cgpa": False,
        "contains_grades": False,
    }

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            result["pages"] = len(pdf.pages)

            full_text = ""
            all_tables = []

            for page in pdf.pages:
                # Extract raw text
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

                # Extract tables
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

            result["has_text"] = len(full_text.strip()) > 0
            result["has_tables"] = len(all_tables) > 0
            result["table_count"] = len(all_tables)
            result["sample_text"] = full_text[:1000] if full_text else ""

            # Store first table sample (first 5 rows)
            if all_tables:
                result["sample_tables"] = all_tables[0][:5]

            # Check for key academic data indicators
            text_lower = full_text.lower()
            result["contains_roll_number"] = any(
                kw in text_lower for kw in ["roll", "enrollment", "rollno", "roll no", "2k", "2K"]
            )
            result["contains_name"] = "name" in text_lower
            result["contains_sgpa"] = "sgpa" in text_lower
            result["contains_cgpa"] = "cgpa" in text_lower
            result["contains_grades"] = any(
                kw in text_lower for kw in ["grade", "marks", "credits"]
            )

    except Exception as e:
        result["error"] = str(e)

    return result


def analyze_with_pymupdf(pdf_bytes: bytes, label: str) -> dict:
    """
    Analyzes a PDF using PyMuPDF.
    Good backup tool — handles more PDF types.
    """
    result = {
        "tool": "pymupdf",
        "label": label,
        "pages": 0,
        "has_text": False,
        "is_scanned": False,
        "sample_text": "",
    }

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result["pages"] = len(doc)

        full_text = ""
        for page in doc:
            full_text += page.get_text()

        result["has_text"] = len(full_text.strip()) > 0
        result["sample_text"] = full_text[:500] if full_text else ""

        # If no text found, PDF is likely scanned (image-based)
        result["is_scanned"] = not result["has_text"]

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def run_feasibility_study():
    """
    Main function — loads our scraped CSV, picks sample PDFs,
    downloads and analyzes them, and prints a full report.
    """

    print("\n" + "="*65)
    print("  DTU PDF FEASIBILITY STUDY")
    print("  Investigating student-level data availability in PDFs")
    print("="*65 + "\n")

    # Load the most recent CSV from our data folder
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    if not csv_files:
        print("❌ No CSV files found. Run scraper/runner.py first.")
        return

    latest_csv = sorted(csv_files)[-1]
    csv_path = os.path.join(DATA_DIR, latest_csv)
    df = pd.read_csv(csv_path)

    print(f"✅ Loaded: {latest_csv}")
    print(f"   Total entries: {len(df)}")

    # Filter to only entries that have PDF links
    df_with_links = df[df["links"].notna() & (df["links"] != "")]
    print(f"   Entries with links: {len(df_with_links)}\n")

    # Pick a diverse sample of PDFs to test
    # We want B.Tech, M.Tech, Ph.D results to see if structure differs
    sample_filters = {
        "B.Tech result":    df_with_links[df_with_links["title"].str.contains("B.Tech", case=False, na=False)],
        "M.Tech result":    df_with_links[df_with_links["title"].str.contains("M.Tech", case=False, na=False)],
        "Ph.D result":      df_with_links[df_with_links["title"].str.contains("Ph.D", case=False, na=False)],
        "Recent Nov-25":    df_with_links[df_with_links["session"].str.contains("Nov-25", case=False, na=False)],
    }

    pdfs_to_test = []
    for category, subset in sample_filters.items():
        if not subset.empty:
            row = subset.iloc[0]
            url = row["links"].split(" | ")[0]
            pdfs_to_test.append({
                "category": category,
                "title": row["title"],
                "url": url
            })

    print(f"📋 Selected {len(pdfs_to_test)} PDFs for analysis:\n")
    for p in pdfs_to_test:
        print(f"  [{p['category']}] {p['title']}")
        print(f"   URL: {p['url']}\n")

    # Analyze each PDF
    print("\n" + "="*65)
    print("  ANALYSIS RESULTS")
    print("="*65)

    findings = []

    for pdf_info in pdfs_to_test:
        print(f"\n📄 Analyzing: {pdf_info['category']}")
        print(f"   Title: {pdf_info['title']}")

        pdf_bytes = download_pdf_to_memory(pdf_info["url"])
        if not pdf_bytes:
            continue

        # Run both tools
        plumber_result = analyze_with_pdfplumber(pdf_bytes, pdf_info["category"])
        pymupdf_result = analyze_with_pymupdf(pdf_bytes, pdf_info["category"])

        print(f"\n  --- pdfplumber results ---")
        print(f"  Pages       : {plumber_result['pages']}")
        print(f"  Has text    : {plumber_result['has_text']}")
        print(f"  Has tables  : {plumber_result['has_tables']}")
        print(f"  Table count : {plumber_result['table_count']}")
        print(f"  Roll number : {plumber_result['contains_roll_number']}")
        print(f"  Names       : {plumber_result['contains_name']}")
        print(f"  SGPA        : {plumber_result['contains_sgpa']}")
        print(f"  CGPA        : {plumber_result['contains_cgpa']}")
        print(f"  Grades      : {plumber_result['contains_grades']}")

        print(f"\n  --- PyMuPDF results ---")
        print(f"  Is scanned  : {pymupdf_result['is_scanned']}")
        print(f"  Has text    : {pymupdf_result['has_text']}")

        if plumber_result.get("sample_text"):
            print(f"\n  --- Sample text (first 300 chars) ---")
            print(f"  {plumber_result['sample_text'][:300]}")

        if plumber_result.get("sample_tables"):
            print(f"\n  --- First table (first 3 rows) ---")
            for row in plumber_result["sample_tables"][:3]:
                print(f"  {row}")

        findings.append({
            "category": pdf_info["category"],
            "title": pdf_info["title"],
            "pages": plumber_result["pages"],
            "has_text": plumber_result["has_text"],
            "has_tables": plumber_result["has_tables"],
            "is_scanned": pymupdf_result["is_scanned"],
            "has_roll_number": plumber_result["contains_roll_number"],
            "has_sgpa": plumber_result["contains_sgpa"],
            "has_cgpa": plumber_result["contains_cgpa"],
            "has_grades": plumber_result["contains_grades"],
        })

        print("\n" + "-"*65)

    # Final verdict
    print("\n" + "="*65)
    print("  FINAL VERDICT")
    print("="*65)

    any_has_student_data = any(
        f["has_roll_number"] or f["has_sgpa"] or f["has_grades"]
        for f in findings
    )
    any_scanned = any(f["is_scanned"] for f in findings)
    any_has_tables = any(f["has_tables"] for f in findings)

    if any_has_student_data:
        print("\n  ✅ STUDENT DATA FOUND IN PDFs")
        print("  → Student profiles are FEASIBLE")
        print("  → We can extract: roll numbers, names, grades, SGPA/CGPA")
        print("  → Next step: Build the PDF parser pipeline")
    elif any_scanned:
        print("\n  ⚠️  PDFs ARE SCANNED IMAGES")
        print("  → Standard text extraction won't work")
        print("  → OCR required (Tesseract / EasyOCR)")
        print("  → Student profiles are possible but harder")
    else:
        print("\n  ❌ NO STUDENT-LEVEL DATA FOUND")
        print("  → PDFs may only contain aggregate results")
        print("  → We will pivot to result tracking only")

    print(f"\n  Tables found  : {any_has_tables}")
    print(f"  Scanned PDFs  : {any_scanned}")
    print(f"  Student data  : {any_has_student_data}")
    print()


if __name__ == "__main__":
    run_feasibility_study()