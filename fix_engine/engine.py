"""Main Fix Application Engine orchestrator for Phase 2."""

from typing import Any, Callable, Dict, List, Optional

from fix_engine.latency_fix import apply_latency_fix
from fix_engine.models import FixResult, FixStatus, TestEnvironment
from fix_engine.registry import TestEnvironmentRegistry, get_default_registry
from fix_engine.robots_fix import apply_robots_fix

FixHandler = Callable[[TestEnvironment, str, Optional[str], Optional[Dict[str, Any]]], FixResult]


class FixApplicationEngine:
    """
    Orchestrates fix application across registered Phase 2 test environments.
    Strictly enforces allowlist security and deterministic transformations.
    """

    def __init__(self, registry: Optional[TestEnvironmentRegistry] = None) -> None:
        self.registry = registry if registry is not None else get_default_registry()
        self._handlers: Dict[str, FixHandler] = {
            "robots_txt": apply_robots_fix,
            "robots": apply_robots_fix,
            "robots_allow_ai": apply_robots_fix,
            "allow_ai_bots": apply_robots_fix,
            "allow_ai_crawlers": apply_robots_fix,
            "latency": apply_latency_fix,
            "performance": apply_latency_fix,
            "reduce_latency": apply_latency_fix,
            "simulated_latency": apply_latency_fix,
        }

    def get_supported_fixes(self) -> List[str]:
        """Return list of canonical supported fix identifiers."""
        return ["robots_txt", "latency"]

    def apply_fix(
        self,
        fix_id: str,
        target: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> FixResult:
        """
        Safely apply a supported fix to a registered local test environment.
        """
        if not fix_id or not isinstance(fix_id, str):
            return FixResult(
                fix_id=str(fix_id),
                status=FixStatus.UNSUPPORTED_FIX.value,
                target=str(target),
                files_changed=[],
                message="A valid fix_id string must be provided.",
            )

        norm_fix_id = fix_id.strip().lower()
        if norm_fix_id not in self._handlers:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.UNSUPPORTED_FIX.value,
                target=str(target),
                files_changed=[],
                message=(
                    f"Unsupported fix '{fix_id}'. Supported fixes: "
                    f"{', '.join(self.get_supported_fixes())}."
                ),
            )

        # Validate target against explicit security allowlist
        env = self.registry.get(target)
        if env is None:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.TARGET_NOT_ALLOWED.value,
                target=str(target),
                files_changed=[],
                message=(
                    f"Target '{target}' is not an approved local test environment. "
                    "Modifications to external domains or unregistered environments are strictly prohibited."
                ),
            )

        # Dispatch to handler
        handler = self._handlers[norm_fix_id]
        return handler(env, fix_id, target, options)


def apply_fix(
    fix_id: str,
    target: str,
    options: Optional[Dict[str, Any]] = None,
    registry: Optional[TestEnvironmentRegistry] = None,
) -> Dict[str, Any]:
    """
    Public convenience API for Phase 2:
    Applies the specified fix to the approved target environment and returns
    a JSON-serializable dictionary adhering to the required project schema.
    """
    engine = FixApplicationEngine(registry=registry)
    result = engine.apply_fix(fix_id, target, options=options)
    return result.to_dict()
