"""Handlers for Phase 3 controlled restriction transformations and simulations."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from crawler.robots import RobotsParser
from fix_engine.models import TestEnvironment
from fix_engine.restriction_models import (
    RestrictionCategory,
    RestrictionResult,
    RestrictionStatus,
)


def _normalize_personas(personas: Optional[List[str]]) -> List[str]:
    """Standardize persona token list."""
    if not personas:
        return ["gptbot"]
    return [p.strip().lower() for p in personas if p.strip()]


# =============================================================================
# 1. ROBOTS.TXT RESTRICTIONS
# =============================================================================

def apply_robots_restriction(
    env: TestEnvironment,
    personas: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> RestrictionResult:
    """
    Deterministically adds Disallow: / directives for targeted AI crawlers in robots.txt.
    """
    target_bots = _normalize_personas(personas)
    robots_path = env.robots_path
    if robots_path is None or not env._is_subpath(robots_path, env.root_dir):
        return RestrictionResult(
            control_id=RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
            status=RestrictionStatus.APPLICATION_FAILED.value,
            target=env.id,
            personas=target_bots,
            message=f"Invalid or untrusted robots.txt path for target '{env.id}'.",
        )

    content = robots_path.read_text(encoding="utf-8") if robots_path.exists() else "User-agent: *\nAllow: /\n"

    # Check if already restricted for all target bots
    parser = RobotsParser(content)
    already_restricted = True
    for bot in target_bots:
        is_allowed, rule = parser.is_allowed("/", bot)
        if is_allowed:
            already_restricted = False
            break

    if already_restricted:
        return RestrictionResult(
            control_id=RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
            status=RestrictionStatus.ALREADY_APPLIED.value,
            target=env.id,
            personas=target_bots,
            files_changed=[],
            message=f"Robots.txt is already restricting target AI crawler(s): {', '.join(target_bots)}.",
        )

    # Transform content to add Disallow: / for target bots
    new_content = _add_disallow_to_robots(content, target_bots)
    robots_path.write_text(new_content, encoding="utf-8")

    return RestrictionResult(
        control_id=RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
        status=RestrictionStatus.APPLIED.value,
        target=env.id,
        personas=target_bots,
        files_changed=[str(robots_path)],
        message=f"Applied robots.txt restriction for AI crawlers: {', '.join(target_bots)}.",
    )


def remove_robots_restriction(
    env: TestEnvironment,
    personas: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> RestrictionResult:
    """
    Deterministically removes Disallow: / directives for targeted AI crawlers, allowing them.
    """
    target_bots = _normalize_personas(personas)
    robots_path = env.robots_path
    if robots_path is None or not env._is_subpath(robots_path, env.root_dir):
        return RestrictionResult(
            control_id=RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
            status=RestrictionStatus.APPLICATION_FAILED.value,
            target=env.id,
            personas=target_bots,
            message=f"Invalid or untrusted robots.txt path for target '{env.id}'.",
        )

    if not robots_path.exists():
        return RestrictionResult(
            control_id=RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
            status=RestrictionStatus.ALREADY_REMOVED.value,
            target=env.id,
            personas=target_bots,
            message="No robots.txt found; restriction is not active.",
        )

    content = robots_path.read_text(encoding="utf-8")
    parser = RobotsParser(content)

    # Check if already allowed for all target bots
    already_allowed = True
    for bot in target_bots:
        is_allowed, rule = parser.is_allowed("/", bot)
        if not is_allowed:
            already_allowed = False
            break

    if already_allowed:
        return RestrictionResult(
            control_id=RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
            status=RestrictionStatus.ALREADY_REMOVED.value,
            target=env.id,
            personas=target_bots,
            files_changed=[],
            message=f"Robots.txt is not restricting target AI crawler(s): {', '.join(target_bots)}.",
        )

    # Transform content to allow target bots
    new_content = _remove_disallow_from_robots(content, target_bots)
    robots_path.write_text(new_content, encoding="utf-8")

    return RestrictionResult(
        control_id=RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
        status=RestrictionStatus.REMOVED.value,
        target=env.id,
        personas=target_bots,
        files_changed=[str(robots_path)],
        message=f"Removed robots.txt restriction for AI crawlers: {', '.join(target_bots)}.",
    )


def _add_disallow_to_robots(content: str, target_bots: List[str]) -> str:
    """Helper to update robots.txt so target_bots have Disallow: /."""
    lines = content.splitlines()
    output_lines: List[str] = []
    i = 0
    handled_bots: Set[str] = set()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.lower().startswith("user-agent:"):
            # Gather user-agent block
            ua_lines: List[str] = []
            agents: List[str] = []
            while i < len(lines) and lines[i].strip().lower().startswith("user-agent:"):
                raw = lines[i]
                agent = raw.split(":", 1)[1].strip()
                ua_lines.append(raw)
                agents.append(agent.lower())
                i += 1

            # Directives
            directives: List[str] = []
            while i < len(lines) and not lines[i].strip().lower().startswith("user-agent:"):
                directives.append(lines[i])
                i += 1

            # Check if this block matches any target bot
            matched = [b for b in target_bots if b in agents]
            if matched and len(agents) == len(matched):
                # Entire block is target bot(s) - ensure Disallow: /
                output_lines.extend(ua_lines)
                output_lines.append("Disallow: /")
                handled_bots.update(matched)
                continue
            elif matched:
                # Mixed block: separate target bot(s)
                non_matched_ua = [ua for ua, ag in zip(ua_lines, agents) if ag not in matched]
                output_lines.extend(non_matched_ua)
                output_lines.extend(directives)
                for mb in matched:
                    output_lines.append(f"\nUser-agent: {mb.title() if mb == 'gptbot' else mb}")
                    output_lines.append("Disallow: /")
                    handled_bots.add(mb)
                continue
            else:
                output_lines.extend(ua_lines)
                output_lines.extend(directives)
                continue

        output_lines.append(line)
        i += 1

    # Append any target bots not previously in file
    for bot in target_bots:
        if bot not in handled_bots:
            display = "GPTBot" if bot == "gptbot" else ("ClaudeBot" if bot == "claudebot" else bot.title())
            if output_lines and output_lines[-1].strip():
                output_lines.append("")
            output_lines.append(f"User-agent: {display}")
            output_lines.append("Disallow: /")

    res = "\n".join(output_lines)
    if not res.endswith("\n"):
        res += "\n"
    return res


def _remove_disallow_from_robots(content: str, target_bots: List[str]) -> str:
    """Helper to update robots.txt so target_bots are allowed."""
    lines = content.splitlines()
    output_lines: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.lower().startswith("user-agent:"):
            ua_lines: List[str] = []
            agents: List[str] = []
            while i < len(lines) and lines[i].strip().lower().startswith("user-agent:"):
                raw = lines[i]
                agent = raw.split(":", 1)[1].strip()
                ua_lines.append(raw)
                agents.append(agent.lower())
                i += 1

            directives: List[str] = []
            while i < len(lines) and not lines[i].strip().lower().startswith("user-agent:"):
                directives.append(lines[i])
                i += 1

            matched = [b for b in target_bots if b in agents]
            if matched:
                # Change Disallow: / to Allow: /
                filtered_directives = [
                    d for d in directives if not (d.strip().lower().startswith("disallow:") and d.strip().split(":", 1)[1].strip() in ("/", "/*"))
                ]
                output_lines.extend(ua_lines)
                output_lines.append("Allow: /")
                output_lines.extend(filtered_directives)
                continue
            else:
                output_lines.extend(ua_lines)
                output_lines.extend(directives)
                continue

        output_lines.append(line)
        i += 1

    res = "\n".join(output_lines)
    if not res.endswith("\n"):
        res += "\n"
    return res


# =============================================================================
# 2. SIMULATION RESTRICTIONS (RATE LIMIT, WAF CHALLENGE, CAPTCHA)
# =============================================================================

def _get_restrictions_path(env: TestEnvironment) -> Path:
    return env.root_dir / "restrictions.json"


def _read_restrictions_file(env: TestEnvironment) -> Dict[str, Any]:
    path = _get_restrictions_path(env)
    if not env._is_subpath(path, env.root_dir):
        raise ValueError(f"Path traversal detected for restrictions file: {path}")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_restrictions_file(env: TestEnvironment, data: Dict[str, Any]) -> None:
    path = _get_restrictions_path(env)
    if not env._is_subpath(path, env.root_dir):
        raise ValueError(f"Path traversal detected for restrictions file: {path}")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def apply_simulation_restriction(
    env: TestEnvironment,
    control_type: str,
    personas: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> RestrictionResult:
    """
    Applies simulation restrictions (rate_limit, waf_challenge, captcha) to the controlled test environment.
    """
    target_bots = _normalize_personas(personas)
    data = _read_restrictions_file(env)

    control_config = data.get(control_type, {})
    is_active = control_config.get("enabled", False)
    current_bots = set(control_config.get("personas", []))

    if is_active and set(target_bots).issubset(current_bots):
        return RestrictionResult(
            control_id=control_type,
            status=RestrictionStatus.ALREADY_APPLIED.value,
            target=env.id,
            personas=target_bots,
            files_changed=[],
            message=f"Restriction '{control_type}' is already active for personas: {', '.join(target_bots)}.",
        )

    new_bots = sorted(list(current_bots.union(set(target_bots))))
    data[control_type] = {
        "enabled": True,
        "personas": new_bots,
    }
    _write_restrictions_file(env, data)

    path = _get_restrictions_path(env)
    return RestrictionResult(
        control_id=control_type,
        status=RestrictionStatus.APPLIED.value,
        target=env.id,
        personas=target_bots,
        files_changed=[str(path)],
        message=f"Applied '{control_type}' restriction for personas: {', '.join(target_bots)}.",
    )


def remove_simulation_restriction(
    env: TestEnvironment,
    control_type: str,
    personas: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> RestrictionResult:
    """
    Removes simulation restrictions from the controlled test environment.
    """
    target_bots = _normalize_personas(personas)
    data = _read_restrictions_file(env)

    control_config = data.get(control_type, {})
    is_active = control_config.get("enabled", False)
    current_bots = set(control_config.get("personas", []))

    if not is_active or not (current_bots.intersection(set(target_bots))):
        return RestrictionResult(
            control_id=control_type,
            status=RestrictionStatus.ALREADY_REMOVED.value,
            target=env.id,
            personas=target_bots,
            files_changed=[],
            message=f"Restriction '{control_type}' is already inactive for personas: {', '.join(target_bots)}.",
        )

    remaining_bots = sorted(list(current_bots - set(target_bots)))
    if remaining_bots:
        data[control_type] = {
            "enabled": True,
            "personas": remaining_bots,
        }
    else:
        data[control_type] = {
            "enabled": False,
            "personas": [],
        }
    _write_restrictions_file(env, data)

    path = _get_restrictions_path(env)
    return RestrictionResult(
        control_id=control_type,
        status=RestrictionStatus.REMOVED.value,
        target=env.id,
        personas=target_bots,
        files_changed=[str(path)],
        message=f"Removed '{control_type}' restriction for personas: {', '.join(target_bots)}.",
    )
