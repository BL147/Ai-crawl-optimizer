"""Phase 2 & Phase 3 Fix & Restriction Engine for AI Crawl Optimizer."""

from fix_engine.engine import FixApplicationEngine, apply_fix
from fix_engine.models import FixResult, FixStatus, TestEnvironment
from fix_engine.registry import (
    TestEnvironmentRegistry,
    get_default_registry,
    reset_default_registry,
)
from fix_engine.restriction_engine import (
    RestrictionEngine,
    apply_restriction,
    remove_restriction,
)
from fix_engine.restriction_models import (
    RESTRICTION_CATALOG,
    RestrictionCapability,
    RestrictionCategory,
    RestrictionDefinition,
    RestrictionResult,
    RestrictionStatus,
)

__all__ = [
    "FixApplicationEngine",
    "FixResult",
    "FixStatus",
    "TestEnvironment",
    "TestEnvironmentRegistry",
    "apply_fix",
    "get_default_registry",
    "reset_default_registry",
    # Phase 3 Exports
    "RestrictionEngine",
    "RestrictionCategory",
    "RestrictionCapability",
    "RestrictionStatus",
    "RestrictionResult",
    "RestrictionDefinition",
    "RESTRICTION_CATALOG",
    "apply_restriction",
    "remove_restriction",
]
