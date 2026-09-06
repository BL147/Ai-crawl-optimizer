"""Unit tests for personas module."""

import pytest
from crawler.personas import get_persona, list_personas, PERSONAS, CrawlerPersona


def test_standard_personas_exist():
    assert "gptbot" in PERSONAS
    assert "claudebot" in PERSONAS
    assert "perplexitybot" in PERSONAS
    assert "google_extended" in PERSONAS
    assert "bytespider" in PERSONAS
    assert "ccbot" in PERSONAS
    assert "standard_browser" in PERSONAS


def test_get_persona_normalized():
    # Test case insensitivity and dash substitution
    p1 = get_persona("GPTBot")
    assert p1.id == "gptbot"
    assert "GPTBot" in p1.user_agent

    p2 = get_persona("claude-bot")
    assert p2.id == "claudebot"
    assert "ClaudeBot" in p2.user_agent

    p3 = get_persona("Google-Extended")
    assert p3.id == "google_extended"


def test_get_persona_custom():
    custom = get_persona("MyCustomAgent/1.0")
    assert custom.id == "MyCustomAgent/1.0"
    assert custom.user_agent == "MyCustomAgent/1.0"
    assert custom.robots_token == "*"


def test_standard_browser_persona():
    baseline = get_persona("standard_browser")
    assert not baseline.is_ai_agent
    assert "Chrome" in baseline.user_agent
    assert "Sec-Ch-Ua" in baseline.extra_headers


def test_list_personas():
    personas = list_personas()
    assert len(personas) >= 8
    ids = [p["id"] for p in personas]
    assert "gptbot" in ids
    assert "standard_browser" in ids
