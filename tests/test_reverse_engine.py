"""Comprehensive test suite for Phase 3 AI Restriction / Reverse Fix Engine."""

import json
from pathlib import Path
import pytest
import requests

from crawler.engine import CrawlerEngine
from crawler.robots import RobotsParser
from demo_streaming_site.app import start_server
from fix_engine import (
    RestrictionEngine,
    RestrictionResult,
    RestrictionStatus,
    RestrictionCapability,
    RestrictionCategory,
    RESTRICTION_CATALOG,
    TestEnvironment,
    TestEnvironmentRegistry,
    apply_fix,
    apply_restriction,
    remove_restriction,
)
from orchestrator import run_audit
from validation import compare_and_validate, ValidationStatus


@pytest.fixture
def mock_env(tmp_path: Path):
    """Create an isolated, controlled local test environment for restriction testing."""
    root_dir = tmp_path / "mock_site"
    root_dir.mkdir(parents=True, exist_ok=True)

    robots_file = root_dir / "robots.txt"
    robots_file.write_text(
        "User-agent: *\n"
        "Allow: /\n",
        encoding="utf-8",
    )

    app_file = root_dir / "app.py"
    app_file.write_text(
        "BLOCK_AI_BOTS = False\n",
        encoding="utf-8",
    )

    registry = TestEnvironmentRegistry()
    env = TestEnvironment(
        id="mock_site",
        root_dir=root_dir,
        base_url="http://127.0.0.1:5050",
        robots_path=robots_file,
        config_path=app_file,
        description="Controlled Test Site for Reverse Restrictions",
    )
    registry.register(env)

    return {
        "env": env,
        "registry": registry,
        "root_dir": root_dir,
        "robots_file": robots_file,
        "app_file": app_file,
    }


# ============================================================================
# Tests 1 - 5: Robots.txt AI Restriction & Reversibility Lifecycle
# ============================================================================

def test_robots_restriction_lifecycle(mock_env):
    """
    Tests 1 - 5:
    1. GPTBot accessible initially
    2. Apply robots restriction
    3. GPTBot becomes RESTRICTED
    4. Remove restriction
    5. GPTBot becomes ACCESSIBLE
    """
    robots_file = mock_env["robots_file"]
    registry = mock_env["registry"]

    # 1. Initially GPTBot is accessible
    parser_initial = RobotsParser(robots_file.read_text(encoding="utf-8"))
    assert parser_initial.is_allowed("/", "gptbot")[0] is True
    assert parser_initial.is_allowed("/", "claudebot")[0] is True

    # 2. Apply robots restriction
    res_apply = apply_restriction(
        control_id="ai_robots_restriction",
        target="mock_site",
        options={"personas": ["gptbot", "claudebot"]},
        registry=registry,
    )
    assert res_apply["status"] == RestrictionStatus.APPLIED.value
    assert res_apply["control_id"] == "ai_robots_restriction"
    assert "gptbot" in res_apply["personas"]
    assert len(res_apply["files_changed"]) == 1

    # 3. GPTBot and ClaudeBot become RESTRICTED
    parser_restricted = RobotsParser(robots_file.read_text(encoding="utf-8"))
    assert parser_restricted.is_allowed("/", "gptbot")[0] is False
    assert parser_restricted.is_allowed("/", "claudebot")[0] is False
    # Non-targeted crawler (e.g. Googlebot) remains allowed
    assert parser_restricted.is_allowed("/", "googlebot")[0] is True

    # 4. Remove restriction
    res_remove = remove_restriction(
        control_id="ai_robots_restriction",
        target="mock_site",
        options={"personas": ["gptbot", "claudebot"]},
        registry=registry,
    )
    assert res_remove["status"] == RestrictionStatus.REMOVED.value
    assert "gptbot" in res_remove["personas"]

    # 5. GPTBot becomes ACCESSIBLE again
    parser_restored = RobotsParser(robots_file.read_text(encoding="utf-8"))
    assert parser_restored.is_allowed("/", "gptbot")[0] is True
    assert parser_restored.is_allowed("/", "claudebot")[0] is True


# ============================================================================
# Tests 6 - 9: Rate Limit & WAF / Challenge Simulations
# ============================================================================

def test_rate_limit_simulation_lifecycle(mock_env):
    """
    Tests 6 - 7:
    6. Apply AI rate limit
    7. Restriction config is written; remove restores state.
    """
    root_dir = mock_env["root_dir"]
    registry = mock_env["registry"]
    restr_file = root_dir / "restrictions.json"

    # Apply AI rate limit
    res_apply = apply_restriction(
        control_id="ai_rate_limit",
        target="mock_site",
        options={"personas": ["gptbot"]},
        registry=registry,
    )
    assert res_apply["status"] == RestrictionStatus.APPLIED.value
    assert restr_file.exists()

    data = json.loads(restr_file.read_text(encoding="utf-8"))
    assert data["rate_limit"]["enabled"] is True
    assert "gptbot" in data["rate_limit"]["personas"]

    # Remove AI rate limit
    res_remove = remove_restriction(
        control_id="ai_rate_limit",
        target="mock_site",
        options={"personas": ["gptbot"]},
        registry=registry,
    )
    assert res_remove["status"] == RestrictionStatus.REMOVED.value
    data_after = json.loads(restr_file.read_text(encoding="utf-8"))
    assert data_after["rate_limit"]["enabled"] is False


def test_waf_challenge_simulation_lifecycle(mock_env):
    """
    Tests 8 - 9:
    8. Apply WAF simulation
    9. Restriction config is written; remove restores state.
    """
    root_dir = mock_env["root_dir"]
    registry = mock_env["registry"]
    restr_file = root_dir / "restrictions.json"

    # Apply WAF challenge simulation
    res_apply = apply_restriction(
        control_id="ai_waf_challenge",
        target="mock_site",
        options={"personas": ["gptbot", "perplexitybot"]},
        registry=registry,
    )
    assert res_apply["status"] == RestrictionStatus.APPLIED.value
    data = json.loads(restr_file.read_text(encoding="utf-8"))
    assert data["waf_challenge"]["enabled"] is True
    assert "perplexitybot" in data["waf_challenge"]["personas"]

    # Remove WAF challenge simulation
    res_remove = remove_restriction(
        control_id="ai_waf_challenge",
        target="mock_site",
        options={"personas": ["gptbot", "perplexitybot"]},
        registry=registry,
    )
    assert res_remove["status"] == RestrictionStatus.REMOVED.value
    data_after = json.loads(restr_file.read_text(encoding="utf-8"))
    assert data_after["waf_challenge"]["enabled"] is False


def test_captcha_simulation_lifecycle(mock_env):
    """Test CAPTCHA simulation apply and remove lifecycle."""
    root_dir = mock_env["root_dir"]
    registry = mock_env["registry"]
    restr_file = root_dir / "restrictions.json"

    res_apply = apply_restriction(
        control_id="ai_captcha",
        target="mock_site",
        options={"personas": ["claudebot"]},
        registry=registry,
    )
    assert res_apply["status"] == RestrictionStatus.APPLIED.value
    data = json.loads(restr_file.read_text(encoding="utf-8"))
    assert data["captcha"]["enabled"] is True
    assert "claudebot" in data["captcha"]["personas"]

    res_remove = remove_restriction(
        control_id="ai_captcha",
        target="mock_site",
        options={"personas": ["claudebot"]},
        registry=registry,
    )
    assert res_remove["status"] == RestrictionStatus.REMOVED.value
    data_after = json.loads(restr_file.read_text(encoding="utf-8"))
    assert data_after["captcha"]["enabled"] is False


# ============================================================================
# Tests 10 - 13: Safety & Security Boundary Checks
# ============================================================================

def test_external_url_rejected():
    """Test 10: External public URLs are strictly rejected."""
    for public_url in [
        "https://spotify.com",
        "https://netflix.com",
        "https://bbc.com",
        "https://google.com/robots.txt",
        "http://192.168.1.1",
    ]:
        res = apply_restriction("ai_robots_restriction", public_url)
        assert res["status"] == RestrictionStatus.TARGET_NOT_ALLOWED.value
        assert res["files_changed"] == []

        res_rem = remove_restriction("ai_robots_restriction", public_url)
        assert res_rem["status"] == RestrictionStatus.TARGET_NOT_ALLOWED.value


def test_arbitrary_path_rejected():
    """Test 11: Arbitrary unmanaged filesystem paths are rejected."""
    for arb_path in [
        "/etc/passwd",
        "/var/log",
        "/tmp/arbitrary_site",
        "/Users/shared",
    ]:
        res = apply_restriction("ai_robots_restriction", arb_path)
        assert res["status"] == RestrictionStatus.TARGET_NOT_ALLOWED.value
        assert res["files_changed"] == []


def test_path_traversal_rejected(mock_env):
    """Test 12: Path traversal attempts are rejected."""
    traversal_targets = [
        "mock_site/../../../../etc",
        "../../../etc/shadow",
        "mock_site/..",
        "./mock_site/../../",
    ]
    registry = mock_env["registry"]
    for target in traversal_targets:
        res = apply_restriction("ai_robots_restriction", target, registry=registry)
        assert res["status"] == RestrictionStatus.TARGET_NOT_ALLOWED.value
        assert res["files_changed"] == []


def test_unregistered_environment_rejected(mock_env):
    """Test 13: Unregistered environment IDs and ports are rejected."""
    registry = mock_env["registry"]
    for unreg in ["unregistered_corp", "production_app", "http://127.0.0.1:9999"]:
        res = apply_restriction("ai_robots_restriction", unreg, registry=registry)
        assert res["status"] == RestrictionStatus.TARGET_NOT_ALLOWED.value
        assert res["files_changed"] == []


# ============================================================================
# Test 14: Recommendation-Only Controls
# ============================================================================

def test_recommendation_only_controls(mock_env):
    """
    Test 14: Controls that cannot safely be modified automatically return
    status = recommendation_only with structured implementation steps.
    """
    registry = mock_env["registry"]

    rec_controls = [
        "cloudflare_waf_config",
        "akamai_bot_manager",
        "recaptcha_enterprise",
        "ai_authentication",
    ]

    for control_id in rec_controls:
        res = apply_restriction(control_id, "mock_site", registry=registry)
        assert res["status"] == RestrictionStatus.RECOMMENDATION_ONLY.value
        assert res["control_id"] == control_id
        assert len(res["implementation_steps"]) > 0
        assert res["files_changed"] == []

        res_rem = remove_restriction(control_id, "mock_site", registry=registry)
        assert res_rem["status"] == RestrictionStatus.RECOMMENDATION_ONLY.value
        assert len(res_rem["implementation_steps"]) > 0


# ============================================================================
# Tests 15 - 16: Idempotency
# ============================================================================

def test_apply_restriction_idempotency(mock_env):
    """Test 15: Applying an already-existing restriction is idempotent."""
    registry = mock_env["registry"]

    # First apply
    res1 = apply_restriction(
        "ai_robots_restriction",
        "mock_site",
        options={"personas": ["gptbot"]},
        registry=registry,
    )
    assert res1["status"] == RestrictionStatus.APPLIED.value

    # Second apply: must report ALREADY_APPLIED
    res2 = apply_restriction(
        "ai_robots_restriction",
        "mock_site",
        options={"personas": ["gptbot"]},
        registry=registry,
    )
    assert res2["status"] == RestrictionStatus.ALREADY_APPLIED.value
    assert res2["files_changed"] == []
    assert "already restricting" in res2["message"]


def test_remove_restriction_idempotency(mock_env):
    """Test 16: Removing a non-existing restriction is idempotent."""
    registry = mock_env["registry"]

    # Removing when not restricted
    res = remove_restriction(
        "ai_robots_restriction",
        "mock_site",
        options={"personas": ["gptbot"]},
        registry=registry,
    )
    assert res["status"] == RestrictionStatus.ALREADY_REMOVED.value
    assert res["files_changed"] == []
    assert "not restricting" in res["message"]


# ============================================================================
# Part 9: Validation Contract Integration Tests with CineStream & Crawler
# ============================================================================

def test_cinestream_robots_restriction_end_to_end_validation():
    """
    Part 9 Validation Contract:
    BEFORE: GPTBot ACCESSIBLE
    Apply: robots restriction
    Re-crawl same target
    Observe actual crawler result: GPTBot RESTRICTED
    Validation Engine: compare_and_validate -> VERIFIED
    Remove: restriction
    Re-crawl same target
    Observe actual crawler result: GPTBot ACCESSIBLE
    Validation Engine: compare_and_validate -> VERIFIED
    """
    demo_robots_path = Path("demo_streaming_site/robots.txt")
    initial_content = demo_robots_path.read_text(encoding="utf-8")

    try:
        base_url = start_server(port=5050)

        # Ensure GPTBot is initially allowed
        remove_restriction(
            "ai_robots_restriction",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )

        # Baseline crawl: GPTBot is ACCESSIBLE
        audit_before = run_audit(base_url, persona="gptbot")
        assert audit_before["robots_txt"]["is_allowed"] is True
        assert audit_before["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

        # Apply restriction
        res_apply = apply_restriction(
            "ai_robots_restriction",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_apply["status"] == RestrictionStatus.APPLIED.value

        # Post-restriction crawl: GPTBot is RESTRICTED
        audit_after = run_audit(base_url, persona="gptbot")
        assert audit_after["robots_txt"]["is_allowed"] is False
        assert audit_after["crawl"]["detection"]["inference"]["verdict"] == "RESTRICTED"

        # Validation Engine verification
        val_report = compare_and_validate(
            audit_before,
            audit_after,
            target_issue="ai_robots_restriction",
        )
        assert val_report.validation_status == ValidationStatus.VERIFIED
        assert "RESTRICTED" in str(val_report.issue_after)

        # Reversibility: remove restriction and validate return to ACCESSIBLE
        res_remove = remove_restriction(
            "ai_robots_restriction",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_remove["status"] == RestrictionStatus.REMOVED.value

        audit_restored = run_audit(base_url, persona="gptbot")
        assert audit_restored["robots_txt"]["is_allowed"] is True
        assert audit_restored["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

        val_restore_report = compare_and_validate(
            audit_after,
            audit_restored,
            target_issue="robots_txt",
        )
        assert val_restore_report.validation_status == ValidationStatus.VERIFIED

    finally:
        demo_robots_path.write_text(initial_content, encoding="utf-8")


def test_cinestream_rate_limit_simulation_end_to_end_validation():
    """
    Test rate limit simulation on CineStream:
    Apply ai_rate_limit -> crawler returns HTTP 429 BLOCKED -> validation VERIFIED.
    Remove -> crawler returns HTTP 200 ACCESSIBLE.
    """
    demo_robots_path = Path("demo_streaming_site/robots.txt")
    initial_content = demo_robots_path.read_text(encoding="utf-8")
    restr_path = Path("demo_streaming_site/restrictions.json")
    try:
        remove_restriction(
            "ai_robots_restriction",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        base_url = start_server(port=5050)

        # Baseline crawl: accessible
        audit_before = run_audit(base_url, persona="gptbot")
        assert audit_before["crawl"]["http"]["status_code"] == 200
        assert audit_before["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

        # Apply rate limit restriction
        res_apply = apply_restriction(
            "ai_rate_limit",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_apply["status"] == RestrictionStatus.APPLIED.value

        # Post-restriction crawl: 429 BLOCKED
        audit_after = run_audit(base_url, persona="gptbot")
        assert audit_after["crawl"]["http"]["status_code"] == 429
        assert audit_after["crawl"]["detection"]["inference"]["verdict"] == "BLOCKED"

        # Validation Engine confirms restriction applied
        val_report = compare_and_validate(
            audit_before,
            audit_after,
            target_issue="ai_rate_limit",
        )
        assert val_report.validation_status == ValidationStatus.VERIFIED

        # Remove rate limit
        res_remove = remove_restriction(
            "ai_rate_limit",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_remove["status"] == RestrictionStatus.REMOVED.value

        audit_restored = run_audit(base_url, persona="gptbot")
        assert audit_restored["crawl"]["http"]["status_code"] == 200
        assert audit_restored["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

    finally:
        if restr_path.exists():
            restr_path.unlink()
        demo_robots_path.write_text(initial_content, encoding="utf-8")


def test_cinestream_waf_challenge_simulation_end_to_end_validation():
    """
    Test WAF challenge simulation on CineStream:
    Apply ai_waf_challenge -> crawler returns CHALLENGED -> validation VERIFIED.
    Remove -> crawler returns ACCESSIBLE.
    """
    demo_robots_path = Path("demo_streaming_site/robots.txt")
    initial_content = demo_robots_path.read_text(encoding="utf-8")
    restr_path = Path("demo_streaming_site/restrictions.json")
    try:
        remove_restriction(
            "ai_robots_restriction",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        base_url = start_server(port=5050)

        # Baseline crawl: accessible
        audit_before = run_audit(base_url, persona="gptbot")
        assert audit_before["crawl"]["http"]["status_code"] == 200
        assert audit_before["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

        # Apply WAF challenge restriction
        res_apply = apply_restriction(
            "ai_waf_challenge",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_apply["status"] == RestrictionStatus.APPLIED.value

        # Post-restriction crawl: CHALLENGED
        audit_after = run_audit(base_url, persona="gptbot")
        assert audit_after["crawl"]["detection"]["inference"]["verdict"] == "CHALLENGED"

        # Validation Engine confirms WAF restriction applied
        val_report = compare_and_validate(
            audit_before,
            audit_after,
            target_issue="ai_waf_challenge",
        )
        assert val_report.validation_status == ValidationStatus.VERIFIED

        # Remove WAF challenge
        res_remove = remove_restriction(
            "ai_waf_challenge",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_remove["status"] == RestrictionStatus.REMOVED.value

        audit_restored = run_audit(base_url, persona="gptbot")
        assert audit_restored["crawl"]["http"]["status_code"] == 200
        assert audit_restored["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

    finally:
        if restr_path.exists():
            restr_path.unlink()
        demo_robots_path.write_text(initial_content, encoding="utf-8")


def test_cinestream_captcha_simulation_end_to_end_validation():
    """
    Test CAPTCHA simulation on CineStream:
    Apply ai_captcha -> crawler returns CHALLENGED -> validation VERIFIED.
    Remove -> crawler returns ACCESSIBLE.
    """
    demo_robots_path = Path("demo_streaming_site/robots.txt")
    initial_content = demo_robots_path.read_text(encoding="utf-8")
    restr_path = Path("demo_streaming_site/restrictions.json")
    try:
        remove_restriction(
            "ai_robots_restriction",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        base_url = start_server(port=5050)

        # Baseline crawl: accessible
        audit_before = run_audit(base_url, persona="gptbot")
        assert audit_before["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

        # Apply CAPTCHA restriction
        res_apply = apply_restriction(
            "ai_captcha",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_apply["status"] == RestrictionStatus.APPLIED.value

        # Post-restriction crawl: CHALLENGED
        audit_after = run_audit(base_url, persona="gptbot")
        assert audit_after["crawl"]["detection"]["inference"]["verdict"] == "CHALLENGED"

        # Validation Engine confirms CAPTCHA restriction applied
        val_report = compare_and_validate(
            audit_before,
            audit_after,
            target_issue="ai_captcha",
        )
        assert val_report.validation_status == ValidationStatus.VERIFIED

        # Remove CAPTCHA
        res_remove = remove_restriction(
            "ai_captcha",
            "demo_streaming_site",
            options={"personas": ["gptbot"]},
        )
        assert res_remove["status"] == RestrictionStatus.REMOVED.value

        audit_restored = run_audit(base_url, persona="gptbot")
        assert audit_restored["crawl"]["detection"]["inference"]["verdict"] == "ACCESSIBLE"

    finally:
        if restr_path.exists():
            restr_path.unlink()
        demo_robots_path.write_text(initial_content, encoding="utf-8")
