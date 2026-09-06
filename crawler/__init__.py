"""AI Crawl Optimizer - Crawler & Bot-Block Detection Module.

Exports:
    crawl_url: Asynchronous crawl function returning structured dict.
    crawl_sync: Synchronous crawl wrapper returning structured dict.
    crawl_all_personas: Asynchronous crawl across multiple bot personas.
    crawl_with_baseline: Audits an AI persona and compares against a standard browser baseline.
    list_personas: List all available crawler personas.
    get_persona: Retrieve persona metadata by identifier.
    CrawlerEngine: The underlying Playwright engine.
    CrawlResult: Pydantic model for results.
    BlockType: Enumeration of detected block types.
"""

import asyncio
from typing import Any, Dict, List, Optional

from crawler.engine import CrawlerEngine
from crawler.models import BlockType, CrawlResult
from crawler.personas import CrawlerPersona, get_persona, list_personas, PERSONAS
from crawler.detector import BotBlockDetector
from crawler.robots import inspect_robots


async def crawl_url(
    url: str,
    persona: str = "gptbot",
    headless: bool = True,
    timeout_seconds: float = 15.0,
    wait_after_load_ms: int = 1500,
) -> Dict[str, Any]:
    """
    Crawl a URL with a specific persona asynchronously.
    Returns a JSON-serializable dictionary matching the unified audit schema.
    """
    engine = CrawlerEngine(headless=headless)
    result: CrawlResult = await engine.crawl(
        url=url,
        persona_name=persona,
        timeout_seconds=timeout_seconds,
        wait_after_load_ms=wait_after_load_ms,
    )
    return result.to_dict()


def crawl_sync(
    url: str,
    persona: str = "gptbot",
    headless: bool = True,
    timeout_seconds: float = 15.0,
    wait_after_load_ms: int = 1500,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for crawl_url, suitable for Streamlit or synchronous orchestration.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    crawl_url(url, persona, headless, timeout_seconds, wait_after_load_ms),
                ).result()
        else:
            return loop.run_until_complete(
                crawl_url(url, persona, headless, timeout_seconds, wait_after_load_ms)
            )
    except RuntimeError:
        return asyncio.run(
            crawl_url(url, persona, headless, timeout_seconds, wait_after_load_ms)
        )


def crawl_all_sync(
    url: str,
    personas: Optional[List[str]] = None,
    headless: bool = True,
    timeout_seconds: float = 12.0,
) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for crawl_all_personas.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    crawl_all_personas(url, personas, headless, timeout_seconds),
                ).result()
        else:
            return loop.run_until_complete(
                crawl_all_personas(url, personas, headless, timeout_seconds)
            )
    except RuntimeError:
        return asyncio.run(
            crawl_all_personas(url, personas, headless, timeout_seconds)
        )


def crawl_with_baseline_sync(
    url: str,
    persona: str = "gptbot",
    headless: bool = True,
    timeout_seconds: float = 12.0,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for crawl_with_baseline.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    crawl_with_baseline(url, persona, headless, timeout_seconds),
                ).result()
        else:
            return loop.run_until_complete(
                crawl_with_baseline(url, persona, headless, timeout_seconds)
            )
    except RuntimeError:
        return asyncio.run(
            crawl_with_baseline(url, persona, headless, timeout_seconds)
        )


async def crawl_all_personas(
    url: str,
    personas: Optional[List[str]] = None,
    headless: bool = True,
    timeout_seconds: float = 15.0,
) -> List[Dict[str, Any]]:
    """
    Audit a URL across multiple AI agent personas.
    If personas is None, audits all default AI personas.
    """
    target_personas = personas or [p for p, data in PERSONAS.items() if data.is_ai_agent]
    engine = CrawlerEngine(headless=headless)
    results = []
    for p in target_personas:
        res = await engine.crawl(url=url, persona_name=p, timeout_seconds=timeout_seconds)
        results.append(res.to_dict())
    return results


async def crawl_with_baseline(
    url: str,
    persona: str = "gptbot",
    headless: bool = True,
    timeout_seconds: float = 15.0,
) -> Dict[str, Any]:
    """
    Audit both the requested AI persona and the standard desktop browser baseline,
    determining if the site selectively blocks AI agents.
    """
    engine = CrawlerEngine(headless=headless)
    ai_result = await engine.crawl(url=url, persona_name=persona, timeout_seconds=timeout_seconds)
    baseline_result = await engine.crawl(
        url=url, persona_name="standard_browser", timeout_seconds=timeout_seconds
    )

    ai_dict = ai_result.to_dict()
    baseline_dict = baseline_result.to_dict()

    selective_block = (
        ai_result.detection.is_blocked and not baseline_result.detection.is_blocked
    ) or (
        not ai_result.robots_txt.is_allowed and baseline_result.robots_txt.is_allowed
    )

    return {
        "url": url,
        "target_persona": ai_dict,
        "baseline_browser": baseline_dict,
        "selective_ai_block_detected": selective_block,
    }


def crawl_target(url: str) -> Dict[str, Any]:
    """
    Synchronously crawls the URL across key AI personas and baseline browser.
    Returns structured results compatible with both the orchestrator and scoring engine.
    """
    personas_to_test = ["gptbot", "claudebot", "perplexitybot", "standard_browser"]
    results = crawl_all_sync(url, personas=personas_to_test, headless=True, timeout_seconds=12.0)
    bots: Dict[str, Any] = {}
    for r in results:
        p = r.get("persona", "unknown")
        h = r.get("http", {})
        d = r.get("detection", {})
        inf = d.get("inference", {})
        mech = inf.get("mechanism")
        mech_str = str(mech) if mech and mech != BlockType.NONE else None

        bots[p] = {
            "status": h.get("status_code", 200),
            "latency_ms": h.get("response_time_ms", 0),
            "blocked": d.get("is_blocked", False),
            "waf": mech_str,
            "captcha": bool(mech_str and ("CHALLENGE" in mech_str or "CAPTCHA" in mech_str)),
            "headers": h.get("headers", {}),
            "raw": r,
        }
        # Alias mappings for compatibility
        if p == "standard_browser":
            bots["browser_chrome"] = bots[p]
        elif p == "gptbot":
            bots["gpt_bot"] = bots[p]
        elif p == "claudebot":
            bots["claude_bot"] = bots[p]
        elif p == "perplexitybot":
            bots["perplexity_bot"] = bots[p]
    return {"bots": bots, "raw_results": results}


__all__ = [
    "crawl_url",
    "crawl_sync",
    "crawl_all_sync",
    "crawl_all_personas",
    "crawl_with_baseline",
    "crawl_with_baseline_sync",
    "crawl_target",
    "list_personas",
    "get_persona",
    "CrawlerEngine",
    "CrawlResult",
    "BlockType",
    "BotBlockDetector",
    "inspect_robots",
]

