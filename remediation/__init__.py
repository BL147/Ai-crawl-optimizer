"""AI Crawl Optimizer - Remediation Module.

Exports:
    generate_remediation: Primary entry point accepting crawler result and returning remediation dict.
    RemediationEngine: Core orchestrator class.
    RemediationResult: Structured result data model.
    BeforeAfterExample: Before-and-after configuration comparison model.
    normalize_crawler_result: Safe extractor for raw crawler results.
    NormalizedAudit: Normalized representation of facts and inferences.
    IssueType: Categorized crawl accessibility issues.
"""

from remediation.engine import RemediationEngine, generate_remediation
from remediation.models import BeforeAfterExample, RemediationResult
from remediation.normalizer import IssueType, NormalizedAudit, normalize_crawler_result

__all__ = [
    "generate_remediation",
    "RemediationEngine",
    "RemediationResult",
    "BeforeAfterExample",
    "normalize_crawler_result",
    "NormalizedAudit",
    "IssueType",
]
