"""Controlled response-header fix implementation for Phase 2 test environments."""

import re
from typing import Any, Dict, Optional

from fix_engine.models import FixResult, FixStatus, TestEnvironment


def apply_x_robots_tag_fix(
    env: TestEnvironment,
    fix_id: str = "x_robots_tag",
    target: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> FixResult:
    """Disable the demo's restrictive X-Robots-Tag configuration."""
    effective_target = target if target is not None else env.id
    config_path = env.config_path
    if config_path is None or not config_path.exists():
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message="No controlled environment configuration file found.",
        )

    resolved_config = config_path.resolve()
    if not env._is_subpath(resolved_config, env.root_dir):
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message="Security error: configuration path escapes the controlled environment.",
        )

    content = config_path.read_text(encoding="utf-8")
    pattern = r"(?m)^(BLOCK_WITH_X_ROBOTS_TAG\s*=\s*)(True|False)"
    match = re.search(pattern, content)
    if not match:
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message="Controlled environment does not define BLOCK_WITH_X_ROBOTS_TAG.",
        )
    if match.group(2) == "False":
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.ALREADY_APPLIED.value,
            target=effective_target,
            files_changed=[],
            message="X-Robots-Tag restriction is already disabled.",
        )

    updated = content[: match.start()] + f"{match.group(1)}False" + content[match.end() :]
    config_path.write_text(updated, encoding="utf-8")
    return FixResult(
        fix_id=fix_id,
        status=FixStatus.APPLIED.value,
        target=effective_target,
        files_changed=[str(config_path)],
        message="Disabled the controlled X-Robots-Tag restriction.",
        details={"header": "X-Robots-Tag", "previous_value": "noindex, nofollow", "new_value": None},
    )
