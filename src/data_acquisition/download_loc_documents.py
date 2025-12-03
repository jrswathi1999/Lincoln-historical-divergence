"""
Script to download LoC documents using the improved scraper.

This script uses the improved LoC scraper to download actual PDF/text files
from Library of Congress pages.
"""

import sys
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.data_acquisition.loc_scraper_improved import LoCScraperImproved

# Note: This script now uses Selenium to handle JavaScript-rendered pages
# Make sure Chrome/Chromium is installed and chromedriver is in PATH


def main():
    """
    Download LoC documents using improved scraper.
    """
    print("=" * 70)
    print("Improved LoC Document Downloader")
    print("=" * 70)
    
    # Initialize improved scraper
    scraper = LoCScraperImproved()
    
    # The 5 LoC URLs we need
    loc_urls = [
        "https://www.loc.gov/item/mal0440500/",  # Election night 1860
        "https://www.loc.gov/resource/mal.0882800",  # Fort Sumter Decision
        "https://www.loc.gov/exhibits/gettysburg-address/ext/trans-nicolay-copy.html",  # Gettysburg Address
        "https://www.loc.gov/resource/mal.4361300",  # Second Inaugural Address
        "https://www.loc.gov/resource/mal.4361800/",  # Last Public Address
    ]
    
    print(f"\nDownloading {len(loc_urls)} documents...")
    print("This may take a few minutes as we download PDFs/text files.\n")
    
    # Scrape documents
    documents = scraper.scrape_all_documents(loc_urls)
    
    print(f"\n{'='*70}")
    print(f"Download Summary")
    print(f"{'='*70}")
    print(f"Successfully downloaded: {len(documents)}/{len(loc_urls)} documents")
    
    # Show what we got
    for doc in documents:
        print(f"\n  - {doc['title'][:60]}...")
        print(f"    Format: {doc.get('file_format', 'unknown')}")
        print(f"    Content length: {len(doc.get('content', '')):,} characters")
        if doc.get('date'):
            print(f"    Date: {doc['date']}")
    
    print(f"\n{'='*70}")
    print("COMPLETE!")
    print(f"{'='*70}")
    print(f"Documents saved to: data/raw/loc/")
    print(f"\nNext step: Run normalize_loc_documents.py to normalize the data")


if __name__ == "__main__":
    main()

