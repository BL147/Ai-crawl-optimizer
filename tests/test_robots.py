"""Unit tests for robots.txt parsing and rule matching."""

import pytest
from crawler.robots import RobotsParser


SAMPLE_ROBOTS_TXT = """
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /admin/public/
Crawl-delay: 5

User-agent: GPTBot
Disallow: /
Crawl-delay: 10

User-agent: ClaudeBot
Disallow: /articles/*.pdf$
Disallow: /api/
Allow: /articles/

User-agent: Google-Extended
Disallow: /

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/news-sitemap.xml
"""


def test_robots_parser_sitemaps():
    parser = RobotsParser(SAMPLE_ROBOTS_TXT)
    assert len(parser.sitemaps) == 2
    assert "https://example.com/sitemap.xml" in parser.sitemaps
    assert "https://example.com/news-sitemap.xml" in parser.sitemaps


def test_robots_parser_gptbot_block():
    parser = RobotsParser(SAMPLE_ROBOTS_TXT)
    allowed, rule = parser.is_allowed("/blog/post-1", "GPTBot")
    assert not allowed
    assert "Disallow: /" in rule
    assert parser.get_crawl_delay("GPTBot") == 10.0


def test_robots_parser_claudebot_allow_and_wildcard():
    parser = RobotsParser(SAMPLE_ROBOTS_TXT)

    # /articles/ is allowed
    allowed, rule = parser.is_allowed("/articles/tech-trends", "ClaudeBot")
    assert allowed

    # /articles/something.pdf should be disallowed
    allowed_pdf, rule_pdf = parser.is_allowed("/articles/report.pdf", "ClaudeBot")
    assert not allowed_pdf
    assert "Disallow" in rule_pdf

    # /api/ is disallowed
    allowed_api, _ = parser.is_allowed("/api/v1/data", "ClaudeBot")
    assert not allowed_api


def test_robots_parser_fallback_to_wildcard():
    parser = RobotsParser(SAMPLE_ROBOTS_TXT)
    # PerplexityBot is not specifically mentioned, falls back to User-agent: *
    allowed, rule = parser.is_allowed("/blog/welcome", "PerplexityBot")
    assert allowed

    allowed_admin, rule_admin = parser.is_allowed("/admin/settings", "PerplexityBot")
    assert not allowed_admin
    assert "Disallow: /admin/" in rule_admin

    assert parser.get_crawl_delay("PerplexityBot") == 5.0


def test_inspect_ai_directives():
    parser = RobotsParser(SAMPLE_ROBOTS_TXT)
    ai_summary = parser.inspect_ai_directives()
    assert "gptbot" in ai_summary
    assert "claudebot" in ai_summary
    assert "google-extended" in ai_summary
    assert ai_summary["gptbot"]["defined"] is True
    assert ai_summary["gptbot"]["crawl_delay"] == 10.0
