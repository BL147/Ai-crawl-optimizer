"""Unit tests for bot-block and WAF challenge detector."""

import pytest
from crawler.detector import BotBlockDetector
from crawler.models import BlockType, HttpObservation, PageObservation


def test_cloudflare_challenge():
    http = HttpObservation(
        status_code=403,
        headers={"cf-ray": "8c4599a1bc23-SJC", "server": "cloudflare"},
    )
    page = PageObservation(
        title="Just a moment...",
        snippet="Checking your browser before accessing example.com. Enable JavaScript and cookies to continue.",
    )
    html = '<div class="cf-turnstile"></div><form id="challenge-form"></form>'

    result = BotBlockDetector.detect(http, page, html_content=html)
    assert result.is_blocked
    assert result.inference.verdict == "CHALLENGED"
    assert result.inference.mechanism == BlockType.CLOUDFLARE_CHALLENGE
    assert result.inference.confidence >= 0.90
    assert "cf-ray: 8c4599a1bc23-SJC" in result.evidence.matched_headers
    assert ".cf-turnstile" in result.evidence.dom_signals
    assert "just a moment..." in result.evidence.matched_keywords


def test_cloudflare_error_1020():
    http = HttpObservation(
        status_code=403,
        headers={"cf-ray": "8c4599a1bc23-SJC", "server": "cloudflare"},
    )
    page = PageObservation(
        title="Attention Required! | Cloudflare",
        snippet="Error 1020: Access Denied. Performance & security by Cloudflare.",
    )
    result = BotBlockDetector.detect(http, page, html_content="")
    assert result.is_blocked
    assert result.inference.verdict == "BLOCKED"
    assert result.inference.mechanism == BlockType.CLOUDFLARE_BLOCK
    assert result.inference.confidence >= 0.90


def test_datadome_detection():
    http = HttpObservation(
        status_code=403,
        headers={"x-datadome": "protected"},
    )
    page = PageObservation(
        title="Access Denied",
        snippet="Please verify you are not a robot",
    )
    html = '<script src="https://ct.datadome.co/tags.js"></script>'

    result = BotBlockDetector.detect(http, page, html_content=html)
    assert result.is_blocked
    assert result.inference.verdict == "CHALLENGED"
    assert result.inference.mechanism == BlockType.DATADOME
    assert result.inference.confidence >= 0.90
    assert "script[src*='datadome']" in result.evidence.dom_signals


def test_perimeterx_detection():
    http = HttpObservation(
        status_code=403,
        headers={"server": "nginx"},
    )
    page = PageObservation(
        title="Access Denied",
        snippet="Access to this page has been denied because we believe you are using automation tools.",
    )
    html = '<div id="px-captcha"></div>'

    result = BotBlockDetector.detect(http, page, html_content=html)
    assert result.is_blocked
    assert result.inference.verdict == "CHALLENGED"
    assert result.inference.mechanism == BlockType.PERIMETERX
    assert result.inference.confidence >= 0.90
    assert "#px-captcha" in result.evidence.dom_signals


def test_aws_waf_detection():
    http = HttpObservation(
        status_code=405,
        headers={"x-amzn-waf-action": "block"},
    )
    page = PageObservation(
        title="405 Not Allowed",
        snippet="Request blocked by AWS WAF",
    )
    html = '<div class="aws-waf-captcha-wrapper"></div>'

    result = BotBlockDetector.detect(http, page, html_content=html)
    assert result.is_blocked
    assert result.inference.mechanism == BlockType.AWS_WAF
    assert result.inference.confidence >= 0.90


def test_recaptcha_detection():
    http = HttpObservation(status_code=200)
    page = PageObservation(title="Security Check")
    html = '<div class="g-recaptcha" data-sitekey="xyz"></div><iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>'

    result = BotBlockDetector.detect(http, page, html_content=html)
    assert result.is_blocked
    assert result.inference.mechanism == BlockType.RECAPTCHA


def test_http_403_standalone_inconclusive():
    """Standalone HTTP 403 without WAF/anti-bot evidence must be marked INCONCLUSIVE."""
    http = HttpObservation(status_code=403)
    page = PageObservation(
        title="403 Forbidden",
        snippet="You do not have permission to access /private/resource on this server.",
    )
    result = BotBlockDetector.detect(http, page, html_content="")

    # Must NOT claim that AI crawler is specifically blocked
    assert result.is_blocked is False
    assert result.inference.verdict == "INCONCLUSIVE"
    assert result.inference.mechanism == BlockType.HTTP_FORBIDDEN
    assert result.inference.confidence <= 0.40
    assert "inconclusive" in result.inference.summary.lower()

    # Evidence is preserved
    assert result.evidence.status_code == 403
    assert result.evidence.page_title == "403 Forbidden"


def test_http_403_with_explicit_bot_block():
    """HTTP 403 with explicit anti-bot text should be flagged with high confidence."""
    http = HttpObservation(status_code=403)
    page = PageObservation(
        title="Access Denied",
        snippet="Bot traffic detected. Automated access is prohibited on this domain.",
    )
    result = BotBlockDetector.detect(http, page, html_content="")

    assert result.is_blocked is True
    assert result.inference.verdict == "BLOCKED"
    assert result.inference.mechanism == BlockType.CUSTOM_BOT_BLOCK
    assert result.inference.confidence >= 0.85


def test_http_429_rate_limit():
    http = HttpObservation(status_code=429)
    page = PageObservation(
        title="Too Many Requests",
        snippet="Rate limit exceeded. Please try again later.",
    )
    result = BotBlockDetector.detect(http, page, html_content="")
    assert result.is_blocked
    assert result.inference.verdict == "BLOCKED"
    assert result.inference.mechanism == BlockType.HTTP_429_RATE_LIMITED


def test_accessible_clean_page():
    http = HttpObservation(
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8", "server": "Apache"},
    )
    page = PageObservation(
        title="Documentation - AI Agents Guide",
        snippet="Welcome to our comprehensive guide on building autonomous AI agents with LLMs.",
        text_length=5420,
    )
    html = "<html><body><h1>Documentation - AI Agents Guide</h1><p>Welcome to our guide...</p></body></html>"

    result = BotBlockDetector.detect(http, page, html_content=html)
    assert not result.is_blocked
    assert result.inference.verdict == "ACCESSIBLE"
    assert result.inference.mechanism == BlockType.NONE
    assert result.inference.confidence == 0.0
    assert result.evidence.status_code == 200
