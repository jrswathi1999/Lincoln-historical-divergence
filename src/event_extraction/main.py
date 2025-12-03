"""
Part 2: Event Extraction - Main Script

This script extracts information about 5 key events from all documents.
For each (document, event) pair, it uses LLM to extract:
- Claims about the event
- Temporal details (dates, times)
- Tone of the writing

Run this script to complete Part 2 of the project.
"""

import sys
import json
from pathlib import Path

# Add parent directories to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.event_extraction.config import KEY_EVENTS
from src.event_extraction.llm_extractor import LLMEventExtractor
from src.event_extraction.document_chunker import DocumentChunker


def load_datasets():
    """Load the normalized datasets from Part 1."""
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "normalized"
    
    # Load Gutenberg books
    gutenberg_path = data_dir / "gutenberg_dataset.json"
    with open(gutenberg_path, 'r', encoding='utf-8') as f:
        gutenberg_data = json.load(f)
    
    # Load LoC documents
    loc_path = data_dir / "loc_dataset.json"
    with open(loc_path, 'r', encoding='utf-8') as f:
        loc_data = json.load(f)
    
    return gutenberg_data, loc_data


def extract_author_from_title(title: str) -> str:
    """
    Extract author name from document title.
    For Gutenberg books, author is usually in the title.
    """
    # Try to extract author from common title patterns
    if "by" in title.lower():
        parts = title.split("by")
        if len(parts) > 1:
            author = parts[-1].strip()
            # Clean up author name
            author = author.split("|")[0].strip()  # Remove "| Project Gutenberg"
            return author
    return "Unknown Author"


def main():
    """
    Main function to run Part 2: Event Extraction.
    """
    print("=" * 70)
    print("ML Evals Engineer - Lincoln Project")
    print("Part 2: Event Extraction (PARALLEL MODE - 5x faster)")
    print("=" * 70)
    
    # Load datasets
    print("\n[STEP 1] Loading datasets...")
    gutenberg_data, loc_data = load_datasets()
    print(f"  Loaded {len(gutenberg_data)} Gutenberg books")
    print(f"  Loaded {len(loc_data)} LoC documents")
    
    # Initialize LLM extractor
    print("\n[STEP 2] Initializing LLM extractor...")
    extractor = LLMEventExtractor(model="gpt-4o-mini")
    
    if not extractor.client:
        print("\n[ERROR] LLM client not available!")
        print("  Please set OPENAI_API_KEY in a .env file:")
        print("  Create .env file with: OPENAI_API_KEY=your_key_here")
        return
    
    # Prepare output directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    output_dir = project_root / "data" / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "event_extractions.json"
    
    # Load existing results if resuming
    all_extractions = []
    processed_pairs = set()  # Track (document_id, event_id) pairs already processed
    
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                all_extractions = existing
                # Build set of already processed (document, event) pairs
                for ext in existing:
                    doc_id = ext.get('source_document', '')
                    event_id = ext.get('event', '')
                    if doc_id and event_id:
                        # Extract document ID from source_document (might be title)
                        # We'll use a simpler approach: track by checking if we have extractions
                        pass
                print(f"  Loaded {len(all_extractions)} existing extractions (will append new results)")
        except Exception as e:
            print(f"  Warning: Could not load existing results: {e}")
            all_extractions = []
    
    # Process each event
    print(f"\n[STEP 3] Extracting information for {len(KEY_EVENTS)} events...")
    
    for event in KEY_EVENTS:
        event_id = event['id']
        event_name = event['name']
        event_keywords = event['keywords']
        
        print(f"\n{'='*70}")
        print(f"Processing Event: {event_name}")
        print(f"{'='*70}")
        
        # Process Gutenberg books
        print(f"\n  Processing {len(gutenberg_data)} Gutenberg books...")
        for book in gutenberg_data:
            book_id = book['id']
            book_title = book['title']
            book_content = book.get('content', '')
            author = extract_author_from_title(book_title)
            
            if not book_content or len(book_content) < 100:
                print(f"    [SKIP] {book_id}: No content")
                continue
            
            print(f"    Processing: {book_title[:60]}...")
            try:
                # Use parallel processing for faster extraction
                extractions = extractor.extract_from_document_parallel(
                    book_content,
                    book_id,
                    book_title,
                    author,
                    event_id,
                    event_name,
                    event_keywords,
                    max_workers=3  # 3 workers for balanced speed and rate limit safety
                )
                
                all_extractions.extend(extractions)
                
                # Save incrementally after each document (so we don't lose progress)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_extractions, f, indent=2, ensure_ascii=False)
                
                if extractions:
                    print(f"      Found {len(extractions)} relevant sections")
                else:
                    print(f"      No relevant sections found (keywords: {', '.join(event_keywords[:3])}...)")
            except KeyboardInterrupt:
                print(f"\n[INTERRUPTED] Stopping extraction...")
                # Save what we have so far
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_extractions, f, indent=2, ensure_ascii=False)
                print(f"  Progress saved to: {output_file}")
                raise
            except Exception as e:
                print(f"      [ERROR] {type(e).__name__}: {str(e)[:50]}")
                continue
        
        # Process LoC documents
        print(f"\n  Processing {len(loc_data)} LoC documents...")
        for doc in loc_data:
            doc_id = doc['id']
            doc_title = doc['title']
            doc_content = doc.get('content', '')
            author = "Abraham Lincoln"  # LoC documents are by Lincoln
            
            if not doc_content or len(doc_content) < 50:
                print(f"    [SKIP] {doc_id}: No content")
                continue
            
            print(f"    Processing: {doc_title[:60]}...")
            try:
                # Use parallel processing for faster extraction
                extractions = extractor.extract_from_document_parallel(
                    doc_content,
                    doc_id,
                    doc_title,
                    author,
                    event_id,
                    event_name,
                    event_keywords,
                    max_workers=3  # 3 workers for balanced speed and rate limit safety
                )
                
                all_extractions.extend(extractions)
                
                # Save incrementally after each document (so we don't lose progress)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_extractions, f, indent=2, ensure_ascii=False)
                
                if extractions:
                    print(f"      Found {len(extractions)} relevant sections")
                else:
                    print(f"      No relevant sections found")
            except KeyboardInterrupt:
                print(f"\n[INTERRUPTED] Stopping extraction...")
                # Save what we have so far
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_extractions, f, indent=2, ensure_ascii=False)
                print(f"  Progress saved to: {output_file}")
                raise
            except Exception as e:
                print(f"      [ERROR] {type(e).__name__}: {str(e)[:50]}")
                continue
    
    # Save results
    print(f"\n[STEP 4] Saving extraction results...")
    output_file = output_dir / "event_extractions.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_extractions, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print("PART 2 COMPLETE - Summary")
    print(f"{'='*70}")
    print(f"[OK] Total extractions: {len(all_extractions)}")
    print(f"[OK] Results saved to: {output_file}")
    print(f"\nNext step: Part 3 - LLM Judge & Statistical Validation")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

