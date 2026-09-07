"""Robots.txt fix implementation for Phase 2 test environments."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from crawler.robots import RobotsParser
from fix_engine.models import FixResult, FixStatus, TestEnvironment

DEFAULT_AI_BOTS = [
    "GPTBot",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "ByteSpider",
    "Cohere-AI",
    "CCBot",
    "OAI-SearchBot",
    "Diffbot",
]


def _normalize_tokens(bots: List[str]) -> List[str]:
    """Normalize bot names/tokens to canonical display names and tokens."""
    return [b.strip() for b in bots if b.strip()]


def _check_already_allowed(
    content: str,
    target_tokens: Set[str],
) -> bool:
    """
    Check if all target AI bots are already fully allowed in robots.txt.
    Returns True only if:
    1. RobotsParser evaluates is_allowed=True for path '/'
    2. There are no specific Disallow directives for the target bot
    """
    parser = RobotsParser(content)

    for token in target_tokens:
        tok_lower = token.lower()
        allowed, rule = parser.is_allowed("/", tok_lower)
        if not allowed:
            return False

        # If the bot has its own rules, ensure none of them are Disallow
        if tok_lower in parser.rules:
            for rule_type, pattern in parser.rules[tok_lower]:
                if rule_type == "disallow" and pattern:
                    return False

    return True


def _transform_robots_content(
    content: str,
    target_bots: List[str],
) -> str:
    """
    Deterministically transform robots.txt content so that target AI crawlers
    are allowed without breaking other directives, comments, or sitemaps.
    """
    target_tokens_lower = {b.lower(): b for b in target_bots}

    lines = content.splitlines()
    output_lines: List[str] = []
    
    # Track existing blocks
    # A block starts with one or more User-agent lines followed by directives
    i = 0
    existing_configured_bots: Set[str] = set()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if this line starts a User-agent definition
        if stripped.lower().startswith("user-agent:"):
            # Gather all contiguous user-agent lines in this record group
            ua_lines: List[Tuple[str, str]] = []  # (original_line, agent_name)
            while i < len(lines) and lines[i].strip().lower().startswith("user-agent:"):
                raw_ua = lines[i]
                agent = raw_ua.split(":", 1)[1].strip()
                ua_lines.append((raw_ua, agent))
                i += 1

            # Gather subsequent directive lines belonging to this agent group
            directive_lines: List[str] = []
            while i < len(lines):
                cur = lines[i]
                cur_stripped = cur.strip()
                if cur_stripped.lower().startswith("user-agent:"):
                    break  # next record group starts
                directive_lines.append(cur)
                i += 1

            # Determine if this group targets any of our AI bots
            matched_ai_bots = [
                agent for _, agent in ua_lines
                if agent.lower() in target_tokens_lower
            ]

            if matched_ai_bots:
                # This block applies to one or more target AI bots
                for agent in matched_ai_bots:
                    existing_configured_bots.add(agent.lower())

                # Check if this block also applies to non-AI bots (mixed block)
                non_ai_uas = [
                    raw for raw, agent in ua_lines
                    if agent.lower() not in target_tokens_lower
                ]

                if non_ai_uas:
                    # Separate non-AI user-agents to preserve their original rules
                    output_lines.extend(non_ai_uas)
                    output_lines.extend(directive_lines)

                # Now output clean Allow block for the matched AI bots
                for raw, agent in ua_lines:
                    if agent.lower() in target_tokens_lower:
                        output_lines.append(f"User-agent: {agent}")

                # Retain non-restrictive directives (e.g. Crawl-delay <= 5) but replace Disallow with Allow: /
                has_allow_slash = False
                for d_line in directive_lines:
                    d_clean = d_line.strip().lower()
                    if d_clean.startswith("disallow:"):
                        # Skip disallow rule for AI bot
                        continue
                    elif d_clean.startswith("allow:"):
                        if d_clean == "allow: /":
                            has_allow_slash = True
                        output_lines.append(d_line)
                    elif d_clean.startswith("crawl-delay:"):
                        output_lines.append(d_line)
                    elif d_clean.startswith("#") or not d_clean:
                        output_lines.append(d_line)
                    else:
                        output_lines.append(d_line)

                if not has_allow_slash:
                    output_lines.append("Allow: /")
            else:
                # Block does not target AI bots: preserve as-is
                for raw, _ in ua_lines:
                    output_lines.append(raw)
                output_lines.extend(directive_lines)
        else:
            # Comment, blank line, or top-level sitemap
            output_lines.append(line)
            i += 1

    # For any target AI bots that were not already explicitly configured in their own blocks,
    # add an explicit Allow rule so they are not blocked by wildcard Disallow
    missing_bots = [
        b for b in target_bots
        if b.lower() not in existing_configured_bots
    ]

    if missing_bots:
        # Check if file needs a separating newline
        if output_lines and output_lines[-1].strip():
            output_lines.append("")

        output_lines.append("# AI Crawlers explicitly allowed by AI Crawl Optimizer")
        for bot in missing_bots:
            output_lines.append(f"User-agent: {bot}")
        output_lines.append("Allow: /")

    new_content = "\n".join(output_lines)
    if not new_content.endswith("\n"):
        new_content += "\n"
    return new_content


def apply_robots_fix(
    env: TestEnvironment,
    fix_id: str = "robots_txt",
    target: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> FixResult:
    """
    Apply robots.txt fix to a registered local test environment.
    Removes restrictive Disallow rules for AI crawlers and ensures Allow: / directives.
    """
    effective_target = target if target is not None else env.id
    options = options or {}
    raw_target_bots = options.get("personas") or DEFAULT_AI_BOTS
    target_bots = [b.strip() for b in raw_target_bots if isinstance(b, str) and b.strip()]
    if not target_bots:
        target_bots = DEFAULT_AI_BOTS
    target_tokens_lower = {b.lower() for b in target_bots}

    robots_path = env.robots_path
    if robots_path is None:
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message="Environment does not define a robots_path.",
        )

    # Runtime path traversal & symlink escape verification
    resolved_path = robots_path.resolve()
    if not env._is_subpath(resolved_path, env.root_dir):
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message=f"Security error: robots_path '{robots_path}' resolves outside environment root '{env.root_dir}'.",
        )

    # If robots.txt does not exist, create a clean default allow file
    if not robots_path.exists():
        try:
            robots_path.parent.mkdir(parents=True, exist_ok=True)
            initial_content = (
                "# Robots policy created by AI Crawl Optimizer\n"
                "User-agent: *\n"
                "Allow: /\n\n"
            )
            for bot in target_bots:
                initial_content += f"User-agent: {bot}\n"
            initial_content += "Allow: /\n"

            robots_path.write_text(initial_content, encoding="utf-8")
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.APPLIED.value,
                target=effective_target,
                files_changed=[str(robots_path)],
                message=f"Created robots.txt allowing AI crawlers ({', '.join(target_bots[:4])}...).",
            )
        except Exception as exc:
            return FixResult(
                fix_id=fix_id,
                status=FixStatus.APPLICATION_FAILED.value,
                target=effective_target,
                files_changed=[],
                message=f"Failed to create robots.txt: {exc}",
            )

    # Read existing content
    try:
        current_content = robots_path.read_text(encoding="utf-8")
    except Exception as exc:
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message=f"Failed to read robots.txt: {exc}",
        )

    # Check if fix is already applied
    if _check_already_allowed(current_content, target_tokens_lower):
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.ALREADY_APPLIED.value,
            target=effective_target,
            files_changed=[],
            message="Robots.txt already permits AI crawlers. No modifications needed.",
            details={"bots_verified": list(target_bots)},
        )

    # Transform content to allow AI bots
    try:
        updated_content = _transform_robots_content(current_content, target_bots)

        # Atomic-like write
        robots_path.write_text(updated_content, encoding="utf-8")

        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLIED.value,
            target=effective_target,
            files_changed=[str(robots_path)],
            message=f"Updated robots.txt to allow AI crawlers ({', '.join(target_bots[:4])}...).",
            details={
                "modified_bots": list(target_bots),
                "file_path": str(robots_path),
            },
        )
    except Exception as exc:
        return FixResult(
            fix_id=fix_id,
            status=FixStatus.APPLICATION_FAILED.value,
            target=effective_target,
            files_changed=[],
            message=f"Failed to update robots.txt: {exc}",
        )
