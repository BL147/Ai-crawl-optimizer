"""Security allowlist and environment registry for Phase 2 test environments."""

import os
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fix_engine.models import TestEnvironment


class TestEnvironmentRegistry:
    """
    Explicit security registry managing allowed Phase 2 local test environments.
    Guarantees that no external URLs or arbitrary paths can be modified.
    """
    __test__ = False

    def __init__(self) -> None:
        self._environments: Dict[str, TestEnvironment] = {}

    def register(self, env: TestEnvironment) -> None:
        """Register an approved test environment."""
        self._environments[env.id] = env

    def unregister(self, env_id: str) -> Optional[TestEnvironment]:
        """Unregister an environment by ID."""
        return self._environments.pop(env_id, None)

    def is_allowed(self, target: str) -> bool:
        """Check whether a target (URL, ID, or path) is an approved test environment."""
        return self.get(target) is not None

    def get(self, target: str) -> Optional[TestEnvironment]:
        """
        Resolve a target identifier, URL, or local path to a registered TestEnvironment.
        Returns None if the target is external, unregistered, or disallowed.
        """
        if not target or not isinstance(target, str):
            return None

        clean_target = target.strip()
        if not clean_target:
            return None

        # 1. Check exact environment ID match
        if clean_target in self._environments:
            return self._environments[clean_target]

        # 2. Check URL match
        if clean_target.startswith("http://") or clean_target.startswith("https://"):
            parsed_target = urlparse(clean_target)
            target_host = (parsed_target.hostname or "").lower()
            target_port = parsed_target.port

            # Security check: Disallow external domains immediately
            if target_host not in {"localhost", "127.0.0.1", "0.0.0.0"}:
                return None

            for env in self._environments.values():
                if env.base_url:
                    parsed_base = urlparse(env.base_url)
                    base_host = (parsed_base.hostname or "").lower()
                    base_port = parsed_base.port

                    # Match host (treating localhost and 127.0.0.1 interchangeably) and port
                    hosts_match = (
                        target_host == base_host
                        or {target_host, base_host} <= {"localhost", "127.0.0.1"}
                    )
                    ports_match = (target_port == base_port)

                    if hosts_match and ports_match:
                        return env
            return None

        # 3. Check filesystem path match
        try:
            target_path = Path(clean_target).resolve()
            for env in self._environments.values():
                if target_path == env.root_dir or env._is_subpath(target_path, env.root_dir):
                    return env
        except Exception:
            pass

        return None

    def list_environments(self) -> List[Dict[str, str]]:
        """List summary of registered test environments."""
        return [
            {
                "id": env.id,
                "base_url": env.base_url or "N/A",
                "root_dir": str(env.root_dir),
                "description": env.description,
            }
            for env in self._environments.values()
        ]


_GLOBAL_REGISTRY: Optional[TestEnvironmentRegistry] = None


def get_default_registry() -> TestEnvironmentRegistry:
    """Retrieve or initialize the default global registry pre-populated with repo test environments."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        registry = TestEnvironmentRegistry()

        # Automatically register demo_streaming_site if present in workspace
        workspace_root = Path(__file__).resolve().parent.parent
        demo_site_dir = workspace_root / "demo_streaming_site"
        if demo_site_dir.is_dir():
            registry.register(
                TestEnvironment(
                    id="demo_streaming_site",
                    root_dir=demo_site_dir,
                    base_url="http://127.0.0.1:5050",
                    robots_path=demo_site_dir / "robots.txt",
                    config_path=demo_site_dir / "app.py",
                    description="CineStream Streaming Platform Demo Website",
                )
            )

        _GLOBAL_REGISTRY = registry
    return _GLOBAL_REGISTRY


def reset_default_registry() -> None:
    """Reset global registry (useful for test isolation)."""
    global _GLOBAL_REGISTRY
    _GLOBAL_REGISTRY = None
