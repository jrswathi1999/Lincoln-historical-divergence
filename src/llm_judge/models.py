"""
Pydantic models for LLM Judge outputs.

These models define the structure of judge responses using instructor/pydantic
for type safety and automatic validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class ContradictionClassification(BaseModel):
    """Classification of contradictions between accounts."""
    type: Literal["Factual", "Interpretive", "Omission", "None"] = Field(
        description="Type of contradiction: Factual (factual disagreement), Interpretive (different interpretation), Omission (missing information), or None (no contradiction)"
    )
    explanation: str = Field(
        description="Detailed explanation of the contradiction, or why there is no contradiction"
    )


class JudgeResult(BaseModel):
    """
    Result from LLM Judge comparing two accounts of the same event.
    
    This matches the Part 3 requirements for consistency scoring and contradiction classification.
    """
    consistency_score: int = Field(
        ge=0,
        le=100,
        description="Consistency score from 0-100, where 100 means perfectly consistent and 0 means completely contradictory"
    )
    contradiction_type: ContradictionClassification = Field(
        description="Classification of any contradictions found"
    )
    reasoning: str = Field(
        description="Detailed reasoning explaining the consistency score and contradiction classification"
    )
    key_differences: list[str] = Field(
        default_factory=list,
        description="List of key differences between the two accounts"
    )
    key_similarities: list[str] = Field(
        default_factory=list,
        description="List of key similarities between the two accounts"
    )


