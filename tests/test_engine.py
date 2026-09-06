"""Integration tests for Playwright crawler engine."""

import pytest
from crawler import crawl_url, crawl_sync, list_personas, BlockType
from crawler.engine import CrawlerEngine


@pytest.mark.asyncio
async def test_crawler_engine_data_url():
    """Verify crawler navigates and extracts page title and text properly."""
    engine = CrawlerEngine(headless=True)
    html_page = "data:text/html,<html><head><title>Test AI Crawl</title></head><body><h1>Hello AI</h1><p>Sample content for testing.</p></body></html>"

    result = await engine.crawl(url=html_page, persona_name="gptbot", timeout_seconds=10.0, wait_after_load_ms=100)

    assert result.success is True
    assert result.persona == "gptbot"
    assert "GPTBot" in result.user_agent
    assert result.page.title == "Test AI Crawl"
    assert "Sample content for testing." in result.page.snippet
    assert result.detection.block_type == BlockType.NONE
    assert result.detection.is_blocked is False


@pytest.mark.asyncio
async def test_crawl_url_returns_dict():
    """Verify crawl_url returns a dictionary with full schema."""
    html_page = "data:text/html,<html><head><title>Schema Test</title></head><body><p>Schema Verification</p></body></html>"
    res = await crawl_url(url=html_page, persona="claudebot", timeout_seconds=10.0, wait_after_load_ms=100)

    assert isinstance(res, dict)
    assert res["target_url"] == html_page
    assert res["persona"] == "claudebot"
    assert "robots_txt" in res
    assert "http" in res
    assert "page" in res
    assert "detection" in res
    assert res["detection"]["is_blocked"] is False


def test_crawl_sync_execution():
    """Verify crawl_sync executes synchronously."""
    html_page = "data:text/html,<html><head><title>Sync Test</title></head><body><p>Sync Execution</p></body></html>"
    res = crawl_sync(url=html_page, persona="perplexitybot", timeout_seconds=10.0, wait_after_load_ms=100)

    assert isinstance(res, dict)
    assert res["page"]["title"] == "Sync Test"
    assert res["persona"] == "perplexitybot"
