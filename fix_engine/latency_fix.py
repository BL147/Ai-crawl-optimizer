"""Controlled simulated latency and performance fix implementation."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fix_engine.models import FixResult, FixStatus, TestEnvironment

LATENCY_PATTERNS: List[Tuple[str, str]] = [
    # (regex pattern matching assignment, group 1 prefix, group 2 current val)
    (r"(?m)^(SIMULATED_LATENCY_MS\s*=\s*)([0-9]+)", "SIMULATED_LATENCY_MS"),
    (r"(?m)^(LATENCY_MS\s*=\s*)([0-9]+)", "LATENCY_MS"),
    (r"(?m)^(SIMULATED_DELAY_SECONDS\s*=\s*)([0-9.]+)", "SIMULATED_DELAY_SECONDS"),
    (r"(?m)^(SIMULATE_LATENCY\s*=\s*)(True|False)", "SIMULATE_LATENCY"),
    (r"(?m)^(DELAY_MS\s*=\s*)([0-9]+)", "DELAY_MS"),
    (r"(?m)^(CRAWL_DELAY_MS\s*=\s*)([0-9]+)", "CRAWL_DELAY_MS"),
]

JSON_LATENCY_KEYS = [
    "simulated_latency_ms",
    "latency_ms",
    "simulated_delay_ms",
    "delay_ms",
    "response_delay_ms",
    "simulate_latency",
]


def apply_latency_fix(
    env: TestEnvironment,
    fix_id: str = "latency",
    target: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> FixResult:
    """
    Apply controlled latency reduction to a registered test environment.
    Deterministically updates simulated latency configurations to 0ms.
    """
    effective_target = target if target is not None else env.id
    options = options or {}
    target_latency_ms = options.get("target_latency_ms", 0)

    # Resolve config file to inspect and modify
    config_path = env.config_path
    if config_path is None or not config_path.exists():
        # Search inside env.root_dir for common candidate config files
        candidates = [
            env.root_dir / "config.json",
            env.root_dir / "config.py",
            env.root_dir / "app.py",
            env.root_dir / "server.py",
        ]
        found = next((c for c in candidates if c.is_file()), None)
        if found:
            config_path = found
        else:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.APPLICATION_FAILED.value,
                target=effective_target,
                files_changed=[],
                message="No latency configuration file found in test environment.",
            )

    # Runtime path traversal & symlink escape verification
    resolved_config = config_path.resolve()
    if not env._is_subpath(resolved_config, env.root_dir):
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message=f"Security error: config_path '{config_path}' resolves outside environment root '{env.root_dir}'.",
        )

    # 1. Handle JSON configuration file
    if config_path.suffix.lower() == ".json":
        try:
            raw_text = config_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except Exception as exc:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.APPLICATION_FAILED.value,
                target=effective_target,
                files_changed=[],
                message=f"Failed to parse JSON config '{config_path.name}': {exc}",
            )

        matched_key = next((k for k in JSON_LATENCY_KEYS if k in data), None)
        if not matched_key:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.ALREADY_APPLIED.value,
                target=effective_target,
                files_changed=[],
                message=f"No simulated latency settings found in '{config_path.name}'. Latency is already minimal.",
            )

        val = data[matched_key]
        if isinstance(val, (int, float)):
            if val <= target_latency_ms:
                return FixResult(
                    fix_id=fix_id,
                    status=FixStatus.ALREADY_APPLIED.value,
                    target=effective_target,
                    files_changed=[],
                    message=f"Simulated latency is already {val} ms (<= {target_latency_ms} ms).",
                    details={"current_latency_ms": val},
                )
            # Update to target
            data[matched_key] = target_latency_ms
        elif isinstance(val, bool):
            if not val:
                return FixResult(
                    fix_id=fix_id,
                    status=FixStatus.ALREADY_APPLIED.value,
                    target=effective_target,
                    files_changed=[],
                    message="Simulated latency is already disabled (False).",
                )
            data[matched_key] = False
        else:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.APPLICATION_FAILED.value,
                target=effective_target,
                files_changed=[],
                message=f"Unexpected latency value type for key '{matched_key}': {type(val)}",
            )

        try:
            config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.APPLIED.value,
                target=effective_target,
                files_changed=[str(config_path)],
                message=f"Reduced simulated latency from {val} ms to {target_latency_ms} ms in {config_path.name}.",
                details={"previous_latency": val, "new_latency": target_latency_ms},
            )
        except Exception as exc:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.APPLICATION_FAILED.value,
                target=effective_target,
                files_changed=[],
                message=f"Failed to write config file '{config_path.name}': {exc}",
            )

    # 2. Handle Python configuration file
    try:
        content = config_path.read_text(encoding="utf-8")
    except Exception as exc:
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message=f"Failed to read config file '{config_path.name}': {exc}",
        )

    for pattern, var_name in LATENCY_PATTERNS:
        match = re.search(pattern, content)
        if match:
            raw_val = match.group(2).strip()
            # If already 0 or False
            if raw_val in ("0", "0.0", "False"):
                return FixResult(
                    fix_id=fix_id,
                    status=FixStatus.ALREADY_APPLIED.value,
                    target=effective_target,
                    files_changed=[],
                    message=f"Simulated latency ({var_name} = {raw_val}) is already disabled / 0 ms.",
                    details={"variable": var_name, "value": raw_val},
                )

            # Replace with target_latency_ms
            new_val = str(target_latency_ms) if raw_val not in ("True", "False") else "False"
            prefix = match.group(1)
            updated_content = (
                content[: match.start()]
                + f"{prefix}{new_val}"
                + content[match.end() :]
            )

            try:
                config_path.write_text(updated_content, encoding="utf-8")
                return FixResult(
                    fix_id=fix_id,
                    status=FixStatus.APPLIED.value,
                    target=effective_target,
                    files_changed=[str(config_path)],
                    message=f"Reduced simulated latency ({var_name}: {raw_val} -> {new_val}) in {config_path.name}.",
                    details={"variable": var_name, "previous_value": raw_val, "new_value": new_val},
                )
            except Exception as exc:
                return FixResult(
                    fix_id=fix_id,
                    status=FixStatus.APPLICATION_FAILED.value,
                    target=effective_target,
                    files_changed=[],
                    message=f"Failed to write config file '{config_path.name}': {exc}",
                )

    # If no latency pattern was found in the python file
    return FixResult(
        fix_id=fix_id,
        status=FixStatus.ALREADY_APPLIED.value,
        target=effective_target,
        files_changed=[],
        message=f"No active simulated latency variable found in '{config_path.name}'. Latency is not artificially inflated.",
    )
