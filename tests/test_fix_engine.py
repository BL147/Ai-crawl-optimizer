"""Comprehensive test suite for Phase 2 Fix Application Engine."""

import json
import os
import stat
from pathlib import Path
import pytest

from crawler.robots import RobotsParser
from fix_engine import (
    FixApplicationEngine,
    FixResult,
    FixStatus,
    TestEnvironment,
    TestEnvironmentRegistry,
    apply_fix,
)


@pytest.fixture
def mock_env(tmp_path: Path):
    """Create an isolated, controlled local test environment for testing fixes."""
    root_dir = tmp_path / "fictional_spotify"
    root_dir.mkdir(parents=True, exist_ok=True)

    robots_file = root_dir / "robots.txt"
    robots_file.write_text(
        "# Spotify Mock Robots Policy\n"
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        "User-agent: ClaudeBot\n"
        "Disallow: /\n\n"
        "User-agent: Googlebot\n"
        "Allow: /\n\n"
        "Sitemap: http://localhost:5050/sitemap.xml\n",
        encoding="utf-8",
    )

    app_file = root_dir / "app.py"
    app_file.write_text(
        "SIMULATED_LATENCY_MS = 3500\n"
        "BLOCK_AI_BOTS = False\n",
        encoding="utf-8",
    )

    registry = TestEnvironmentRegistry()
    env = TestEnvironment(
        id="fictional_spotify",
        root_dir=root_dir,
        base_url="http://127.0.0.1:5050",
        robots_path=robots_file,
        config_path=app_file,
        description="Controlled Fictional Spotify Test Site",
    )
    registry.register(env)

    return {
        "env": env,
        "registry": registry,
        "root_dir": root_dir,
        "robots_file": robots_file,
        "app_file": app_file,
    }


def test_successful_robots_fix(mock_env):
    """Test 1: Successful robots.txt fix allows restricted AI crawlers."""
    robots_file = mock_env["robots_file"]
    registry = mock_env["registry"]

    # Before fix: GPTBot and ClaudeBot must be disallowed
    before_parser = RobotsParser(robots_file.read_text(encoding="utf-8"))
    assert before_parser.is_allowed("/", "gptbot")[0] is False
    assert before_parser.is_allowed("/", "claudebot")[0] is False

    # Apply fix
    result = apply_fix("robots_txt", "fictional_spotify", registry=registry)

    # Verify structured result
    assert result["status"] == FixStatus.APPLIED.value
    assert result["fix_id"] == "robots_txt"
    assert result["target"] == "fictional_spotify"
    assert len(result["files_changed"]) == 1
    assert str(robots_file) in result["files_changed"][0]

    # After fix: GPTBot and ClaudeBot must be allowed
    after_content = robots_file.read_text(encoding="utf-8")
    after_parser = RobotsParser(after_content)
    assert after_parser.is_allowed("/", "gptbot")[0] is True
    assert after_parser.is_allowed("/", "claudebot")[0] is True
    # Non-AI Googlebot should still be allowed
    assert after_parser.is_allowed("/", "googlebot")[0] is True
    # Sitemap should be preserved
    assert "sitemap.xml" in after_content


def test_already_applied_robots_fix(mock_env):
    """Test 2: Idempotency - applying robots.txt fix twice reports already_applied."""
    registry = mock_env["registry"]

    # First application: should apply
    res1 = apply_fix("robots_txt", "fictional_spotify", registry=registry)
    assert res1["status"] == FixStatus.APPLIED.value

    # Second application: should detect already applied
    res2 = apply_fix("robots_txt", "fictional_spotify", registry=registry)
    assert res2["status"] == FixStatus.ALREADY_APPLIED.value
    assert res2["files_changed"] == []
    assert "already permits" in res2["message"]


def test_unsupported_fix(mock_env):
    """Test 3: Reject unrecognized fix IDs."""
    registry = mock_env["registry"]

    result = apply_fix("bypass_turnstile_exploit", "fictional_spotify", registry=registry)
    assert result["status"] == FixStatus.UNSUPPORTED_FIX.value
    assert result["files_changed"] == []
    assert "Unsupported fix" in result["message"]


def test_target_not_allowed_external_urls(mock_env):
    """Test 4: Reject external URLs and unregistered environments."""
    registry = mock_env["registry"]

    external_targets = [
        "https://spotify.com",
        "https://www.bbc.com/news",
        "https://netflix.com",
        "http://unregistered-local:8080",
        "/etc/passwd",
    ]

    for target in external_targets:
        res = apply_fix("robots_txt", target, registry=registry)
        assert res["status"] == FixStatus.TARGET_NOT_ALLOWED.value
        assert res["files_changed"] == []
        assert "not an approved local test environment" in res["message"]


def test_application_failure(mock_env):
    """Test 5: Handle write errors gracefully and report application_failed."""
    robots_file = mock_env["robots_file"]
    registry = mock_env["registry"]

    # Make file read-only to trigger PermissionError on write
    os.chmod(robots_file, stat.S_IREAD)

    try:
        res = apply_fix("robots_txt", "fictional_spotify", registry=registry)
        assert res["status"] == FixStatus.APPLICATION_FAILED.value
        assert res["files_changed"] == []
        assert "Failed to" in res["message"]
    finally:
        # Restore permissions for cleanup
        os.chmod(robots_file, stat.S_IWRITE | stat.S_IREAD)


def test_successful_latency_fix_py(mock_env):
    """Test 6: Successful simulated latency reduction in Python config."""
    app_file = mock_env["app_file"]
    registry = mock_env["registry"]

    # Before fix
    assert "SIMULATED_LATENCY_MS = 3500" in app_file.read_text(encoding="utf-8")

    # Apply fix
    result = apply_fix("latency", "fictional_spotify", registry=registry)
    assert result["status"] == FixStatus.APPLIED.value
    assert str(app_file) in result["files_changed"][0]

    # After fix
    content_after = app_file.read_text(encoding="utf-8")
    assert "SIMULATED_LATENCY_MS = 0" in content_after


def test_already_applied_latency_fix_py(mock_env):
    """Test 7: Latency fix is idempotent when latency is already 0."""
    registry = mock_env["registry"]

    # First application: reduces to 0
    res1 = apply_fix("latency", "fictional_spotify", registry=registry)
    assert res1["status"] == FixStatus.APPLIED.value

    # Second application: already 0
    res2 = apply_fix("latency", "fictional_spotify", registry=registry)
    assert res2["status"] == FixStatus.ALREADY_APPLIED.value
    assert res2["files_changed"] == []
    assert "already disabled" in res2["message"]


def test_latency_fix_json(tmp_path: Path):
    """Test latency fix on JSON configuration files."""
    root_dir = tmp_path / "json_env"
    root_dir.mkdir(parents=True, exist_ok=True)

    config_file = root_dir / "config.json"
    config_file.write_text(json.dumps({"simulated_latency_ms": 4200, "debug": True}), encoding="utf-8")

    registry = TestEnvironmentRegistry()
    registry.register(
        TestEnvironment(
            id="json_env",
            root_dir=root_dir,
            config_path=config_file,
        )
    )

    # Apply fix
    res1 = apply_fix("latency", "json_env", registry=registry)
    assert res1["status"] == FixStatus.APPLIED.value
    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["simulated_latency_ms"] == 0

    # Apply second time: already applied
    res2 = apply_fix("latency", "json_env", registry=registry)
    assert res2["status"] == FixStatus.ALREADY_APPLIED.value


def test_target_resolution_by_base_url(mock_env):
    """Test resolving registered environment via base URL (http://127.0.0.1:5050)."""
    registry = mock_env["registry"]

    # Target specified by URL instead of ID
    result = apply_fix("robots_txt", "http://127.0.0.1:5050", registry=registry)
    assert result["status"] == FixStatus.APPLIED.value
    assert result["target"] == "http://127.0.0.1:5050"


def test_path_traversal_prevention(tmp_path: Path):
    """Security test: ensure path traversal outside root_dir is strictly rejected at instantiation."""
    root_dir = tmp_path / "safe_dir"
    root_dir.mkdir()

    with pytest.raises(ValueError, match="path traversal"):
        TestEnvironment(
            id="bad_env",
            root_dir=root_dir,
            robots_path=Path("../../etc/robots.txt"),
        )


def test_whitespace_target_rejected(mock_env):
    """Security test: whitespace or empty target string must not resolve to current working directory."""
    registry = mock_env["registry"]

    for empty_target in ["", "   ", "\t\n"]:
        res = apply_fix("robots_txt", empty_target, registry=registry)
        assert res["status"] == FixStatus.TARGET_NOT_ALLOWED.value
        assert res["files_changed"] == []


def test_root_dir_cannot_be_filesystem_root():
    """Security test: root_dir cannot be set to the filesystem root directory."""
    with pytest.raises(ValueError, match="root filesystem directory"):
        TestEnvironment(
            id="root_env",
            root_dir=Path("/"),
        )


def test_runtime_symlink_escape_rejected(tmp_path: Path):
    """Security test: symlinks pointing outside environment root created after init are blocked."""
    root_dir = tmp_path / "symlink_env"
    root_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret_robots.txt"
    outside_file.write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")

    # Initial robots path inside root_dir
    robots_path = root_dir / "robots.txt"

    env = TestEnvironment(
        id="symlink_env",
        root_dir=root_dir,
        robots_path=robots_path,
    )
    registry = TestEnvironmentRegistry()
    registry.register(env)

    # Now create a symlink pointing outside root_dir
    robots_path.symlink_to(outside_file)

    # Attempting to apply fix must be rejected by runtime subpath check
    res = apply_fix("robots_txt", "symlink_env", registry=registry)
    assert res["status"] == FixStatus.APPLICATION_FAILED.value
    assert "Security error" in res["message"]
    # Verify outside file was NOT modified
    assert "Disallow: /" in outside_file.read_text(encoding="utf-8")

