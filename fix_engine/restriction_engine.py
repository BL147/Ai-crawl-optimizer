"""Main orchestrator for Phase 3 AI Restriction / Reverse Fix Engine."""

from typing import Any, Dict, List, Optional

from fix_engine.models import TestEnvironment
from fix_engine.registry import TestEnvironmentRegistry, get_default_registry
from fix_engine.restriction_handlers import (
    apply_robots_restriction,
    apply_simulation_restriction,
    remove_robots_restriction,
    remove_simulation_restriction,
)
from fix_engine.restriction_models import (
    RESTRICTION_ALIASES,
    RESTRICTION_CATALOG,
    RestrictionCapability,
    RestrictionCategory,
    RestrictionResult,
    RestrictionStatus,
)


class RestrictionEngine:
    """
    Orchestrates applying and removing AI crawl restrictions on registered test environments.
    Strictly preserves allowlist security and idempotency.
    """

    def __init__(self, registry: Optional[TestEnvironmentRegistry] = None) -> None:
        self.registry = registry if registry is not None else get_default_registry()

    def get_supported_restrictions(self) -> List[str]:
        """Return list of supported automated restriction identifiers."""
        return [
            cat for cat, defn in RESTRICTION_CATALOG.items()
            if defn.capability == RestrictionCapability.SUPPORTED_CONTROLLED_FIX
        ]

    def get_recommendation_only_restrictions(self) -> List[str]:
        """Return list of recommendation-only restriction identifiers."""
        return [
            cat for cat, defn in RESTRICTION_CATALOG.items()
            if defn.capability == RestrictionCapability.RECOMMENDATION_ONLY
        ]

    def apply_restriction(
        self,
        control_id: str,
        target: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> RestrictionResult:
        """
        Safely apply an AI restriction to an approved local test environment.
        """
        options = options or {}
        personas = options.get("personas", ["gptbot"])

        if not control_id or not isinstance(control_id, str):
            return RestrictionResult(
                control_id=str(control_id),
                status=RestrictionStatus.UNSUPPORTED.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message="A valid control_id string must be provided.",
            )

        norm_id = control_id.strip().lower()
        canonical_cat = RESTRICTION_ALIASES.get(norm_id, norm_id)

        if canonical_cat not in RESTRICTION_CATALOG:
            return RestrictionResult(
                control_id=control_id,
                status=RestrictionStatus.UNSUPPORTED.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message=(
                    f"Unsupported restriction '{control_id}'. Supported controls: "
                    f"{', '.join(sorted(RESTRICTION_CATALOG.keys()))}."
                ),
            )

        defn = RESTRICTION_CATALOG[canonical_cat]

        # Recommendation-only controls cannot and should not be modified automatically
        if defn.capability == RestrictionCapability.RECOMMENDATION_ONLY:
            return RestrictionResult(
                control_id=canonical_cat,
                status=RestrictionStatus.RECOMMENDATION_ONLY.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message=(
                    f"Control '{defn.title}' is a recommendation-only control and cannot be automatically applied "
                    "to a local server. Review implementation steps."
                ),
                capability=RestrictionCapability.RECOMMENDATION_ONLY.value,
                implementation_steps=defn.recommendation_steps,
            )

        # Validate target against explicit security allowlist
        env = self.registry.get(target)
        if env is None:
            return RestrictionResult(
                control_id=canonical_cat,
                status=RestrictionStatus.TARGET_NOT_ALLOWED.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message=(
                    f"Target '{target}' is not an approved local test environment. "
                    "Restrictions cannot be applied to external domains or unregistered environments."
                ),
            )

        # Dispatch to handler
        if canonical_cat == RestrictionCategory.AI_ROBOTS_RESTRICTION.value:
            return apply_robots_restriction(env, personas=personas, options=options)
        elif canonical_cat == RestrictionCategory.AI_RATE_LIMIT.value:
            return apply_simulation_restriction(env, "rate_limit", personas=personas, options=options)
        elif canonical_cat == RestrictionCategory.AI_WAF_CHALLENGE.value:
            return apply_simulation_restriction(env, "waf_challenge", personas=personas, options=options)
        elif canonical_cat == RestrictionCategory.AI_CAPTCHA.value:
            return apply_simulation_restriction(env, "captcha", personas=personas, options=options)
        else:
            return RestrictionResult(
                control_id=canonical_cat,
                status=RestrictionStatus.UNSUPPORTED.value,
                target=env.id,
                personas=personas,
                message=f"No execution handler registered for '{canonical_cat}'.",
            )

    def remove_restriction(
        self,
        control_id: str,
        target: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> RestrictionResult:
        """
        Safely remove an AI restriction from an approved local test environment (Reversibility).
        """
        options = options or {}
        personas = options.get("personas", ["gptbot"])

        if not control_id or not isinstance(control_id, str):
            return RestrictionResult(
                control_id=str(control_id),
                status=RestrictionStatus.UNSUPPORTED.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message="A valid control_id string must be provided.",
            )

        norm_id = control_id.strip().lower()
        canonical_cat = RESTRICTION_ALIASES.get(norm_id, norm_id)

        if canonical_cat not in RESTRICTION_CATALOG:
            return RestrictionResult(
                control_id=control_id,
                status=RestrictionStatus.UNSUPPORTED.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message=f"Unsupported restriction '{control_id}'.",
            )

        defn = RESTRICTION_CATALOG[canonical_cat]
        if defn.capability == RestrictionCapability.RECOMMENDATION_ONLY:
            return RestrictionResult(
                control_id=canonical_cat,
                status=RestrictionStatus.RECOMMENDATION_ONLY.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message=f"Control '{defn.title}' is recommendation-only.",
                capability=RestrictionCapability.RECOMMENDATION_ONLY.value,
                implementation_steps=defn.recommendation_steps,
            )

        env = self.registry.get(target)
        if env is None:
            return RestrictionResult(
                control_id=canonical_cat,
                status=RestrictionStatus.TARGET_NOT_ALLOWED.value,
                target=str(target),
                personas=personas,
                files_changed=[],
                message=f"Target '{target}' is not an approved local test environment.",
            )

        # Dispatch removal
        if canonical_cat == RestrictionCategory.AI_ROBOTS_RESTRICTION.value:
            return remove_robots_restriction(env, personas=personas, options=options)
        elif canonical_cat == RestrictionCategory.AI_RATE_LIMIT.value:
            return remove_simulation_restriction(env, "rate_limit", personas=personas, options=options)
        elif canonical_cat == RestrictionCategory.AI_WAF_CHALLENGE.value:
            return remove_simulation_restriction(env, "waf_challenge", personas=personas, options=options)
        elif canonical_cat == RestrictionCategory.AI_CAPTCHA.value:
            return remove_simulation_restriction(env, "captcha", personas=personas, options=options)
        else:
            return RestrictionResult(
                control_id=canonical_cat,
                status=RestrictionStatus.UNSUPPORTED.value,
                target=env.id,
                personas=personas,
                message=f"No removal handler registered for '{canonical_cat}'.",
            )


# =============================================================================
# Public Convenience APIs
# =============================================================================

def apply_restriction(
    control_id: str,
    target: str,
    options: Optional[Dict[str, Any]] = None,
    registry: Optional[TestEnvironmentRegistry] = None,
) -> Dict[str, Any]:
    """
    Public convenience API for Phase 3:
    Applies the specified restriction to an approved target environment.
    """
    engine = RestrictionEngine(registry=registry)
    result = engine.apply_restriction(control_id, target, options=options)
    return result.to_dict()


def remove_restriction(
    control_id: str,
    target: str,
    options: Optional[Dict[str, Any]] = None,
    registry: Optional[TestEnvironmentRegistry] = None,
) -> Dict[str, Any]:
    """
    Public convenience API for Phase 3:
    Removes the specified restriction from an approved target environment (Reversibility).
    """
    engine = RestrictionEngine(registry=registry)
    result = engine.remove_restriction(control_id, target, options=options)
    return result.to_dict()
