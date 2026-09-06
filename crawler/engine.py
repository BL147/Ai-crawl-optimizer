"""Playwright-based crawler engine for simulating personas and collecting observations."""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response, Error as PlaywrightError

from crawler.detector import BotBlockDetector
from crawler.models import CrawlResult, HttpObservation, PageObservation
from crawler.personas import CrawlerPersona, get_persona
from crawler.robots import inspect_robots


class CrawlerEngine:
    """Orchestrates Playwright browser sessions to audit URLs under specific personas."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def crawl(
        self,
        url: str,
        persona_name: str = "gptbot",
        timeout_seconds: float = 15.0,
        wait_after_load_ms: int = 1500,
    ) -> CrawlResult:
        """
        Execute an automated crawl of the target URL using the configured persona.
        Returns a rich, structured CrawlResult model.
        """
        persona = get_persona(persona_name)
        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 1: Inspect robots.txt concurrently with browser setup
        robots_task = asyncio.create_task(inspect_robots(url, persona, timeout=min(6.0, timeout_seconds)))

        http_obs = HttpObservation(final_url=url)
        page_obs = PageObservation()
        html_content = ""
        error_message: Optional[str] = None
        success = True

        redirects: List[str] = []
        response_headers: Dict[str, str] = {}
        status_code: Optional[int] = None
        content_type: Optional[str] = None
        start_time = time.perf_counter()

        try:
            async with async_playwright() as p:
                browser: Browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )

                # Configure context with persona's user agent and headers
                context: BrowserContext = await browser.new_context(
                    user_agent=persona.user_agent,
                    extra_http_headers=persona.extra_headers,
                    viewport={"width": 1280, "height": 800},
                    java_script_enabled=True,
                )

                page: Page = await context.new_page()

                # Track redirect chains
                def on_request(request):
                    if request.is_navigation_request() and request.redirected_from:
                        redirects.append(request.redirected_from.url)

                page.on("request", on_request)

                # Navigate
                try:
                    response: Optional[Response] = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=int(timeout_seconds * 1000),
                    )

                    # Give scripts, redirects, and potential challenge challenges a moment to render
                    if wait_after_load_ms > 0:
                        await page.wait_for_timeout(wait_after_load_ms)

                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

                    if response:
                        status_code = response.status
                        response_headers = response.headers
                        content_type = response_headers.get("content-type")
                        final_url = response.url
                    else:
                        final_url = page.url

                    # Page observations
                    title = await page.title()
                    html_content = await page.content()

                    # Extract text snippet
                    body_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                    cleaned_text = " ".join((body_text or "").split())
                    snippet = cleaned_text[:1000]

                    # Extract meta tags
                    meta_tags = await page.evaluate(
                        """() => {
                            const tags = {};
                            document.querySelectorAll('meta').forEach(el => {
                                const name = el.getAttribute('name') || el.getAttribute('property');
                                const content = el.getAttribute('content');
                                if (name && content) {
                                    tags[name.toLowerCase()] = content;
                                }
                            });
                            return tags;
                        }"""
                    )

                    x_robots = response_headers.get("x-robots-tag")
                    server = response_headers.get("server")

                    http_obs = HttpObservation(
                        status_code=status_code,
                        final_url=final_url,
                        redirect_count=len(redirects),
                        redirects=redirects,
                        headers=response_headers,
                        content_type=content_type,
                        response_time_ms=elapsed_ms,
                        server=server,
                        x_robots_tag=x_robots,
                    )

                    page_obs = PageObservation(
                        title=title,
                        meta_tags=meta_tags,
                        text_length=len(cleaned_text),
                        snippet=snippet,
                        has_javascript_requirement="javascript" in snippet.lower()
                        and ("enable" in snippet.lower() or "required" in snippet.lower()),
                    )

                except PlaywrightError as pe:
                    success = False
                    error_message = str(pe)
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    http_obs = HttpObservation(
                        final_url=url,
                        response_time_ms=elapsed_ms,
                    )

                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            success = False
            error_message = f"Browser execution failure: {str(e)}"

        # Await robots.txt inspection
        try:
            robots_result = await robots_task
        except Exception as re_err:
            from crawler.models import RobotsDirectives

            robots_result = RobotsDirectives(
                exists=False,
                url=f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt",
                is_allowed=True,
                matching_rule=f"Robots inspection error: {str(re_err)}",
            )

        # Run heuristic detection engine
        detection = BotBlockDetector.detect(http=http_obs, page=page_obs, html_content=html_content)

        return CrawlResult(
            target_url=url,
            persona=persona.id,
            user_agent=persona.user_agent,
            timestamp=timestamp,
            success=success,
            error=error_message,
            robots_txt=robots_result,
            http=http_obs,
            page=page_obs,
            detection=detection,
        )
