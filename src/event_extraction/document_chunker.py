"""
Document Chunker

Handles splitting long documents into manageable chunks for LLM processing.
Books are too long for single LLM calls, so we need to:
1. Split documents into chunks
2. Search for relevant chunks containing event information
3. Process only relevant chunks to save tokens and improve quality
"""

from typing import List, Dict
import re
from pathlib import Path


class DocumentChunker:
    """
    Splits documents into chunks and helps find relevant sections.
    
    Strategy:
    - Split by paragraphs (preserve context)
    - Use overlapping windows to avoid cutting mid-sentence
    - Search chunks for event keywords before processing
    """
    
    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        """
        Initialize the chunker.
        
        Args:
            chunk_size: Target characters per chunk
            overlap: Characters to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_document(self, text: str, document_id: str) -> List[Dict]:
        """
        Split a document into chunks.
        
        Args:
            text: Full document text
            document_id: ID of the document
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or len(text) < self.chunk_size:
            return [{
                'chunk_id': f"{document_id}_chunk_0",
                'text': text,
                'start_char': 0,
                'end_char': len(text),
                'chunk_index': 0
            }]
        
        chunks = []
        # Split by paragraphs first (preserve context)
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = ""
        chunk_start = 0
        chunk_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If adding this paragraph would exceed chunk size, save current chunk
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                chunks.append({
                    'chunk_id': f"{document_id}_chunk_{chunk_index}",
                    'text': current_chunk.strip(),
                    'start_char': chunk_start,
                    'end_char': chunk_start + len(current_chunk),
                    'chunk_index': chunk_index
                })
                
                # Start new chunk with overlap
                overlap_text = current_chunk[-self.overlap:] if len(current_chunk) > self.overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + para
                chunk_start = chunk_start + len(current_chunk) - len(overlap_text) - len(para) - 2
                chunk_index += 1
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                'chunk_id': f"{document_id}_chunk_{chunk_index}",
                'text': current_chunk.strip(),
                'start_char': chunk_start,
                'end_char': chunk_start + len(current_chunk),
                'chunk_index': chunk_index
            })
        
        return chunks
    
    def find_relevant_chunks(self, chunks: List[Dict], event_keywords: List[str]) -> List[Dict]:
        """
        Filter chunks that likely contain information about an event.
        
        Args:
            chunks: List of chunk dictionaries
            event_keywords: Keywords to search for
            
        Returns:
            Filtered list of chunks containing keywords
        """
        relevant = []
        keywords_lower = [kw.lower() for kw in event_keywords]
        
        # Also create partial keyword matches (e.g., "election" matches "election night")
        partial_keywords = []
        for kw in keywords_lower:
            # Split compound keywords and add individual words
            words = kw.split()
            partial_keywords.extend(words)
            # Add the full keyword
            partial_keywords.append(kw)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in partial_keywords:
            if kw not in seen and len(kw) > 3:  # Only words longer than 3 chars
                seen.add(kw)
                unique_keywords.append(kw)
        
        for chunk in chunks:
            text_lower = chunk['text'].lower()
            # Check if any keyword appears in this chunk (more lenient matching)
            if any(keyword in text_lower for keyword in unique_keywords):
                relevant.append(chunk)
        
        return relevant
    
    def combine_chunks(self, chunks: List[Dict], max_length: int = 8000) -> str:
        """
        Combine multiple chunks into a single text, respecting max length.
        
        Args:
            chunks: List of chunk dictionaries
            max_length: Maximum total length
            
        Returns:
            Combined text
        """
        combined = ""
        for chunk in chunks:
            if len(combined) + len(chunk['text']) > max_length:
                break
            combined += "\n\n---\n\n" + chunk['text'] if combined else chunk['text']
        
        return combined

