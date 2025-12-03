"""
Part 1: Data Acquisition & Normalization - Main Script

This script orchestrates the entire Part 1 process:
1. Scrape books from Project Gutenberg
2. Scrape documents from Library of Congress
3. Normalize both into JSON datasets

Run this script to complete Part 1 of the project.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from gutenberg_scraper import GutenbergScraper
from loc_scraper_improved import LoCScraperImproved
from normalizer import DataNormalizer


def main():
    """
    Main function to run Part 1: Data Acquisition & Normalization.
    """
    print("=" * 70)
    print("ML Evals Engineer - Lincoln Project")
    print("Part 1: Data Acquisition & Normalization")
    print("=" * 70)
    
    # Step 1: Scrape Project Gutenberg books
    print("\n" + "=" * 70)
    print("STEP 1: Scraping Project Gutenberg Books")
    print("=" * 70)
    
    gutenberg_scraper = GutenbergScraper()
    gutenberg_book_ids = ["6812", "6811", "12801", "14004", "18379"]
    gutenberg_books = gutenberg_scraper.scrape_all_books(gutenberg_book_ids)
    
    print(f"\n[OK] Scraped {len(gutenberg_books)} out of {len(gutenberg_book_ids)} books")
    
    # Step 2: Scrape Library of Congress documents
    print("\n" + "=" * 70)
    print("STEP 2: Scraping Library of Congress Documents")
    print("=" * 70)
    
    loc_scraper = LoCScraperImproved()
    loc_urls = [
        "https://www.loc.gov/item/mal0440500/",  # Election night 1860
        "https://www.loc.gov/resource/mal.0882800",  # Fort Sumter Decision
        "https://www.loc.gov/exhibits/gettysburg-address/ext/trans-nicolay-copy.html",  # Gettysburg Address
        "https://www.loc.gov/resource/mal.4361300",  # Second Inaugural Address
        "https://www.loc.gov/resource/mal.4361800/",  # Last Public Address
    ]
    loc_documents = loc_scraper.scrape_all_documents(loc_urls)
    
    print(f"\n[OK] Scraped {len(loc_documents)} out of {len(loc_urls)} documents")
    
    # Step 3: Normalize datasets
    print("\n" + "=" * 70)
    print("STEP 3: Normalizing Datasets")
    print("=" * 70)
    
    normalizer = DataNormalizer()
    
    # Normalize Gutenberg books
    gutenberg_dataset = normalizer.create_gutenberg_dataset(gutenberg_books)
    normalizer.save_dataset(gutenberg_dataset, "gutenberg_dataset.json")
    
    # Normalize LoC documents
    loc_dataset = normalizer.create_loc_dataset(loc_documents)
    normalizer.save_dataset(loc_dataset, "loc_dataset.json")
    
    # Summary
    print("\n" + "=" * 70)
    print("PART 1 COMPLETE - Summary")
    print("=" * 70)
    print(f"[OK] Gutenberg books scraped: {len(gutenberg_books)}/{len(gutenberg_book_ids)}")
    print(f"[OK] LoC documents scraped: {len(loc_documents)}/{len(loc_urls)}")
    print(f"[OK] Normalized datasets created:")
    print(f"    - data/normalized/gutenberg_dataset.json")
    print(f"    - data/normalized/loc_dataset.json")
    print("\nNext step: Part 2 - Event Extraction")
    print("=" * 70)


if __name__ == "__main__":
    main()

