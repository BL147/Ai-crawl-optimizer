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

    def format_markdown(self) -> str:
        """Format the remediation result into clean GitHub-flavored markdown."""
        evidence_md = "\n".join(f"- {e}" for e in self.evidence) if self.evidence else "- No specific evidence recorded."
        steps_md = "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.validation_steps)) if self.validation_steps else "1. Test with persona to verify resolution."
        
        # Determine code block language
        code = self.code_or_configuration_change or "# No configuration change required"
        code_lang = "nginx"
        if "<meta" in code or "<script" in code:
            code_lang = "html"
        elif "User-agent:" in code:
            code_lang = "robots.txt"
        elif "json" in code.lower() or code.strip().startswith("{"):
            code_lang = "json"

        # Format before/after
        before_str = ""
        after_str = ""
        if isinstance(self.before_after_example, dict):
            before_str = self.before_after_example.get("before", "")
            after_str = self.before_after_example.get("after", "")
        else:
            before_str = str(self.before_after_example)

        before_after_md = ""
        if before_str or after_str:
            before_after_md = f"**Before:**\n```\n{before_str}\n```\n\n**After:**\n```\n{after_str}\n```"
        else:
            before_after_md = "*(None applicable)*"

        uncertainty_section = ""
        if self.uncertainty:
            uncertainty_section = f"\n\n### ⚠️ Diagnostic Uncertainty / Gaps\n{self.uncertainty}"

        return f"""### 1. Problem Detected
{self.problem_detected}

### 2. Evidence
{evidence_md}

### 3. Why It Affects AI Crawling
{self.why_it_affects_ai_crawling}

### 4. Recommended Fix
{self.recommended_fix}

### 5. Exact Code / Configuration Change
```{code_lang}
{code}
```

### 6. Before / After Example
{before_after_md}

### 7. Validation Steps
{steps_md}{uncertainty_section}
"""
