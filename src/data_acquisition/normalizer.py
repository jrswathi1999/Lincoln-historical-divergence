"""
Data Normalizer

This module normalizes scraped data into the required JSON schema.

Required Schema:
{
    "id": "unique_identifier",
    "title": "Human-readable title",
    "reference": "something that points to this item in the raw data",
    "document_type": "Letter | Speech | Note | etc.",
    "date": "As in the source (do not add or remove precision)",
    "place": "If known",
    "from": "If applicable",
    "to": "If applicable",
    "content": "Full source text as formatted in this source"
}
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class DataNormalizer:
    """
    Normalizes scraped data into the required JSON schema.
    
    We need to create two datasets:
    1. gutenberg_dataset.json - Books from Project Gutenberg
    2. loc_dataset.json - Documents from Library of Congress
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the normalizer.
        
        Args:
            output_dir: Directory to save normalized JSON files (relative to project root)
        """
        if output_dir is None:
            # Default to project root/data/normalized
            # Go up from script location to project root
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent
            output_dir = project_root / "data" / "normalized"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def normalize_gutenberg_book(self, book_data: Dict, index: int) -> Dict:
        """
        Normalize a Project Gutenberg book into the required schema.
        
        Args:
            book_data: Raw book data from scraper
            index: Index for unique ID generation
            
        Returns:
            Normalized book entry
        """
        book_id = book_data.get('book_id', f'unknown_{index}')
        
        return {
            "id": f"gutenberg_{book_id}",
            "title": book_data.get('title', f'Book {book_id}'),
            "reference": book_data.get('url', f'https://www.gutenberg.org/ebooks/{book_id}'),
            "document_type": "Book",  # All Gutenberg items are books
            "date": None,  # Books don't have specific dates in the source
            "place": None,
            "from": None,
            "to": None,
            "content": book_data.get('text_content', '')
        }
    
    def normalize_loc_document(self, doc_data: Dict, index: int) -> Dict:
        """
        Normalize a Library of Congress document into the required schema.
        
        Args:
            doc_data: Raw document data from scraper
            index: Index for unique ID generation
            
        Returns:
            Normalized document entry
        """
        # Extract ID from URL
        url = doc_data.get('url', '')
        doc_id = url.split('/')[-1].replace('.html', '').replace('/', '_')
        if not doc_id:
            doc_id = f'loc_doc_{index}'
        
        return {
            "id": f"loc_{doc_id}",
            "title": doc_data.get('title', 'Untitled Document'),
            "reference": url,
            "document_type": doc_data.get('document_type', 'Document'),
            "date": doc_data.get('date'),  # Keep as-is from source
            "place": doc_data.get('place'),
            "from": doc_data.get('from'),
            "to": doc_data.get('to'),
            "content": doc_data.get('content', '')
        }
    
    def create_gutenberg_dataset(self, books: List[Dict]) -> List[Dict]:
        """
        Create normalized dataset from Gutenberg books.
        
        Args:
            books: List of raw book data
            
        Returns:
            List of normalized book entries
        """
        normalized = []
        
        for idx, book in enumerate(books):
            normalized_entry = self.normalize_gutenberg_book(book, idx)
            normalized.append(normalized_entry)
        
        return normalized
    
    def create_loc_dataset(self, documents: List[Dict]) -> List[Dict]:
        """
        Create normalized dataset from LoC documents.
        
        Args:
            documents: List of raw document data
            
        Returns:
            List of normalized document entries
        """
        normalized = []
        
        for idx, doc in enumerate(documents):
            normalized_entry = self.normalize_loc_document(doc, idx)
            normalized.append(normalized_entry)
        
        return normalized
    
    def save_dataset(self, dataset: List[Dict], filename: str):
        """
        Save a normalized dataset to JSON file.
        
        Args:
            dataset: List of normalized entries
            filename: Output filename
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved normalized dataset: {output_path}")
        print(f"  Total entries: {len(dataset)}")
        print(f"  Total characters: {sum(len(entry.get('content', '')) for entry in dataset):,}")


if __name__ == "__main__":
    # This will be called from the main script after scraping
    print("Data Normalizer - Run this after scraping is complete")

