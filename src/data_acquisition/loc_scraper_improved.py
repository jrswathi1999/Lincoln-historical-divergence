"""
Improved Library of Congress (LoC) Scraper

This version handles downloading actual document files (PDF/text) from LoC pages.
LoC pages show handwritten documents with download options for different formats.
"""

import requests
import time
from pathlib import Path
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re
from tqdm import tqdm
import json

# Try to import Selenium for JavaScript-rendered pages
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: Selenium not installed. Install with: pip install selenium")

# Try to import PDF processing libraries
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: PyPDF2 not installed. Install with: pip install PyPDF2")


class LoCScraperImproved:
    """
    Improved scraper that downloads actual document files from LoC.
    
    Strategy:
    1. Access the resource page
    2. Find download links (PDF or text format)
    3. Download the file
    4. Extract text from PDF or use text file directly
    5. Extract metadata from the page
    """
    
    BASE_URL = "https://www.loc.gov"
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the scraper.
        
        Args:
            output_dir: Directory to save downloaded documents
        """
        if output_dir is None:
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent
            output_dir = project_root / "data" / "raw" / "loc"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        # Use more realistic browser headers to avoid blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
        
        # Initialize Selenium driver if available
        self.driver = None
        if SELENIUM_AVAILABLE:
            try:
                chrome_options = Options()
                chrome_options.add_argument('--headless=new')  # Run in background
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                
                # Try webdriver-manager first (auto-downloads chromedriver)
                try:
                    from selenium.webdriver.chrome.service import Service
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except ImportError:
                    # Fallback to system chromedriver
                    self.driver = webdriver.Chrome(options=chrome_options)
                
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                print("  Selenium initialized successfully")
            except Exception as e:
                print(f"Warning: Could not initialize Selenium: {e}")
                print("  Falling back to requests-only mode")
                self.driver = None
    
    def _fetch_with_retry(self, url: str) -> requests.Response:
        """Fetch URL with retry logic and better error handling."""
        for attempt in range(3):
            try:
                # Add referer header for LoC
                headers = {'Referer': 'https://www.loc.gov/'}
                response = self.session.get(url, timeout=30, headers=headers)
                
                if response.status_code == 200:
                    time.sleep(2)  # Be respectful
                    return response
                elif response.status_code == 403:
                    # Try without session cookies, or try JSON API directly
                    if attempt < 2:
                        # Clear cookies and try again
                        self.session.cookies.clear()
                        time.sleep(3)
                        continue
                    else:
                        # Last attempt - try JSON API format directly
                        if '/item/' in url or '/resource/' in url:
                            json_url = url.rstrip('/') + '/?fo=json'
                            try:
                                json_response = self.session.get(json_url, timeout=30, headers=headers)
                                if json_response.status_code == 200:
                                    return json_response
                            except:
                                pass
                        raise requests.HTTPError(f"403 Forbidden: {url}")
                elif response.status_code == 404:
                    raise requests.HTTPError(f"404 Not Found: {url}")
                else:
                    response.raise_for_status()
            except requests.RequestException as e:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise requests.RequestException(f"Failed to fetch {url}")
    
    def find_download_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
        """
        Find download links for PDF and text formats.
        Also tries using Selenium to click download buttons if available.
        
        Args:
            soup: BeautifulSoup object of the page
            base_url: Base URL of the page
            
        Returns:
            Dictionary with format -> URL mapping
        """
        download_links = {}
        
        # Try using Selenium to find and click download buttons
        if self.driver:
            try:
                # Look for download buttons/links using Selenium
                download_buttons = self.driver.find_elements(By.XPATH, 
                    "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')] | "
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')] | "
                    "//a[contains(@href, 'download')] | "
                    "//a[contains(@href, '.pdf')] | "
                    "//a[contains(@href, '.txt')]"
                )
                
                for btn in download_buttons:
                    try:
                        href = btn.get_attribute('href')
                        text = btn.text.lower()
                        
                        if href:
                            if 'pdf' in text or 'pdf' in href.lower():
                                download_links['pdf'] = href if href.startswith('http') else self.BASE_URL + href
                            elif 'text' in text or 'txt' in text or 'text' in href.lower():
                                download_links['text'] = href if href.startswith('http') else self.BASE_URL + href
                    except:
                        continue
                
                # Also try to find format dropdowns
                try:
                    format_selects = self.driver.find_elements(By.TAG_NAME, "select")
                    for select in format_selects:
                        options = select.find_elements(By.TAG_NAME, "option")
                        for option in options:
                            option_text = option.text.lower()
                            if 'text' in option_text or 'txt' in option_text:
                                # Try to get download URL when this option is selected
                                select.click()
                                option.click()
                                time.sleep(1)
                                # Look for download button that appears
                                go_buttons = self.driver.find_elements(By.XPATH, 
                                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'go')] | "
                                    "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'go')]"
                                )
                                for go_btn in go_buttons:
                                    href = go_btn.get_attribute('href')
                                    if href:
                                        download_links['text'] = href if href.startswith('http') else self.BASE_URL + href
                                        break
                except:
                    pass
            except Exception as e:
                print(f"      Selenium download link search failed: {e}")
        
        # Look for download buttons/links
        # LoC often has download options in various places
        
        # Method 1: Look for download links in the page
        download_elements = soup.find_all('a', href=re.compile(r'download|\.pdf|\.txt', re.I))
        for elem in download_elements:
            href = elem.get('href', '')
            text = elem.get_text(strip=True).lower()
            
            if 'pdf' in text or 'pdf' in href.lower():
                if href.startswith('http'):
                    download_links['pdf'] = href
                else:
                    download_links['pdf'] = self.BASE_URL + href
            elif 'text' in text or 'txt' in href.lower():
                if href.startswith('http'):
                    download_links['text'] = href
                else:
                    download_links['text'] = self.BASE_URL + href
        
        # Method 2: Try API format to get download URLs (most reliable)
        # LoC JSON API often has file URLs including fulltext_file
        try:
            api_url = base_url.rstrip('/') + '/?fo=json'
            response = self._fetch_with_retry(api_url)
            if response.headers.get('content-type', '').startswith('application/json'):
                data = response.json()
                
                # Check for fulltext_file directly in resources (most reliable)
                resources = data.get('resources', [])
                if not resources:
                    # Try item.resources
                    item = data.get('item', {})
                    resources = item.get('resources', [])
                
                for resource in resources:
                    # Check for fulltext_file URL (direct text file)
                    fulltext_file = resource.get('fulltext_file')
                    if fulltext_file and '.txt' in fulltext_file:
                        download_links['text'] = fulltext_file
                        print(f"      Found fulltext_file URL: {fulltext_file}")
                    
                    # Also check files array
                    files = resource.get('files', [])
                    for file_info in files:
                        file_format = file_info.get('format', '').lower()
                        file_url = file_info.get('url', '')
                        mime_type = file_info.get('mime', '').lower()
                        
                        if file_format == 'pdf' and file_url:
                            download_links['pdf'] = file_url
                        elif file_format in ['text', 'txt', 'plain', 'transcription'] and file_url:
                            download_links['text'] = file_url
                        
                        # Also check mime types
                        if 'pdf' in mime_type and file_url:
                            download_links['pdf'] = file_url
                        elif 'text' in mime_type and file_url:
                            download_links['text'] = file_url
                
                # Also check resource object directly
                resource_obj = data.get('resource', {})
                if resource_obj:
                    fulltext_file = resource_obj.get('fulltext_file')
                    if fulltext_file and '.txt' in fulltext_file:
                        download_links['text'] = fulltext_file
                        print(f"      Found fulltext_file in resource: {fulltext_file}")
        except Exception as e:
            print(f"      JSON API method failed: {e}")
        
        # Method 3: Look for common LoC download patterns
        # Check for download buttons with format dropdowns
        download_buttons = soup.find_all(['button', 'a'], class_=re.compile(r'download|format', re.I))
        for btn in download_buttons:
            # Check parent elements for format info
            parent = btn.parent
            if parent:
                text = parent.get_text().lower()
                href = btn.get('href', '')
                if 'pdf' in text or 'pdf' in href:
                    if href and href.startswith('http'):
                        download_links['pdf'] = href
                    elif href:
                        download_links['pdf'] = self.BASE_URL + href
        
        return download_links
    
    def download_file(self, url: str, output_path: Path) -> bool:
        """
        Download a file from URL.
        
        Args:
            url: URL to download from
            output_path: Path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            print(f"      Error downloading {url}: {e}")
            return False
    
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        if not PDF_AVAILABLE:
            return ""
        
        try:
            text = ""
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"      Error extracting PDF text: {e}")
            return ""
    
    def extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract metadata from the page."""
        metadata = {
            'date': None,
            'place': None,
            'from': None,
            'to': None,
            'document_type': None
        }
        
        # Extract title
        title_elem = soup.find('h1') or soup.find('title')
        title = title_elem.text.strip() if title_elem else "Untitled Document"
        
        # Try to extract date from various places
        date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',
            r'\w+ \d{1,2}, \d{4}',
            r'\d{4}'
        ]
        
        text = soup.get_text()
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                metadata['date'] = matches[0]
                break
        
        # Look for date in structured data
        date_elem = soup.find(text=re.compile(r'Date|date', re.I))
        if date_elem:
            parent = date_elem.parent
            if parent:
                date_text = parent.get_text()
                date_match = re.search(r'\d{4}-\d{2}-\d{2}|\w+ \d{1,2}, \d{4}', date_text)
                if date_match:
                    metadata['date'] = date_match.group()
        
        # Determine document type
        title_lower = title.lower()
        if 'letter' in title_lower:
            metadata['document_type'] = 'Letter'
        elif 'address' in title_lower or 'speech' in title_lower:
            metadata['document_type'] = 'Speech'
        elif 'note' in title_lower:
            metadata['document_type'] = 'Note'
        else:
            metadata['document_type'] = 'Document'
        
        return metadata
    
    def download_via_selenium(self, url: str, format_type: str = 'text') -> Optional[str]:
        """
        Download file using Selenium by interacting with download dropdown and Go button.
        Also tries the PDF/image conversion button at the top of the document viewer.
        
        Args:
            url: LoC resource URL
            format_type: 'text' or 'pdf'
            
        Returns:
            Downloaded file content as string, or None if failed
        """
        if not self.driver:
            return None
        
        try:
            print(f"  Loading page with Selenium...")
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Give JavaScript time to render
            
            # Method 1: Try the "Text with Images" view option (best for text extraction)
            print(f"  Looking for 'Text with Images' view option...")
            try:
                # Look for buttons/options that switch to text view
                text_view_selectors = [
                    "//button[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text')]",
                    "//a[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text')]",
                    "//button[contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text')]",
                    "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text with image')]",
                    "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text and image')]",
                    "//*[contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text-view')]",
                    "//*[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'text-view')]",
                ]
                
                text_view_buttons = []
                for selector in text_view_selectors:
                    try:
                        buttons = self.driver.find_elements(By.XPATH, selector)
                        text_view_buttons.extend(buttons)
                    except:
                        continue
                
                # Also look in toolbar/control areas and view mode tabs
                try:
                    # Look for view mode tabs/buttons (Image, PDF, Text)
                    view_mode_elements = self.driver.find_elements(By.XPATH,
                        "//*[contains(@class, 'toolbar')]//button | "
                        "//*[contains(@class, 'controls')]//button | "
                        "//*[contains(@class, 'viewer-controls')]//button | "
                        "//*[contains(@class, 'view-mode')]//button | "
                        "//*[contains(@class, 'tab')]//button | "
                        "//*[contains(@class, 'view-tab')] | "
                        "//*[@role='tab']"
                    )
                    for btn in view_mode_elements:
                        btn_text = (btn.text or btn.get_attribute('title') or btn.get_attribute('aria-label') or btn.get_attribute('data-view') or '').lower()
                        # Look for text view options
                        if 'text' in btn_text and ('image' in btn_text or 'view' in btn_text or 'transcript' in btn_text):
                            text_view_buttons.append(btn)
                        # Also check for buttons that say just "Text" when other options are "Image" and "PDF"
                        elif btn_text.strip() == 'text' or btn_text == 'text view':
                            text_view_buttons.append(btn)
                except:
                    pass
                
                # Remove duplicates
                seen = set()
                unique_text_buttons = []
                for btn in text_view_buttons:
                    try:
                        btn_id = id(btn)
                        if btn_id not in seen and btn.is_displayed():
                            seen.add(btn_id)
                            unique_text_buttons.append(btn)
                    except:
                        continue
                
                for btn in unique_text_buttons:
                    try:
                        btn_text = (btn.text or btn.get_attribute('title') or btn.get_attribute('aria-label') or '').lower()
                        if 'text' in btn_text:
                            print(f"    Found text view button: {btn_text}")
                            
                            # Click to switch to text view
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                            time.sleep(0.5)
                            self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(4)  # Wait for view to change and content to load
                            
                            # Wait for text content to appear
                            try:
                                WebDriverWait(self.driver, 10).until(
                                    lambda d: len(d.find_elements(By.XPATH, "//*[contains(@class, 'text')] | //*[contains(@class, 'transcript')] | //pre | //p")) > 0
                                )
                            except:
                                pass
                            
                            # Now extract text from the page
                            page_source = self.driver.page_source
                            soup = BeautifulSoup(page_source, 'html.parser')
                            
                            # Look for transcription/text content areas
                            text_content = self._extract_text_from_text_view(soup)
                            if text_content and len(text_content) > 100:
                                print(f"    Extracted {len(text_content)} characters from text view")
                                return text_content
                            
                            # Also try getting text directly from the page if view changed
                            try:
                                # Look for text elements that appeared after switching view
                                text_elements = self.driver.find_elements(By.XPATH,
                                    "//*[contains(@class, 'transcription')] | "
                                    "//*[contains(@class, 'text-content')] | "
                                    "//pre | "
                                    "//*[@role='textbox']"
                                )
                                for elem in text_elements:
                                    if elem.is_displayed():
                                        elem_text = elem.text.strip()
                                        if len(elem_text) > 100:
                                            print(f"    Extracted {len(elem_text)} characters from text element")
                                            return elem_text
                            except:
                                pass
                    except Exception as e:
                        print(f"    Error with text view button: {e}")
                        continue
            except Exception as e:
                print(f"    Text view method failed: {e}")
            
            # Method 2: Try the PDF/image conversion button at the top of document viewer
            print(f"  Looking for PDF/image conversion button at top of viewer...")
            try:
                # Look for buttons/icons at the top of the document viewer area
                # These are usually toolbar buttons that switch view modes
                viewer_area = None
                try:
                    # Try to find the document viewer container
                    viewer_selectors = [
                        "//*[contains(@class, 'viewer')]",
                        "//*[contains(@id, 'viewer')]",
                        "//*[contains(@class, 'document')]",
                        "//*[contains(@class, 'image')]",
                        "//iframe",
                        "//*[@role='img']"
                    ]
                    for selector in viewer_selectors:
                        try:
                            viewers = self.driver.find_elements(By.XPATH, selector)
                            if viewers:
                                viewer_area = viewers[0]
                                break
                        except:
                            continue
                except:
                    pass
                
                # Look for buttons/icons that convert to PDF - check toolbar areas
                pdf_button_selectors = [
                    # Buttons with PDF in title/aria-label
                    "//button[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pdf')]",
                    "//a[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pdf')]",
                    "//button[contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pdf')]",
                    # Buttons in toolbar/control areas
                    "//*[contains(@class, 'toolbar')]//button | //*[contains(@class, 'controls')]//button",
                    "//*[contains(@class, 'viewer-controls')]//button",
                    # Icon buttons (SVG, img, etc.)
                    "//*[contains(@class, 'icon') and contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pdf')]",
                    # Links/buttons near "PDF" text
                    "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pdf')]/ancestor::button | //*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pdf')]/ancestor::a"
                ]
                
                pdf_buttons = []
                for selector in pdf_button_selectors:
                    try:
                        buttons = self.driver.find_elements(By.XPATH, selector)
                        pdf_buttons.extend(buttons)
                    except:
                        continue
                
                # Also look for buttons that might switch view modes (image -> PDF)
                if viewer_area:
                    try:
                        # Look for buttons near the viewer
                        viewer_buttons = viewer_area.find_elements(By.XPATH,
                            ".//ancestor::*[contains(@class, 'toolbar')]//button | "
                            ".//preceding-sibling::*//button | "
                            ".//following-sibling::*//button"
                        )
                        pdf_buttons.extend(viewer_buttons)
                    except:
                        pass
                
                # Remove duplicates and filter visible buttons
                seen = set()
                unique_buttons = []
                for btn in pdf_buttons:
                    try:
                        btn_id = id(btn)
                        if btn_id not in seen and btn.is_displayed():
                            seen.add(btn_id)
                            unique_buttons.append(btn)
                    except:
                        continue
                
                for btn in unique_buttons:
                    try:
                        btn_text = btn.text.lower()
                        btn_title = (btn.get_attribute('title') or btn.get_attribute('aria-label') or '').lower()
                        btn_class = (btn.get_attribute('class') or '').lower()
                        
                        # Check if this button is related to PDF
                        if 'pdf' in btn_text or 'pdf' in btn_title or 'pdf' in btn_class:
                            print(f"    Found PDF conversion button: {btn_text or btn_title or btn_class}")
                            
                            # Set up download path
                            url_part = url.split('/')[-1].replace('.html', '').replace('/', '_')
                            pdf_path = self.output_dir / f"loc_{url_part}.pdf"
                            
                            # Click the button
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                            time.sleep(0.5)
                            self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(4)  # Wait for PDF conversion/download
                            
                            # Check if PDF was downloaded
                            if pdf_path.exists():
                                print(f"    PDF downloaded: {pdf_path}")
                                content = self.extract_text_from_pdf(pdf_path)
                                if content:
                                    return content
                            
                            # Check if URL changed to PDF view
                            current_url = self.driver.current_url
                            if 'pdf' in current_url.lower() or '.pdf' in current_url or 'st=pdf' in current_url:
                                print(f"    Switched to PDF view: {current_url}")
                                # Try to download the PDF from this URL
                                if self.download_file(current_url, pdf_path):
                                    content = self.extract_text_from_pdf(pdf_path)
                                    if content:
                                        return content
                            
                            # Check for download links that appeared after clicking
                            time.sleep(2)
                            download_links = self.driver.find_elements(By.XPATH,
                                "//a[contains(@href, '.pdf')] | "
                                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')] | "
                                "//a[contains(@href, 'st=pdf')]"
                            )
                            for link in download_links:
                                href = link.get_attribute('href')
                                if href and ('.pdf' in href.lower() or 'st=pdf' in href.lower()):
                                    print(f"    Found PDF download link: {href}")
                                    if self.download_file(href, pdf_path):
                                        content = self.extract_text_from_pdf(pdf_path)
                                        if content:
                                            return content
                            
                            # If we're now on a PDF page, try to get the PDF content directly
                            if 'pdf' in current_url.lower():
                                # The page might now show PDF - try to extract it
                                try:
                                    pdf_iframe = self.driver.find_element(By.XPATH, "//iframe[contains(@src, '.pdf')]")
                                    iframe_src = pdf_iframe.get_attribute('src')
                                    if iframe_src:
                                        print(f"    Found PDF iframe: {iframe_src}")
                                        if self.download_file(iframe_src, pdf_path):
                                            content = self.extract_text_from_pdf(pdf_path)
                                            if content:
                                                return content
                                except:
                                    pass
                            
                            break
                    except Exception as e:
                        print(f"    Error clicking PDF button: {e}")
                        continue
                        
            except Exception as e:
                print(f"    PDF button method failed: {e}")
            
            # Method 2: Try the download dropdown + Go button (existing method)
            
            # Find the download dropdown (select element)
            print(f"  Looking for download dropdown...")
            try:
                # Try multiple selectors for the dropdown
                select_selectors = [
                    "select[name*='format']",
                    "select[id*='format']",
                    "select[class*='format']",
                    "select",
                ]
                
                download_select = None
                for selector in select_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            # Check if it's near "Download" text
                            parent = elem.find_element(By.XPATH, "./..")
                            if 'download' in parent.text.lower():
                                download_select = elem
                                break
                        if download_select:
                            break
                    except:
                        continue
                
                if not download_select:
                    # Try finding by text near "Download"
                    download_labels = self.driver.find_elements(By.XPATH, 
                        "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]"
                    )
                    for label in download_labels:
                        try:
                            # Find select near this label
                            select = label.find_element(By.XPATH, "./following-sibling::select | ./../select")
                            download_select = select
                            break
                        except:
                            continue
                
                if not download_select:
                    print(f"    Could not find download dropdown")
                    return None
                
                print(f"    Found download dropdown")
                
                # Select the format option
                select_obj = Select(download_select)
                
                # Try to select text format
                if format_type == 'text':
                    options_to_try = ['Text (Complete)', 'Text', 'TXT', 'text', 'Plain Text']
                else:
                    options_to_try = ['PDF (Complete)', 'PDF', 'pdf']
                
                selected = False
                for option_text in options_to_try:
                    try:
                        select_obj.select_by_visible_text(option_text)
                        selected = True
                        print(f"    Selected format: {option_text}")
                        break
                    except:
                        try:
                            # Try by value
                            select_obj.select_by_value(option_text.lower())
                            selected = True
                            print(f"    Selected format by value: {option_text}")
                            break
                        except:
                            continue
                
                if not selected:
                    # Try selecting by index (usually text is after PDF)
                    try:
                        if format_type == 'text' and len(select_obj.options) > 1:
                            select_obj.select_by_index(1)  # Usually text is second option
                            print(f"    Selected format by index")
                        else:
                            select_obj.select_by_index(0)
                    except:
                        pass
                
                time.sleep(1)  # Wait for selection to register
                
                # Find and click the "Go" button
                print(f"    Looking for Go button...")
                go_button = None
                
                # Try multiple ways to find Go button
                go_selectors = [
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'go')]",
                    "//input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'go')]",
                    "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'go')]",
                    "//button[@type='submit']",
                ]
                
                for selector in go_selectors:
                    try:
                        buttons = self.driver.find_elements(By.XPATH, selector)
                        for btn in buttons:
                            if btn.is_displayed() and btn.is_enabled():
                                # Check if it's near the download dropdown
                                try:
                                    btn_parent = btn.find_element(By.XPATH, "./..")
                                    if download_select in btn_parent.find_elements(By.TAG_NAME, "*"):
                                        go_button = btn
                                        break
                                except:
                                    # Just take the first visible Go button
                                    go_button = btn
                                    break
                        if go_button:
                            break
                    except:
                        continue
                
                if not go_button:
                    # Try finding button near the select element
                    try:
                        select_parent = download_select.find_element(By.XPATH, "./..")
                        buttons = select_parent.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            if btn.is_displayed():
                                go_button = btn
                                break
                    except:
                        pass
                
                if not go_button:
                    print(f"    Could not find Go button")
                    return None
                
                print(f"    Found Go button, clicking...")
                
                # Set up download directory before clicking
                url_part = url.split('/')[-1].replace('.html', '').replace('/', '_')
                download_path = self.output_dir / f"loc_{url_part}_{format_type}.txt"
                if format_type == 'pdf':
                    download_path = self.output_dir / f"loc_{url_part}.pdf"
                
                # Click the Go button
                self.driver.execute_script("arguments[0].click();", go_button)
                time.sleep(3)  # Wait for download to start
                
                # Check if download started (file appears)
                if download_path.exists():
                    print(f"    File downloaded: {download_path}")
                    if format_type == 'pdf':
                        return self.extract_text_from_pdf(download_path)
                    else:
                        return download_path.read_text(encoding='utf-8', errors='ignore')
                else:
                    # Try to get download URL from the button's action
                    try:
                        download_url = go_button.get_attribute('href') or go_button.get_attribute('onclick')
                        if download_url and 'http' in download_url:
                            # Extract URL from onclick or href
                            import re
                            url_match = re.search(r'https?://[^\s\'"]+', download_url)
                            if url_match:
                                download_url = url_match.group()
                                print(f"    Found download URL: {download_url}")
                                if self.download_file(download_url, download_path):
                                    if format_type == 'pdf':
                                        return self.extract_text_from_pdf(download_path)
                                    else:
                                        return download_path.read_text(encoding='utf-8', errors='ignore')
                    except:
                        pass
                    
                    print(f"    Download may have failed or requires manual interaction")
                    return None
                    
            except Exception as e:
                print(f"    Error interacting with download interface: {e}")
                return None
                
        except Exception as e:
            print(f"  Selenium download failed: {e}")
            return None
    
    def scrape_document(self, url: str) -> Optional[Dict]:
        """
        Scrape a document by downloading its files.
        Uses Selenium to interact with download dropdown and Go button.
        
        Args:
            url: URL to the LoC resource page
            
        Returns:
            Dictionary with document data
        """
        print(f"\nScraping: {url}")
        
        try:
            content = ""
            file_format_used = None
            title = "Untitled Document"
            
            # Try Selenium first if available (handles JavaScript and download UI)
            if self.driver:
                try:
                    print(f"  Using Selenium to download...")
                    # Try text format first
                    content = self.download_via_selenium(url, format_type='text')
                    if content:
                        file_format_used = 'text'
                        print(f"  Successfully downloaded text format ({len(content)} chars)")
                    else:
                        # Try PDF format
                        print(f"  Text download failed, trying PDF...")
                        content = self.download_via_selenium(url, format_type='pdf')
                        if content:
                            file_format_used = 'pdf'
                            print(f"  Successfully downloaded PDF format ({len(content)} chars)")
                    
                    # Get title from page
                    try:
                        title_elem = self.driver.find_element(By.TAG_NAME, "h1")
                        title = title_elem.text.strip()
                    except:
                        try:
                            title = self.driver.title
                        except:
                            pass
                    
                except Exception as e:
                    print(f"  Selenium failed: {e}, trying fallback methods...")
            
            # Fallback: Try JSON API fulltext_file URL (most reliable for text)
            if not content:
                try:
                    print(f"  Trying JSON API to get fulltext_file URL...")
                    api_url = url.rstrip('/') + '/?fo=json'
                    api_response = self._fetch_with_retry(api_url)
                    if api_response.headers.get('content-type', '').startswith('application/json'):
                        api_data = api_response.json()
                        
                        # Look for fulltext_file URL in multiple places
                        fulltext_file = None
                        
                        # Check resources array
                        resources = api_data.get('resources', [])
                        if not resources:
                            # Try item.resources
                            item = api_data.get('item', {})
                            resources = item.get('resources', [])
                        
                        for resource in resources:
                            fulltext_file = resource.get('fulltext_file')
                            if fulltext_file and '.txt' in fulltext_file:
                                break
                        
                        # Also check resource object directly
                        if not fulltext_file:
                            resource_obj = api_data.get('resource', {})
                            if resource_obj:
                                fulltext_file = resource_obj.get('fulltext_file')
                        
                        if fulltext_file and '.txt' in fulltext_file:
                            print(f"  Found fulltext_file URL: {fulltext_file}")
                            # Download the text file directly
                            # Extract ID from URL (e.g., mal.4361800 from https://www.loc.gov/resource/mal.4361800/)
                            url_parts = url.rstrip('/').split('/')
                            url_part = url_parts[-1] if url_parts[-1] else url_parts[-2]
                            url_part = url_part.replace('.html', '').replace('/', '_')
                            if not url_part or url_part == 'loc':
                                # Try to extract from fulltext_file URL itself
                                import re
                                match = re.search(r'mal[.\d]+', fulltext_file)
                                if match:
                                    url_part = match.group()
                            text_path = self.output_dir / f"loc_{url_part}.txt"
                            
                            if self.download_file(fulltext_file, text_path):
                                content = text_path.read_text(encoding='utf-8', errors='ignore')
                                if content and len(content) > 50:
                                    file_format_used = 'text'
                                    print(f"  Downloaded text from fulltext_file ({len(content)} chars)")
                                    
                                    # Also get title from JSON
                                    item = api_data.get('item', {})
                                    if item:
                                        title = item.get('title', title)
                except Exception as e:
                    print(f"  JSON API fulltext_file method failed: {e}")
            
            # Final fallback: Try HTML extraction
            if not content:
                try:
                    response = self._fetch_with_retry(url)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    if not title or title == "Untitled Document":
                        title_elem = soup.find('h1') or soup.find('title')
                        title = title_elem.text.strip() if title_elem else "Untitled Document"
                    
                    # Try to extract from page
                    content = self._extract_content_from_page(soup)
                    file_format_used = 'html'
                except Exception as e:
                    print(f"  HTML extraction also failed: {e}")
            
            # Extract metadata
            if self.driver:
                try:
                    page_source = self.driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                except:
                    soup = None
            else:
                try:
                    response = self._fetch_with_retry(url)
                    soup = BeautifulSoup(response.content, 'html.parser')
                except:
                    soup = None
            
            metadata = self.extract_metadata(soup, url) if soup else {
                'date': None, 'place': None, 'from': None, 'to': None, 'document_type': None
            }
            
            # Save raw text file
            if content:
                url_part = url.split('/')[-1].replace('.html', '').replace('/', '_')
                text_output = self.output_dir / f"loc_{url_part}.txt"
                text_output.write_text(content, encoding='utf-8')
                print(f"  Saved text content to: {text_output}")
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'file_format': file_format_used,
                **metadata
            }
            
        except Exception as e:
            print(f"  Error scraping {url}: {type(e).__name__}: {str(e)[:100]}")
            return None
    
    def _extract_text_from_text_view(self, soup: BeautifulSoup) -> str:
        """Extract text content from text-with-images view."""
        # Look for transcription/text content in text view mode
        text_selectors = [
            '.transcription',
            '.text-content',
            '.text-view',
            '[itemprop="text"]',
            '.item-description',
            '.document-text',
            '.manuscript-text',
            'main',
            'article',
            # Look for divs containing transcribed text
            'div[class*="text"]',
            'div[class*="transcript"]',
            'div[class*="content"]'
        ]
        
        for selector in text_selectors:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(separator='\n', strip=True)
                    # Filter out navigation and UI text
                    if len(text) > 200 and not any(skip in text.lower() for skip in ['menu', 'navigation', 'skip to', 'cookie']):
                        return text
            except:
                continue
        
        # Look for pre-formatted text blocks (common in text views)
        pre_blocks = soup.find_all('pre')
        if pre_blocks:
            text = '\n'.join([pre.get_text(strip=True) for pre in pre_blocks])
            if len(text) > 100:
                return text
        
        # Get all text but filter out common UI elements
        all_text = soup.get_text(separator='\n', strip=True)
        # Split into lines and filter
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        # Remove short lines that are likely UI elements
        filtered_lines = [line for line in lines if len(line) > 10 and not any(
            skip in line.lower() for skip in ['cookie', 'menu', 'skip', 'navigation', 'back to top']
        )]
        
        return '\n'.join(filtered_lines)
    
    def _extract_content_from_page(self, soup: BeautifulSoup) -> str:
        """Extract text content from HTML page as fallback."""
        # First try the text view extraction method
        text = self._extract_text_from_text_view(soup)
        if text and len(text) > 100:
            return text
        
        # Fallback: look for transcription areas
        content_selectors = [
            '.transcription',
            '.text-content',
            '[itemprop="text"]',
            '.item-description',
            'main',
            'article'
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator='\n', strip=True)
                if len(text) > 100:
                    return text
        
        # Fallback: get all paragraph text
        paragraphs = soup.find_all('p')
        text = '\n'.join([p.get_text(strip=True) for p in paragraphs])
        return text
    
    def scrape_all_documents(self, urls: List[str]) -> List[Dict]:
        """Scrape multiple documents."""
        results = []
        
        try:
            for url in tqdm(urls, desc="Scraping LoC documents"):
                doc_data = self.scrape_document(url)
                if doc_data:
                    results.append(doc_data)
                time.sleep(2)  # Be respectful
        finally:
            # Clean up Selenium driver
            if self.driver:
                self.driver.quit()
        
        return results


if __name__ == "__main__":
    scraper = LoCScraperImproved()
    
    loc_urls = [
        "https://www.loc.gov/item/mal0440500/",  # Election night 1860
        "https://www.loc.gov/resource/mal.0882800",  # Fort Sumter Decision
        "https://www.loc.gov/exhibits/gettysburg-address/ext/trans-nicolay-copy.html",  # Gettysburg Address
        "https://www.loc.gov/resource/mal.4361300",  # Second Inaugural Address
        "https://www.loc.gov/resource/mal.4361800/",  # Last Public Address
    ]
    
    print("=" * 70)
    print("Improved LoC Scraper - Testing")
    print("=" * 70)
    
    documents = scraper.scrape_all_documents(loc_urls)
    
    print(f"\n{'='*70}")
    print(f"Successfully scraped {len(documents)} out of {len(loc_urls)} documents")
    print(f"{'='*70}")

