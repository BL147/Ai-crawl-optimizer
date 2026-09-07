"""Regression tests for backend crawler, robots.txt, and detection semantics."""

import pytest
from unittest.mock import patch, AsyncMock
import httpx

from crawler.detector import BotBlockDetector
from crawler.models import BlockType, HttpObservation, PageObservation, RobotsDirectives
from crawler.personas import get_persona
from crawler.robots import RobotsParser, inspect_robots


def test_http_200_with_robots_disallow():
    """HTTP 200 + robots.txt Disallow must return RESTRICTED, not ACCESSIBLE, with is_blocked=False."""
    http = HttpObservation(status_code=200)
    page = PageObservation(title="Welcome", snippet="Public article content")
    robots = RobotsDirectives(
        exists=True,
        url="https://example.com/robots.txt",
        status_code=200,
        is_allowed=False,
        matching_rule="Disallow: /",
    )

    result = BotBlockDetector.detect(http, page, html_content="", robots=robots)

    assert result.inference.verdict == "RESTRICTED"
    assert result.inference.mechanism == BlockType.NONE
    assert result.inference.confidence == 1.0
    assert result.is_blocked is False
    assert "restricts" in result.inference.summary.lower()
    assert result.evidence.status_code == 200
    assert result.evidence.robots_rule == "Disallow: /"
    assert any("Robots policy" in s for s in result.signals)


def test_http_200_with_robots_allow():
    """HTTP 200 + robots.txt Allow must return unrestricted ACCESSIBLE."""
    http = HttpObservation(status_code=200)
    page = PageObservation(title="Welcome", snippet="Clean page")
    robots = RobotsDirectives(
        exists=True,
        url="https://example.com/robots.txt",
        status_code=200,
        is_allowed=True,
        matching_rule="Allow: /",
    )

    result = BotBlockDetector.detect(http, page, html_content="", robots=robots)

    assert result.inference.verdict == "ACCESSIBLE"
    assert result.inference.mechanism == BlockType.NONE
    assert result.inference.confidence == 0.0
    assert result.is_blocked is False


def test_http_200_with_no_robots_txt():
    """HTTP 200 + missing robots.txt (404) defaults to unrestricted ACCESSIBLE."""
    http = HttpObservation(status_code=200)
    page = PageObservation(title="Welcome", snippet="Clean page")
    robots = RobotsDirectives(
        exists=False,
        url="https://example.com/robots.txt",
        status_code=404,
        is_allowed=True,
        matching_rule="HTTP 404 (No robots.txt found - default allow)",
    )

    result = BotBlockDetector.detect(http, page, html_content="", robots=robots)

    assert result.inference.verdict == "ACCESSIBLE"
    assert result.inference.mechanism == BlockType.NONE
    assert result.is_blocked is False


def test_gptbot_disallowed_while_chrome_allowed():
    """Site that disallows GPTBot but allows Chrome must produce persona-specific outcomes."""
    robots_content = """
User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""
    parser = RobotsParser(robots_content)
    gpt_allowed, gpt_rule = parser.is_allowed("/articles/1", "GPTBot")
    chrome_allowed, chrome_rule = parser.is_allowed("/articles/1", "*")

    assert gpt_allowed is False
    assert gpt_rule == "Disallow: /"
    assert chrome_allowed is True
    assert chrome_rule == "Allow: /"

    http = HttpObservation(status_code=200)
    page = PageObservation(title="Article", snippet="Text")

    # GPTBot detection
    gpt_robots = RobotsDirectives(exists=True, is_allowed=gpt_allowed, matching_rule=gpt_rule)
    gpt_result = BotBlockDetector.detect(http, page, "", robots=gpt_robots)
    assert gpt_result.inference.verdict == "RESTRICTED"
    assert gpt_result.is_blocked is False

    # Chrome detection
    chrome_robots = RobotsDirectives(exists=True, is_allowed=chrome_allowed, matching_rule=chrome_rule)
    chrome_result = BotBlockDetector.detect(http, page, "", robots=chrome_robots)
    assert chrome_result.inference.verdict == "ACCESSIBLE"
    assert chrome_result.is_blocked is False


def test_gptbot_disallowed_while_claudebot_allowed():
    """Site that disallows GPTBot but allows ClaudeBot must yield divergent verdicts."""
    robots_content = """
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Allow: /
"""
    parser = RobotsParser(robots_content)
    g_allowed, _ = parser.is_allowed("/", "GPTBot")
    c_allowed, _ = parser.is_allowed("/", "ClaudeBot")

    assert g_allowed is False
    assert c_allowed is True

    http = HttpObservation(status_code=200)
    page = PageObservation(title="Home")

    g_res = BotBlockDetector.detect(http, page, "", robots=RobotsDirectives(is_allowed=g_allowed, matching_rule="Disallow: /"))
    c_res = BotBlockDetector.detect(http, page, "", robots=RobotsDirectives(is_allowed=c_allowed, matching_rule="Allow: /"))

    assert g_res.inference.verdict == "RESTRICTED"
    assert c_res.inference.verdict == "ACCESSIBLE"


def test_standalone_403_remains_inconclusive():
    """HTTP 403 without WAF signals must remain INCONCLUSIVE even with robots directives."""
    http = HttpObservation(status_code=403)
    page = PageObservation(title="403 Forbidden", snippet="Access denied")
    robots = RobotsDirectives(exists=True, is_allowed=False, matching_rule="Disallow: /")

    result = BotBlockDetector.detect(http, page, "", robots=robots)

    assert result.inference.verdict == "INCONCLUSIVE"
    assert result.inference.mechanism == BlockType.HTTP_FORBIDDEN
    assert result.is_blocked is False
    assert result.inference.confidence <= 0.40


def test_403_with_waf_remains_challenged_or_blocked():
    """HTTP 403 with real Cloudflare evidence must remain CHALLENGED."""
    http = HttpObservation(status_code=403, headers={"cf-ray": "999-SJC", "server": "cloudflare"})
    page = PageObservation(title="Just a moment...", snippet="Verify you are human")
    robots = RobotsDirectives(exists=True, is_allowed=False, matching_rule="Disallow: /")

    result = BotBlockDetector.detect(http, page, '<div class="cf-turnstile"></div>', robots=robots)

    assert result.inference.verdict == "CHALLENGED"
    assert result.inference.mechanism == BlockType.CLOUDFLARE_CHALLENGE
    assert result.is_blocked is True


def test_429_remains_rate_limited():
    """HTTP 429 must be classified as rate limited, not a policy restriction."""
    http = HttpObservation(status_code=429)
    page = PageObservation(title="Too Many Requests", snippet="Rate limit exceeded")
    robots = RobotsDirectives(exists=True, is_allowed=False, matching_rule="Disallow: /")

    result = BotBlockDetector.detect(http, page, "", robots=robots)

    assert result.inference.verdict == "BLOCKED"
    assert result.inference.mechanism == BlockType.HTTP_429_RATE_LIMITED
    assert result.is_blocked is True


@pytest.mark.asyncio
async def test_robots_txt_503_fails_closed():
    """Under RFC 9309 2.3.1.3, a 5xx error fetching robots.txt MUST fail closed (is_allowed=False)."""
    persona = get_persona("gptbot")
    mock_resp = httpx.Response(status_code=503, request=httpx.Request("GET", "https://example.com/robots.txt"))

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        directives = await inspect_robots("https://example.com/target", persona)

    assert directives.status_code == 503
    assert directives.is_allowed is False
    assert directives.exists is True
    assert "Server Error" in directives.matching_rule


@pytest.mark.asyncio
async def test_robots_txt_429_fails_closed():
    """Under RFC 9309, a 429 status code on robots.txt MUST fail closed (is_allowed=False)."""
    persona = get_persona("gptbot")
    mock_resp = httpx.Response(status_code=429, request=httpx.Request("GET", "https://example.com/robots.txt"))

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        directives = await inspect_robots("https://example.com/target", persona)

    assert directives.status_code == 429
    assert directives.is_allowed is False
    assert directives.exists is True
    assert "Access Denied" in directives.matching_rule
