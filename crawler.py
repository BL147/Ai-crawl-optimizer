"""
crawler.py - Multi-Bot Emulation & Crawling Engine
Author: A (Crawler Specialist) & System Integrator

Fetches target URLs with different user-agent headers to identify
blocking differences between regular desktop browsers and AI crawlers.
"""

import time
from typing import Dict, Any
import requests

# Standard bot definitions
BOT_AGENTS = {
    "browser_chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "gpt_bot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
    "claude_bot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "perplexity_bot": "PerplexityBot/1.0 (+https://perplexity.ai/perplexitybot)",
    "google_bot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
}

def crawl_target(url: str, timeout: float = 6.0) -> Dict[str, Any]:
    """
    Crawls the target URL using multiple bot user-agent profiles.
    
    Returns:
        Dict containing "bots" dictionary with per-agent crawl responses.
    """
    results = {}
    for bot_id, ua in BOT_AGENTS.items():
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        start = time.time()
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            latency_ms = int((time.time() - start) * 1000)
            h_lower = {k.lower(): v.lower() for k, v in resp.headers.items()}
            t_lower = resp.text[:4000].lower()

            waf = None
            if "cf-ray" in h_lower or ("server" in h_lower and "cloudflare" in h_lower["server"]):
                waf = "Cloudflare"
            elif "x-akamai-transformed" in h_lower:
                waf = "Akamai WAF"

            captcha = (
                ("cf-mitigated" in h_lower and h_lower["cf-mitigated"] == "challenge") or
                any(sig in t_lower for sig in ["turnstile", "recaptcha", "checking your browser", "just a moment..."])
            )

            blocked = resp.status_code in [401, 403, 429] or captcha

            results[bot_id] = {
                "status": resp.status_code,
                "latency_ms": latency_ms,
                "blocked": blocked,
                "waf": waf if blocked else None,
                "captcha": captcha,
                "headers": dict(resp.headers),
                "body_snippet": resp.text[:500]
            }
        except Exception as exc:
            results[bot_id] = {
                "status": 500,
                "latency_ms": int((time.time() - start) * 1000),
                "blocked": True,
                "waf": None,
                "captcha": False,
                "error": str(exc)
            }

    return {"bots": results}
