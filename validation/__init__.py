"""
validation/__init__.py - AI Crawl Optimizer Fix Validation Engine Module
Author: Shlok (System Integrator)
"""

from validation.models import (
    FixStatus,
    IssueCategory,
    TargetIssue,
    ValidationResult,
    ValidationStatus,
)
from validation.engine import FixValidationEngine


def validate_fix(
    target_url: str,
    target_issue=None,
    fix_action=None,
    persona: str = "gptbot",
    audit_before=None,
    audit_after=None,
    fix_status: str = None,
    **crawl_options,
) -> ValidationResult:
    """Convenience functional wrapper for end-to-end fix validation."""
    return FixValidationEngine.validate_fix(
        target_url=target_url,
        target_issue=target_issue,
        fix_action=fix_action,
        persona=persona,
        audit_before=audit_before,
        audit_after=audit_after,
        fix_status=fix_status,
        **crawl_options,
    )


def compare_and_validate(
    audit_before,
    audit_after,
    target_issue=None,
    fix_status: str = "APPLIED",
    timestamp: str = None,
) -> ValidationResult:
    """Convenience functional wrapper for pure audit snapshot comparison."""
    return FixValidationEngine.validate_comparison(
        audit_before=audit_before,
        audit_after=audit_after,
        target_issue=target_issue,
        fix_status=fix_status,
        timestamp=timestamp,
    )


__all__ = [
    "FixValidationEngine",
    "ValidationStatus",
    "ValidationResult",
    "TargetIssue",
    "IssueCategory",
    "FixStatus",
    "validate_fix",
    "compare_and_validate",
]
