"""
Separate script to extract Election Night 1860 document (mal0440500).
This script will help diagnose why this specific document isn't being extracted.
"""

import sys
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.data_acquisition.loc_scraper_improved import LoCScraperImproved


def extract_election_night():
    """
    Extract Election Night 1860 document and diagnose issues.
    """
    url = "https://www.loc.gov/item/mal0440500/"
    
    print("=" * 70)
    print("Extracting Election Night 1860 (mal0440500)")
    print("=" * 70)
    print(f"URL: {url}\n")
    
    scraper = LoCScraperImproved()
    
    # Method 1: Try JSON API to get fulltext_file URL
    print("[METHOD 1] Trying JSON API...")
    try:
        api_url = url.rstrip('/') + '/?fo=json'
        print(f"  Fetching: {api_url}")
        response = requests.get(api_url, headers=scraper.session.headers, timeout=30)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for fulltext_file in resources
            print("\n  Checking for fulltext_file URL...")
            resources = data.get('resources', [])
            if not resources:
                item = data.get('item', {})
                resources = item.get('resources', [])
            
            print(f"  Found {len(resources)} resource(s)")
            
            for i, resource in enumerate(resources):
                print(f"\n  Resource {i+1}:")
                fulltext_file = resource.get('fulltext_file')
                print(f"    fulltext_file: {fulltext_file}")
                
                if fulltext_file:
                    # Check if it's XML or TXT
                    if '.xml' in fulltext_file:
                        print(f"    Type: XML file")
                        # Try to download and extract text
                        print(f"    Downloading XML...")
                        try:
                            xml_response = requests.get(fulltext_file, timeout=30)
                            if xml_response.status_code == 200:
                                print(f"    XML downloaded ({len(xml_response.content)} bytes)")
                                # Parse XML to extract text
                                from xml.etree import ElementTree as ET
                                root = ET.fromstring(xml_response.content)
                                # Try to find text content
                                text_content = ET.tostring(root, encoding='unicode', method='text')
                                print(f"    Extracted text length: {len(text_content)} chars")
                                if len(text_content) > 100:
                                    print(f"    SUCCESS! Text extracted from XML")
                                    return text_content
                        except Exception as e:
                            print(f"    Error downloading XML: {e}")
                    elif '.txt' in fulltext_file:
                        print(f"    Type: TXT file")
                        print(f"    Downloading TXT...")
                        try:
                            txt_response = requests.get(fulltext_file, timeout=30)
                            if txt_response.status_code == 200:
                                text_content = txt_response.text
                                print(f"    Text downloaded ({len(text_content)} chars)")
                                if len(text_content) > 100:
                                    print(f"    SUCCESS! Text extracted")
                                    return text_content
                        except Exception as e:
                            print(f"    Error downloading TXT: {e}")
            
            # Also check for fulltext in page array
            print("\n  Checking page array for fulltext...")
            pages = data.get('page', [])
            print(f"  Found {len(pages)} page(s)")
            for i, page in enumerate(pages):
                if 'fulltext' in page:
                    fulltext = page.get('fulltext', '')
                    print(f"  Page {i+1} has fulltext field ({len(fulltext)} chars)")
                    if len(fulltext) > 100:
                        print(f"  SUCCESS! Found fulltext in page array")
                        return fulltext
            
            # Check item.resources
            print("\n  Checking item.resources...")
            item = data.get('item', {})
            item_resources = item.get('resources', [])
            for resource in item_resources:
                fulltext_file = resource.get('fulltext_file')
                if fulltext_file:
                    print(f"    Found fulltext_file: {fulltext_file}")
                    # Try to download
                    try:
                        file_response = requests.get(fulltext_file, timeout=30)
                        if file_response.status_code == 200:
                            if '.xml' in fulltext_file:
                                from xml.etree import ElementTree as ET
                                root = ET.fromstring(file_response.content)
                                text_content = ET.tostring(root, encoding='unicode', method='text')
                                if len(text_content) > 100:
                                    print(f"    SUCCESS! Extracted from XML")
                                    return text_content
                            else:
                                text_content = file_response.text
                                if len(text_content) > 100:
                                    print(f"    SUCCESS! Extracted text")
                                    return text_content
                    except Exception as e:
                        print(f"    Error: {e}")
        
    except Exception as e:
        print(f"  JSON API method failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Method 2: Try Selenium to interact with page
    print("\n[METHOD 2] Trying Selenium...")
    if scraper.driver:
        try:
            print(f"  Loading page with Selenium...")
            scraper.driver.get(url)
            import time
            time.sleep(3)
            
            # Check page source
            page_source = scraper.driver.page_source
            print(f"  Page loaded ({len(page_source)} chars)")
            
            # Try to find download links
            soup = BeautifulSoup(page_source, 'html.parser')
            download_links = scraper.find_download_links(soup, url)
            print(f"  Found download links: {download_links}")
            
            if download_links:
                for format_type, link_url in download_links.items():
                    print(f"  Trying to download {format_type} from {link_url}")
                    url_part = url.split('/')[-1].replace('.html', '').replace('/', '_')
                    if not url_part or url_part == 'loc':
                        url_part = 'mal0440500'
                    output_path = scraper.output_dir / f"loc_{url_part}.txt"
                    
                    if scraper.download_file(link_url, output_path):
                        content = output_path.read_text(encoding='utf-8', errors='ignore')
                        if len(content) > 100:
                            print(f"  SUCCESS! Downloaded {format_type}")
                            return content
            
            # Try text view button
            print("  Looking for text view button...")
            text_buttons = scraper.driver.find_elements(
                scraper.driver.find_element.__self__.By.XPATH,
                "//button[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text')] | "
                "//a[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text')]"
            )
            print(f"  Found {len(text_buttons)} text view buttons")
            
        except Exception as e:
            print(f"  Selenium method failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("  Selenium not available")
    
    # Method 3: Try direct download from known URL pattern
    print("\n[METHOD 3] Trying direct download URLs...")
    direct_urls = [
        "https://tile.loc.gov/storage-services/service/mss/mal/044/0440500/0440500.xml",
        "https://tile.loc.gov/storage-services/service/mss/mal/044/0440500/0440500.txt",
        "https://tile.loc.gov/storage-services/service/gdc/gdccrowd/mss/mal/044/0440500/0440500.txt",
    ]
    
    for direct_url in direct_urls:
        try:
            print(f"  Trying: {direct_url}")
            response = requests.get(direct_url, timeout=30)
            print(f"    Status: {response.status_code}")
            if response.status_code == 200:
                if '.xml' in direct_url:
                    from xml.etree import ElementTree as ET
                    root = ET.fromstring(response.content)
                    text_content = ET.tostring(root, encoding='unicode', method='text')
                    if len(text_content) > 100:
                        print(f"    SUCCESS! Extracted from XML")
                        return text_content
                else:
                    text_content = response.text
                    if len(text_content) > 100:
                        print(f"    SUCCESS! Extracted text")
                        return text_content
        except Exception as e:
            print(f"    Error: {e}")
    
    print("\n" + "=" * 70)
    print("FAILED: Could not extract text")
    print("=" * 70)
    return None


if __name__ == "__main__":
    text = extract_election_night()
    
    if text:
        # Save to file
        output_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "loc"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "loc_mal0440500.txt"
        output_file.write_text(text, encoding='utf-8')
        print(f"\nSaved to: {output_file}")
        print(f"Content length: {len(text)} characters")
        print(f"\nFirst 500 characters:")
        print(text[:500])
    else:
        print("\nCould not extract text. Check the output above for details.")


