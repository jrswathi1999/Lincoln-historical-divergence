"""
LLM Event Extractor

Uses LLMs to extract event information from document chunks.
Uses instructor library with Pydantic models for type-safe structured outputs.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Try to import OpenAI and instructor, but handle gracefully if not available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI not installed. Install with: pip install openai")

try:
    import instructor
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    print("Warning: instructor not installed. Install with: pip install instructor")

# Load .env from project root
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Import our Pydantic models
# Handle import path - try relative first, then absolute
try:
    from .models import EventExtraction
except ImportError:
    # Fallback for when running as script
    import sys
    sys.path.insert(0, str(project_root))
    from src.event_extraction.models import EventExtraction


class LLMEventExtractor:
    """
    Extracts event information using LLM.
    
    This class:
    1. Takes document chunks and event information
    2. Sends prompts to LLM
    3. Parses structured JSON responses
    4. Handles errors and retries
    """
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """
        Initialize the LLM extractor with instructor support.
        
        Args:
            model: Model name (e.g., "gpt-4o-mini", "gpt-4", "claude-3-sonnet")
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
        """
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if OPENAI_AVAILABLE and INSTRUCTOR_AVAILABLE and self.api_key:
            # Create OpenAI client and patch it with instructor
            base_client = OpenAI(api_key=self.api_key)
            self.client = instructor.patch(base_client)
        else:
            self.client = None
            if not OPENAI_AVAILABLE:
                print("Warning: OpenAI library not installed. Install with: pip install openai")
            if not INSTRUCTOR_AVAILABLE:
                print("Warning: instructor library not installed. Install with: pip install instructor")
            if not self.api_key:
                print("Warning: OPENAI_API_KEY not set. Set it in .env file or environment.")
    
    def extract_event_info(self, 
                          chunk_text: str, 
                          event_id: str, 
                          event_name: str,
                          document_title: str,
                          author: str) -> Optional[Dict]:
        """
        Extract event information from a document chunk using instructor.
        
        Uses Pydantic models for type-safe, validated outputs. Instructor handles
        retries automatically if the LLM returns malformed JSON.
        
        Args:
            chunk_text: Text chunk to analyze
            event_id: Event identifier (e.g., "fort_sumter")
            event_name: Human-readable event name
            document_title: Title of the source document
            author: Author of the document
            
        Returns:
            Dictionary with extracted information, or None if extraction fails
        """
        if not self.client:
            print(f"  [SKIP] LLM client not available. Set OPENAI_API_KEY in .env file")
            return None
        
        prompt = self._build_extraction_prompt(
            chunk_text, event_id, event_name, document_title, author
        )
        
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Use instructor to get structured, validated output
                extraction: EventExtraction = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert historian extracting structured information from historical texts."},
                        {"role": "user", "content": prompt}
                    ],
                    response_model=EventExtraction,  # Instructor validates against Pydantic model
                    temperature=0.3,  # Lower temperature for more consistent extraction
                )
                
                # Ensure event and author are set correctly (they should be from prompt, but double-check)
                extraction.event = event_id
                extraction.author = author
                
                # Convert Pydantic model to dict for backward compatibility
                result = extraction.model_dump()
                
                # Add source document for reference (not in requirements but useful)
                result['source_document'] = document_title
                
                return result
                
            except Exception as e:
                error_str = str(e)
                # Check if it's a rate limit error (429)
                if 'rate_limit' in error_str.lower() or '429' in error_str or 'rate limit' in error_str.lower():
                    if attempt < max_retries - 1:
                        # Extract wait time from error if available, otherwise use exponential backoff
                        wait_time = retry_delay * (2 ** attempt)
                        # Try to extract wait time from error message
                        if 'try again in' in error_str.lower():
                            try:
                                import re
                                wait_match = re.search(r'try again in ([\d.]+)([sm]?)', error_str.lower())
                                if wait_match:
                                    wait_val = float(wait_match.group(1))
                                    unit = wait_match.group(2)
                                    wait_time = wait_val if unit == 's' else wait_val / 1000
                                    wait_time = max(wait_time, 0.5)  # Minimum 0.5 seconds
                            except:
                                pass
                        
                        time.sleep(wait_time)
                        continue
                    else:
                        # Final attempt failed, return None
                        return None
                else:
                    # Not a rate limit error, don't retry
                    if attempt == 0:  # Only print error on first attempt
                        print(f"  [ERROR] LLM extraction failed: {type(e).__name__}")
                    return None
        
        return None
    
    def _load_prompt_template(self) -> str:
        """
        Load the prompt template from the separate prompt file.
        
        Returns:
            Prompt template string
        """
        script_dir = Path(__file__).parent
        prompt_file = script_dir / "extraction_prompt.txt"
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_file}\n"
                "Please ensure extraction_prompt.txt exists in src/event_extraction/"
            )
    
    def _build_extraction_prompt(self,
                                chunk_text: str,
                                event_id: str,
                                event_name: str,
                                document_title: str,
                                author: str) -> str:
        """
        Build the prompt for event extraction using the template file.
        
        This is a critical part - the prompt design determines extraction quality.
        Uses Chain-of-Thought reasoning to improve accuracy.
        
        Args:
            chunk_text: Text chunk to analyze
            event_id: Event identifier
            event_name: Human-readable event name
            document_title: Document title
            author: Author name
            
        Returns:
            Formatted prompt string
        """
        template = self._load_prompt_template()
        
        # Format the template with the provided variables
        prompt = template.format(
            event_id=event_id,
            event_name=event_name,
            document_title=document_title,
            author=author,
            chunk_text=chunk_text
        )
        
        return prompt
    
    def extract_from_document(self,
                            document_text: str,
                            document_id: str,
                            document_title: str,
                            author: str,
                            event_id: str,
                            event_name: str,
                            event_keywords: List[str]) -> List[Dict]:
        """
        Extract event information from an entire document.
        
        This method:
        1. Chunks the document
        2. Finds relevant chunks
        3. Extracts from relevant chunks
        4. Combines results
        
        Args:
            document_text: Full document text
            document_id: Document identifier
            document_title: Document title
            author: Author name
            event_id: Event identifier
            event_name: Event name
            event_keywords: Keywords to search for
            
        Returns:
            List of extraction results (one per relevant chunk)
        """
        import sys
        from pathlib import Path
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        sys.path.insert(0, str(project_root))
        from src.event_extraction.document_chunker import DocumentChunker
        
        chunker = DocumentChunker(chunk_size=2000, overlap=200)
        chunks = chunker.chunk_document(document_text, document_id)
        relevant_chunks = chunker.find_relevant_chunks(chunks, event_keywords)
        
        if not relevant_chunks:
            return []
        
        results = []
        total_chunks = len(relevant_chunks)
        
        for idx, chunk in enumerate(relevant_chunks, 1):
            if idx % 5 == 0 or idx == total_chunks:
                print(f"        Processing chunk {idx}/{total_chunks}...", end='\r')
            
            try:
                result = self.extract_event_info(
                    chunk['text'],
                    event_id,
                    event_name,
                    document_title,
                    author
                )
                if result and result.get('claims'):  # Only add if we found claims
                    results.append(result)
            except KeyboardInterrupt:
                print(f"\n        [INTERRUPTED] Stopping chunk processing...")
                raise
            except Exception as e:
                # Skip errors on individual chunks, continue processing
                continue
        
        if total_chunks > 0:
            print(f"        Processed {total_chunks} chunks" + " " * 20)  # Clear the progress line
        
        return results
    
    def extract_from_document_parallel(self,
                                      document_text: str,
                                      document_id: str,
                                      document_title: str,
                                      author: str,
                                      event_id: str,
                                      event_name: str,
                                      event_keywords: List[str],
                                      max_workers: int = 3) -> List[Dict]:
        """
        Extract event information from an entire document using parallel processing.
        
        This method processes chunks concurrently for much faster extraction.
        
        Args:
            document_text: Full document text
            document_id: Document identifier
            document_title: Document title
            author: Author name
            event_id: Event identifier
            event_name: Event name
            event_keywords: Keywords to search for
            max_workers: Number of concurrent workers (default: 3, balanced for speed and rate limits)
            
        Returns:
            List of extraction results (one per relevant chunk)
        """
        import sys
        from pathlib import Path
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        sys.path.insert(0, str(project_root))
        from src.event_extraction.document_chunker import DocumentChunker
        
        chunker = DocumentChunker(chunk_size=2000, overlap=200)
        chunks = chunker.chunk_document(document_text, document_id)
        relevant_chunks = chunker.find_relevant_chunks(chunks, event_keywords)
        
        if not relevant_chunks:
            return []
        
        results = []
        total_chunks = len(relevant_chunks)
        
        # Process chunks in parallel using ThreadPoolExecutor with rate limiting
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks in batches to avoid overwhelming the API
            batch_size = max_workers * 2  # Process in batches
            results = []
            completed = 0
            
            for batch_start in range(0, total_chunks, batch_size):
                batch_end = min(batch_start + batch_size, total_chunks)
                batch_chunks = relevant_chunks[batch_start:batch_end]
                
                # Submit batch
                future_to_chunk = {
                    executor.submit(
                        self.extract_event_info,
                        chunk['text'],
                        event_id,
                        event_name,
                        document_title,
                        author
                    ): (batch_start + idx + 1, chunk)
                    for idx, chunk in enumerate(batch_chunks)
                }
                
                # Process batch results
                for future in as_completed(future_to_chunk):
                    idx, chunk = future_to_chunk[future]
                    completed += 1
                    
                    # Update progress
                    if completed % 5 == 0 or completed == total_chunks:
                        print(f"        Processing chunk {completed}/{total_chunks}...", end='\r')
                    
                    try:
                        result = future.result()
                        if result and result.get('claims'):
                            results.append(result)
                    except KeyboardInterrupt:
                        print(f"\n        [INTERRUPTED] Stopping chunk processing...")
                        executor.shutdown(wait=False)
                        raise
                    except Exception as e:
                        # Skip errors on individual chunks, continue processing
                        continue
                
                # Small delay between batches to avoid rate limits
                if batch_end < total_chunks:
                    time.sleep(2.0)  # 2 second delay between batches to respect rate limits
        
        if total_chunks > 0:
            print(f"        Processed {total_chunks} chunks" + " " * 20)  # Clear the progress line
        
        return results

