"""
Project Gutenberg Scraper

This module handles downloading and parsing books from Project Gutenberg.
We need to download 5 books about Abraham Lincoln by other authors.

Books to download:
1. https://www.gutenberg.org/ebooks/6812
2. https://www.gutenberg.org/ebooks/6811
3. https://www.gutenberg.org/ebooks/12801/
4. https://www.gutenberg.org/ebooks/14004/
5. https://www.gutenberg.org/ebooks/18379

Project Gutenberg provides multiple formats. We'll use the plain text UTF-8 format
which is typically available at: https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt
or https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt
"""

import requests
import time
from pathlib import Path
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential


class GutenbergScraper:
    """
    Scraper for Project Gutenberg books.
    
    Project Gutenberg is a library of free eBooks. We need to:
    1. Download the book content (plain text format)
    2. Parse metadata (title, author, etc.)
    3. Handle rate limiting (be respectful!)
    """
    
    BASE_URL = "https://www.gutenberg.org"
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the scraper.
        
        Args:
            output_dir: Directory to save downloaded books (relative to project root)
        """
        if output_dir is None:
            # Default to project root/data/raw/gutenberg
            # Go up from script location to project root
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent
            output_dir = project_root / "data" / "raw" / "gutenberg"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        # Set a user agent to be respectful
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Educational Research - ML Evals Project)'
        })
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _fetch_with_retry(self, url: str) -> requests.Response:
        """
        Fetch a URL with retry logic and rate limiting.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If request fails after retries
        """
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        # Be respectful - wait a bit between requests
        time.sleep(1)
        return response
    
    def get_book_metadata(self, book_id: str) -> Dict[str, str]:
        """
        Get metadata for a book from its Gutenberg page.
        
        Args:
            book_id: Gutenberg book ID (e.g., "6812")
            
        Returns:
            Dictionary with metadata (title, author, etc.)
        """
        url = f"{self.BASE_URL}/ebooks/{book_id}"
        
        try:
            response = self._fetch_with_retry(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title (usually in <title> tag or h1)
            title_elem = soup.find('title')
            title = title_elem.text.strip() if title_elem else f"Book {book_id}"
            
            # Try to extract author from metadata
            author = "Unknown"
            # Look for author in various places
            author_elem = soup.find('span', {'property': 'schema:author'})
            if not author_elem:
                author_elem = soup.find('a', href=re.compile(r'/ebooks/author/'))
            if author_elem:
                author = author_elem.text.strip()
            
            return {
                'book_id': book_id,
                'title': title,
                'author': author,
                'url': url
            }
        except Exception as e:
            print(f"Warning: Could not fetch metadata for book {book_id}: {e}")
            return {
                'book_id': book_id,
                'title': f"Book {book_id}",
                'author': "Unknown",
                'url': url
            }
    
    def download_book_text(self, book_id: str) -> Optional[str]:
        """
        Download the plain text version of a book.
        
        Project Gutenberg books are available in multiple formats. We'll try:
        1. https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt
        2. https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt
        
        Args:
            book_id: Gutenberg book ID
            
        Returns:
            Book text content, or None if download fails
        """
        # Try different URL patterns
        urls_to_try = [
            f"{self.BASE_URL}/files/{book_id}/{book_id}-0.txt",
            f"{self.BASE_URL}/files/{book_id}/{book_id}.txt",
            f"{self.BASE_URL}/cache/epub/{book_id}/pg{book_id}.txt",
        ]
        
        for url in urls_to_try:
            try:
                response = self._fetch_with_retry(url)
                # Check if we got actual text content
                if response.status_code == 200 and len(response.text) > 1000:
                    return response.text
            except Exception as e:
                continue
        
        print(f"Warning: Could not download book {book_id} from any URL")
        return None
    
    def scrape_book(self, book_id: str) -> Optional[Dict]:
        """
        Scrape a complete book: download text and metadata.
        
        Args:
            book_id: Gutenberg book ID
            
        Returns:
            Dictionary with book data, or None if scraping fails
        """
        print(f"\nScraping book {book_id}...")
        
        # Get metadata
        metadata = self.get_book_metadata(book_id)
        print(f"  Title: {metadata['title']}")
        print(f"  Author: {metadata['author']}")
        
        # Download text
        text_content = self.download_book_text(book_id)
        if not text_content:
            return None
        
        # Save raw text
        output_file = self.output_dir / f"book_{book_id}.txt"
        output_file.write_text(text_content, encoding='utf-8')
        print(f"  Saved to: {output_file}")
        print(f"  Text length: {len(text_content):,} characters")
        
        return {
            **metadata,
            'text_content': text_content,
            'text_length': len(text_content)
        }
    
    def scrape_all_books(self, book_ids: List[str]) -> List[Dict]:
        """
        Scrape multiple books.
        
        Args:
            book_ids: List of Gutenberg book IDs
            
        Returns:
            List of book data dictionaries
        """
        results = []
        
        for book_id in tqdm(book_ids, desc="Scraping books"):
            book_data = self.scrape_book(book_id)
            if book_data:
                results.append(book_data)
            # Be respectful - wait between books
            time.sleep(2)
        
        return results


if __name__ == "__main__":
    # Test the scraper with one book
    scraper = GutenbergScraper()
    
    # The 5 books we need to download
    book_ids = ["6812", "6811", "12801", "14004", "18379"]
    
    print("=" * 60)
    print("Project Gutenberg Scraper - Test Run")
    print("=" * 60)
    
    # Scrape all books
    books = scraper.scrape_all_books(book_ids)
    
    print(f"\n{'='*60}")
    print(f"Successfully scraped {len(books)} out of {len(book_ids)} books")
    print(f"{'='*60}")

