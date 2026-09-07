"""
validation/models.py - Data Models for Phase 2 Fix Validation Engine
Author: Shlok (System Integrator)
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """Possible outcomes of an issue-specific fix validation."""
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class FixStatus(str, Enum):
    """Status of fix execution or application by the Fix Application Engine."""
    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    ERROR = "ERROR"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNKNOWN = "UNKNOWN"
    # Aliases for backwards compatibility
    FAILED_TO_APPLY = "FAILED_TO_APPLY"
    NO_CHANGE = "NO_CHANGE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class IssueCategory(str, Enum):
    """Categories of crawlability issues."""
    ROBOTS_TXT = "ROBOTS_TXT"
    WAF_CHALLENGE = "WAF_CHALLENGE"
    CAPTCHA = "CAPTCHA"
    HTTP_STATUS = "HTTP_STATUS"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER_ERROR = "SERVER_ERROR"
    LATENCY = "LATENCY"
    SELECTIVE_BLOCK = "SELECTIVE_BLOCK"
    AI_RESTRICTION = "AI_RESTRICTION"
    OTHER = "OTHER"


class TargetIssue(BaseModel):
    """
    Specification of the specific issue targeted for validation.
    """
    category: IssueCategory = IssueCategory.OTHER
    persona: Optional[str] = None
    expected_previous_state: Optional[str] = None
    expected_resolved_state: Optional[str] = None
    description: Optional[str] = None
    threshold: Optional[float] = None  # e.g., max acceptable latency in ms


class ValidationResult(BaseModel):
    """
    Standardized result contract for Phase 2 Fix Validation Engine.
    Guarantees the required fields:
    - before_score
    - after_score
    - score_delta
    - issue_before
    - issue_after
    - fix_status
    - validation_status
    - evidence
    - timestamp
    """
    before_score: int
    after_score: int
    score_delta: int
    issue_before: Union[str, Dict[str, Any]]
    issue_after: Union[str, Dict[str, Any]]
    fix_status: str
    validation_status: ValidationStatus
    evidence: List[str] = Field(default_factory=list)
    timestamp: str
    target_url: Optional[str] = None
    persona: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to clean JSON-serializable dictionary."""
        return self.model_dump(mode="json")

    def __getitem__(self, item: str) -> Any:
        """Allow dict-style key access (e.g. res['validation_status']) for cross-team compatibility."""
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        """Allow 'key in res' checks."""
        return hasattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        """Allow dict-style .get(key, default) access."""
        return getattr(self, item, default)
