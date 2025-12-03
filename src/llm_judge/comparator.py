"""
Comparator

Groups extractions by event and matches Lincoln's accounts with others' accounts
for comparison by the LLM Judge.
"""

from typing import List, Dict, Tuple
from collections import defaultdict


class ExtractionComparator:
    """
    Groups and matches extractions for comparison.
    
    For each event, finds:
    - Lincoln's accounts (from LoC documents)
    - Other authors' accounts (from Gutenberg books)
    - Creates pairs for comparison
    """
    
    def __init__(self, extractions: List[Dict]):
        """
        Initialize with extractions from Part 2.
        
        Args:
            extractions: List of extraction dictionaries from event_extractions.json
        """
        self.extractions = extractions
    
    def group_by_event(self) -> Dict[str, List[Dict]]:
        """
        Group extractions by event ID.
        
        Returns:
            Dictionary mapping event_id -> list of extractions
        """
        grouped = defaultdict(list)
        for extraction in self.extractions:
            event_id = extraction.get('event')
            if event_id:
                grouped[event_id].append(extraction)
        return dict(grouped)
    
    def separate_lincoln_and_others(self, event_extractions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Separate Lincoln's accounts from others' accounts.
        
        Args:
            event_extractions: List of extractions for a specific event
            
        Returns:
            Tuple of (lincoln_extractions, other_extractions)
        """
        lincoln_extractions = []
        other_extractions = []
        
        for extraction in event_extractions:
            author = extraction.get('author', '').lower()
            if 'lincoln' in author or 'abraham lincoln' in author:
                lincoln_extractions.append(extraction)
            else:
                other_extractions.append(extraction)
        
        return lincoln_extractions, other_extractions
    
    def create_comparison_pairs(self) -> List[Dict]:
        """
        Create pairs of (Lincoln account, Other account) for each event.
        
        Returns:
            List of dictionaries with:
            - event_id
            - event_name
            - lincoln_extraction
            - other_extraction
            - lincoln_source
            - other_source
        """
        grouped = self.group_by_event()
        pairs = []
        
        # Event name mapping
        event_names = {
            'election_night_1860': 'Election Night 1860',
            'fort_sumter': 'Fort Sumter Decision',
            'gettysburg_address': 'Gettysburg Address',
            'second_inaugural': 'Second Inaugural Address',
            'fords_theatre': "Ford's Theatre Assassination"
        }
        
        for event_id, extractions in grouped.items():
            lincoln_extractions, other_extractions = self.separate_lincoln_and_others(extractions)
            event_name = event_names.get(event_id, event_id.replace('_', ' ').title())
            
            # Create pairs: each Lincoln extraction vs each other extraction
            for lincoln_ext in lincoln_extractions:
                for other_ext in other_extractions:
                    # Only create pair if both have claims
                    if lincoln_ext.get('claims') and other_ext.get('claims'):
                        pairs.append({
                            'event_id': event_id,
                            'event_name': event_name,
                            'lincoln_extraction': lincoln_ext,
                            'other_extraction': other_ext,
                            'lincoln_source': lincoln_ext.get('source_document', 'Unknown'),
                            'other_source': other_ext.get('source_document', 'Unknown'),
                            'lincoln_author': lincoln_ext.get('author', 'Abraham Lincoln'),
                            'other_author': other_ext.get('author', 'Unknown')
                        })
        
        return pairs


