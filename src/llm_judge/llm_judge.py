"""
LLM Judge

Uses LLMs to compare two accounts of the same event and evaluate consistency.
Uses instructor library with Pydantic models for type-safe structured outputs.
"""

import os
import time
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# Try to import OpenAI and instructor
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

# Import our Pydantic models
try:
    from .models import JudgeResult, ContradictionClassification
except ImportError:
    import sys
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    sys.path.insert(0, str(project_root))
    from src.llm_judge.models import JudgeResult, ContradictionClassification

# Load .env from project root
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)


class LLMJudge:
    """
    LLM Judge that compares two accounts of the same event.
    
    Uses instructor for structured, validated outputs with Pydantic models.
    """
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """
        Initialize the LLM Judge.
        
        Args:
            model: Model name (e.g., "gpt-4o-mini", "gpt-4")
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
                print("Warning: OpenAI library not installed.")
            if not INSTRUCTOR_AVAILABLE:
                print("Warning: instructor library not installed.")
            if not self.api_key:
                print("Warning: OPENAI_API_KEY not set.")
    
    def _load_prompt_template(self) -> str:
        """Load the judge prompt template from file."""
        script_dir = Path(__file__).parent
        prompt_file = script_dir / "judge_prompt.txt"
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_file}\n"
                "Please ensure judge_prompt.txt exists in src/llm_judge/"
            )
    
    def _format_claims(self, claims: list) -> str:
        """Format claims list for prompt."""
        if not claims:
            return "None provided"
        return "\n".join(f"- {claim}" for claim in claims)
    
    def _format_temporal(self, temporal_details: dict) -> str:
        """Format temporal details for prompt."""
        date = temporal_details.get('date', 'Not mentioned')
        time_str = temporal_details.get('time', 'Not mentioned')
        return f"Date: {date}, Time: {time_str}"
    
    def compare_accounts(self,
                        event_name: str,
                        lincoln_extraction: Dict,
                        other_extraction: Dict) -> Optional[JudgeResult]:
        """
        Compare two accounts of the same event using LLM Judge.
        
        Args:
            event_name: Name of the event being compared
            lincoln_extraction: Extraction from Lincoln's account (from Part 2)
            other_extraction: Extraction from another author's account (from Part 2)
            
        Returns:
            JudgeResult with consistency score and contradiction classification, or None if failed
        """
        if not self.client:
            print(f"  [SKIP] LLM client not available. Set OPENAI_API_KEY in .env file")
            return None
        
        # Extract information from extractions
        lincoln_author = lincoln_extraction.get('author', 'Abraham Lincoln')
        lincoln_claims = lincoln_extraction.get('claims', [])
        lincoln_temporal = lincoln_extraction.get('temporal_details', {})
        lincoln_tone = lincoln_extraction.get('tone', 'Unknown')
        
        other_author = other_extraction.get('author', 'Unknown')
        other_claims = other_extraction.get('claims', [])
        other_temporal = other_extraction.get('temporal_details', {})
        other_tone = other_extraction.get('tone', 'Unknown')
        
        # Load and format prompt
        template = self._load_prompt_template()
        prompt = template.format(
            event_name=event_name,
            lincoln_author=lincoln_author,
            lincoln_claims=self._format_claims(lincoln_claims),
            lincoln_temporal=self._format_temporal(lincoln_temporal),
            lincoln_tone=lincoln_tone,
            other_author=other_author,
            other_claims=self._format_claims(other_claims),
            other_temporal=self._format_temporal(other_temporal),
            other_tone=other_tone
        )
        
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Use instructor to get structured, validated output
                result: JudgeResult = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert historian evaluating historiographical divergence between accounts of historical events. Be objective, fair, and focus on factual consistency."},
                        {"role": "user", "content": prompt}
                    ],
                    response_model=JudgeResult,  # Instructor validates against Pydantic model
                    temperature=0.3,  # Lower temperature for more consistent judgments
                )
                
                return result
                
            except Exception as e:
                error_str = str(e)
                # Check if it's a rate limit error (429)
                if 'rate_limit' in error_str.lower() or '429' in error_str or 'rate limit' in error_str.lower():
                    if attempt < max_retries - 1:
                        # Extract wait time from error if available
                        wait_time = retry_delay * (2 ** attempt)
                        if 'try again in' in error_str.lower():
                            try:
                                import re
                                wait_match = re.search(r'try again in ([\d.]+)([sm]?)', error_str.lower())
                                if wait_match:
                                    wait_val = float(wait_match.group(1))
                                    unit = wait_match.group(2)
                                    wait_time = wait_val if unit == 's' else wait_val / 1000
                                    wait_time = max(wait_time, 0.5)
                            except:
                                pass
                        
                        time.sleep(wait_time)
                        continue
                    else:
                        return None
                else:
                    if attempt == 0:
                        print(f"  [ERROR] Judge comparison failed: {type(e).__name__}")
                    return None
        
        return None


