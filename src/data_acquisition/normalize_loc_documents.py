"""
Script to normalize LoC documents from raw files.

This script reads downloaded LoC documents from data/raw/loc/ and normalizes them
into the required JSON schema, saving to data/normalized/loc_dataset.json
"""

import sys
import json
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.data_acquisition.normalizer import DataNormalizer


def extract_id_from_filename(filename: str) -> Optional[str]:
    """
    Extract LoC document ID from filename.
    
    Examples:
        loc_mal0440500.txt -> mal0440500
        loc_mal.0882800.txt -> mal.0882800
        loc_trans-nicolay-copy.txt -> trans-nicolay-copy
    """
    # Remove loc_ prefix and .txt extension
    base = filename.replace('loc_', '').replace('.txt', '')
    return base if base else None


def get_url_from_id(doc_id: str) -> str:
    """
    Reconstruct LoC URL from document ID.
    
    Examples:
        mal0440500 -> https://www.loc.gov/item/mal0440500/
        mal.0882800 -> https://www.loc.gov/resource/mal.0882800/
        trans-nicolay-copy -> https://www.loc.gov/exhibits/gettysburg-address/ext/trans-nicolay-copy.html
    """
    # Known URL mappings
    url_mapping = {
        'mal0440500': 'https://www.loc.gov/item/mal0440500/',
        'mal.0882800': 'https://www.loc.gov/resource/mal.0882800/',
        'mal.4361300': 'https://www.loc.gov/resource/mal.4361300/',
        'mal.4361800': 'https://www.loc.gov/resource/mal.4361800/',
        'trans-nicolay-copy': 'https://www.loc.gov/exhibits/gettysburg-address/ext/trans-nicolay-copy.html',
    }
    
    if doc_id in url_mapping:
        return url_mapping[doc_id]
    
    # Try to infer URL pattern
    if doc_id.startswith('mal'):
        # Check if it's item or resource format
        if '.' in doc_id:
            return f"https://www.loc.gov/resource/{doc_id}/"
        else:
            return f"https://www.loc.gov/item/{doc_id}/"
    
    # Default fallback
    return f"https://www.loc.gov/item/{doc_id}/"


def fetch_metadata_from_api(url: str) -> Dict:
    """
    Fetch metadata from LoC JSON API.
    
    Returns:
        Dictionary with title, date, place, from, to, document_type
    """
    try:
        api_url = url.rstrip('/') + '/?fo=json'
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            item = data.get('item', {})
            
            title = item.get('title', 'Untitled Document')
            date = item.get('date')
            place = None  # Usually not in API
            from_field = None
            to_field = None
            
            # Try to infer document type from title
            document_type = 'Document'
            title_lower = title.lower()
            if 'address' in title_lower:
                document_type = 'Speech'
            elif 'letter' in title_lower or 'to' in title_lower:
                document_type = 'Letter'
            elif 'note' in title_lower:
                document_type = 'Note'
            
            return {
                'title': title,
                'date': date,
                'place': place,
                'from': from_field,
                'to': to_field,
                'document_type': document_type
            }
    except Exception as e:
        print(f"    Warning: Could not fetch metadata from API: {e}")
    
    return {
        'title': 'Untitled Document',
        'date': None,
        'place': None,
        'from': None,
        'to': None,
        'document_type': 'Document'
    }


def clean_html_and_metadata(content: str) -> str:
    """
    Remove HTML tags, navigation elements, and metadata from content.
    """
    # Remove HTML tags using BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    
    # Remove common navigation/metadata patterns
    lines = text.split('\n')
    cleaned_lines = []
    
    skip_patterns = [
        r'^Library of Congress$',
        r'^Exhibitions$',
        r'^Ask a Librarian$',
        r'^Digital Collections$',
        r'^Library Catalogs$',
        r'^The Library of Congress$',
        r'^> Online Exhibition$',
        r'^Back to Exhibition$',
        r'^Connect with the Library$',
        r'^All ways to connect$',
        r'^Subscribe & Comment$',
        r'^RSS & E-Mail$',
        r'^Download & Play$',
        r'^\(external link\)$',
        r'^Inspector General$',
        r'^Accessibility$',
        r'^External Link Disclaimer$',
        r'^Speech Enabled$',
        r'^mal-\d+$',  # Document IDs like "mal-0440500"
        r'^Abraham Lincoln Papers at the Library of Congress',
        r'^Selected and converted\.$',
        r'^American Memory, Library of Congress\.$',
        r'^Washington, DC, \d+\.$',
        r'^Preceding element provides',
        r'^For more information about',
        r'^Manuscript Division',
        r'^Copyright status',
        r'^The National Digital Library Program',
        r'^This transcription is intended',
        r'^\d{4}/\d{2}/\d{2}$',  # Dates like "1999/05/20"
        r'^\d{4}$',  # Just year numbers
        r'^0001$',  # Page numbers
    ]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip lines matching skip patterns
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                should_skip = True
                break
        
        if not should_skip:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def extract_text_from_json(content: str) -> str:
    """
    Extract actual text content from JSON metadata.
    
    If content is JSON, tries to extract 'fulltext' from 'page' array.
    Otherwise returns the content as-is.
    """
    # Try to parse as JSON
    try:
        # Handle potential control character issues
        data = json.loads(content, strict=False)
        
        # Check if it's a LoC JSON API response
        if isinstance(data, dict):
            # Try to get fulltext from page array (most common location)
            page = data.get('page', [])
            if isinstance(page, list) and len(page) > 0:
                # Look for fulltext in page items - usually the last item with 'fulltext' key
                fulltext_parts = []
                for page_item in page:
                    if isinstance(page_item, dict):
                        fulltext = page_item.get('fulltext')
                        if fulltext and isinstance(fulltext, str) and len(fulltext.strip()) > 0:
                            fulltext_parts.append(fulltext.strip())
                
                if fulltext_parts:
                    # Join all fulltext parts (in case there are multiple pages)
                    extracted = '\n\n'.join(fulltext_parts)
                    if len(extracted) > 100:  # Only use if we got substantial text
                        return extracted
            
            # Also check resource.fulltext (alternative location)
            resource = data.get('resource', {})
            if isinstance(resource, dict):
                fulltext = resource.get('fulltext')
                if fulltext and isinstance(fulltext, str) and len(fulltext.strip()) > 100:
                    return fulltext.strip()
            
            # Check resources array
            resources = data.get('resources', [])
            if isinstance(resources, list) and len(resources) > 0:
                for res in resources:
                    if isinstance(res, dict):
                        fulltext = res.get('fulltext')
                        if fulltext and isinstance(fulltext, str) and len(fulltext.strip()) > 100:
                            return fulltext.strip()
            
            # Check item.resources
            item = data.get('item', {})
            if isinstance(item, dict):
                resources = item.get('resources', [])
                if isinstance(resources, list) and len(resources) > 0:
                    for res in resources:
                        if isinstance(res, dict):
                            fulltext = res.get('fulltext')
                            if fulltext and isinstance(fulltext, str) and len(fulltext.strip()) > 100:
                                return fulltext.strip()
        
    except (json.JSONDecodeError, ValueError) as e:
        # Not JSON or invalid JSON, return as-is
        pass
    
    # Return original content if not JSON or no fulltext found
    return content


def normalize_loc_files():
    """
    Read LoC files from data/raw/loc/ and normalize them.
    """
    print("=" * 70)
    print("Normalizing LoC Documents")
    print("=" * 70)
    
    # Get raw files directory
    raw_dir = project_root / "data" / "raw" / "loc"
    
    if not raw_dir.exists():
        print(f"Error: Directory {raw_dir} does not exist!")
        return
    
    # Find all .txt files
    loc_files = list(raw_dir.glob("loc_*.txt"))
    
    if not loc_files:
        print(f"No LoC files found in {raw_dir}")
        return
    
    print(f"\nFound {len(loc_files)} LoC document(s)\n")
    
    # Process each file
    documents = []
    for file_path in sorted(loc_files):
        filename = file_path.name
        print(f"Processing: {filename}")
        
        # Extract ID and get URL
        doc_id = extract_id_from_filename(filename)
        if not doc_id:
            print(f"  Warning: Could not extract ID from filename, skipping")
            continue
        
        url = get_url_from_id(doc_id)
        print(f"  URL: {url}")
        
        # Read file content
        try:
            raw_content = file_path.read_text(encoding='utf-8', errors='ignore')
            print(f"  Raw content length: {len(raw_content):,} characters")
            
            # Extract text from JSON if needed
            content = extract_text_from_json(raw_content)
            
            # Clean HTML and metadata
            content = clean_html_and_metadata(content)
            print(f"  Extracted content length: {len(content):,} characters")
            
            if len(content) < len(raw_content) * 0.1:
                print(f"  Warning: Extracted content is much shorter than raw content")
        except Exception as e:
            print(f"  Error reading file: {e}")
            continue
        
        # Fetch metadata from API
        print(f"  Fetching metadata...")
        metadata = fetch_metadata_from_api(url)
        
        # Special handling for Gettysburg Address
        if 'trans-nicolay-copy' in doc_id or 'gettysburg' in url.lower():
            metadata['title'] = 'Gettysburg Address - "Nicolay Copy"'
            metadata['document_type'] = 'Speech'
        
        # Create document dictionary
        doc_data = {
            'title': metadata['title'],
            'content': content,
            'url': url,
            'date': metadata['date'],
            'place': metadata['place'],
            'from': metadata['from'],
            'to': metadata['to'],
            'document_type': metadata['document_type'],
            'file_format': 'text'
        }
        
        documents.append(doc_data)
        print(f"  [OK] Processed\n")
    
    # Normalize using DataNormalizer
    print(f"{'='*70}")
    print("Creating normalized dataset...")
    print(f"{'='*70}")
    
    normalizer = DataNormalizer()
    loc_dataset = normalizer.create_loc_dataset(documents)
    normalizer.save_dataset(loc_dataset, "loc_dataset.json")
    
    print(f"\n{'='*70}")
    print("COMPLETE!")
    print(f"{'='*70}")
    print(f"Normalized dataset saved to: data/normalized/loc_dataset.json")
    print(f"Total entries: {len(loc_dataset)}")
    print(f"\nYou can now run Part 2: Event Extraction")


if __name__ == "__main__":
    normalize_loc_files()

