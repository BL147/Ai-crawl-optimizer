"""Data models for AI remediation suggestions."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BeforeAfterExample:
    """Represents a before-and-after configuration comparison."""
    before: str = ""
    after: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"before": self.before, "after": self.after}


@dataclass
class RemediationResult:
    """Structured remediation response adhering to the AI Crawl Optimizer schema."""
    problem_detected: str
    evidence: List[str] = field(default_factory=list)
    why_it_affects_ai_crawling: str = ""
    recommended_fix: str = ""
    code_or_configuration_change: str = ""
    before_after_example: Dict[str, str] = field(default_factory=dict)
    validation_steps: List[str] = field(default_factory=list)
    uncertainty: str = ""
    observed_facts: Dict[str, Any] = field(default_factory=dict)
    raw_model_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a clean JSON-serializable dictionary for Streamlit UI or API consumers."""
        return {
            "problem_detected": self.problem_detected,
            "evidence": list(self.evidence),
            "why_it_affects_ai_crawling": self.why_it_affects_ai_crawling,
            "recommended_fix": self.recommended_fix,
            "code_or_configuration_change": self.code_or_configuration_change,
            "before_after_example": dict(self.before_after_example),
            "validation_steps": list(self.validation_steps),
            "uncertainty": self.uncertainty,
        }
