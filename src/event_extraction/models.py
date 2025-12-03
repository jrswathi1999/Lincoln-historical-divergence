"""
Pydantic models for event extraction outputs.

These models define the structure of LLM responses using instructor/pydantic
for type safety and automatic validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class TemporalDetails(BaseModel):
    """Temporal information about an event."""
    date: Optional[str] = Field(
        default=None,
        description="Date mentioned in the text, if any"
    )
    time: Optional[str] = Field(
        default=None,
        description="Time mentioned in the text, if any"
    )


class EventExtraction(BaseModel):
    """
    Structured extraction of event information from a document chunk.
    
    This matches the exact format required by Part 2 specifications.
    """
    event: str = Field(
        description="Event identifier (e.g., 'fort_sumter', 'election_night_1860')"
    )
    author: str = Field(
        description="Author of the document"
    )
    claims: List[str] = Field(
        default_factory=list,
        description="List of factual claims made about the event. Empty list if event not found."
    )
    temporal_details: TemporalDetails = Field(
        default_factory=lambda: TemporalDetails(),
        description="Dates and times mentioned in relation to the event"
    )
    tone: Optional[str] = Field(
        default=None,
        description="Tone/attitude toward the event (e.g., 'Sympathetic', 'Critical', 'Neutral', 'Descriptive')"
    )


