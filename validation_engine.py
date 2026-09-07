"""
validation_engine.py - Root convenience module for Phase 2 Fix Validation Engine
Author: Shlok (System Integrator)
"""

from validation import (
    FixValidationEngine,
    ValidationStatus,
    ValidationResult,
    TargetIssue,
    IssueCategory,
    FixStatus,
    validate_fix,
    compare_and_validate,
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
