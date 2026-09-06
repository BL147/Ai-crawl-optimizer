"""
orchestrator.py - Master Backend Orchestrator
Author: Shlok (System Integrator)

Provides a unified interface for the entire backend pipeline:
URL -> Crawler -> Detection -> Scoring -> AI Recommendations -> Validated Result

Designed for K (Frontend):
    from orchestrator import run_audit
    result = run_audit("https://example.com")
"""

import time
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin

import requests

from scoring import calculate_score

# User agent signatures for emulation
EMULATED_AGENTS = {
    "browser_chrome": {
        "name": "Standard Chrome Browser",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "is_ai": False
    },
    "gpt_bot": {
        "name": "OpenAI GPTBot",
        "ua": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
        "is_ai": True
    },
    "claude_bot": {
        "name": "Anthropic ClaudeBot",
        "ua": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
        "is_ai": True
    },
    "perplexity_bot": {
        "name": "Perplexity AI Crawler",
        "ua": "PerplexityBot/1.0 (+https://perplexity.ai/perplexitybot)",
        "is_ai": True
    },
    "google_bot": {
        "name": "Googlebot (Standard SEO)",
        "ua": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "is_ai": False
    }
}


def _detect_waf_and_captcha(headers: Dict[str, str], text: str) -> Dict[str, Any]:
    """Detects security shields and CAPTCHAs from HTTP response."""
    h_lower = {k.lower(): v.lower() for k, v in headers.items()}
    t_lower = text.lower() if text else ""

    waf_name = None
    captcha_detected = False

    # 1. Cloudflare Detection
    if "cf-ray" in h_lower or "server" in h_lower and "cloudflare" in h_lower["server"]:
        waf_name = "Cloudflare"
        if "cf-mitigated" in h_lower and h_lower["cf-mitigated"] == "challenge":
            captcha_detected = True

    # 2. Akamai
    elif "x-akamai-transformed" in h_lower or "akamai" in h_lower.get("server", ""):
        waf_name = "Akamai WAF"

    # 3. DataDome
    elif "x-datadome" in h_lower or "datadome" in t_lower:
        waf_name = "DataDome Anti-Bot"
        captcha_detected = True

    # 4. AWS CloudFront
    elif "x-amz-cf-id" in h_lower:
        waf_name = "AWS CloudFront WAF"

    # Content-based CAPTCHA / Challenge signals
    captcha_signatures = [
        "turnstile", "cf-turnstile", "recaptcha", "hcaptcha",
        "checking your browser", "just a moment...", "ray id:"
    ]
    if any(sig in t_lower for sig in captcha_signatures):
        captcha_detected = True
        if not waf_name:
            waf_name = "Cloudflare"

    return {
        "waf_name": waf_name,
        "captcha_detected": captcha_detected
    }


def _fetch_with_agent(url: str, ua_string: str, timeout: float = 6.0) -> Dict[str, Any]:
    """Lightweight resilient fallback fetcher."""
    headers = {
        "User-Agent": ua_string,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    start = time.time()
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        latency_ms = int((time.time() - start) * 1000)
        detection = _detect_waf_and_captcha(dict(resp.headers), resp.text[:4000])

        blocked = (resp.status_code in [401, 403, 429]) or detection["captcha_detected"]

        return {
            "status": resp.status_code,
            "latency_ms": latency_ms,
            "blocked": blocked,
            "waf": detection["waf_name"],
            "captcha": detection["captcha_detected"],
            "headers": dict(resp.headers),
            "body_snippet": resp.text[:500]
        }
    except requests.exceptions.Timeout:
        return {
            "status": 504,
            "latency_ms": int(timeout * 1000),
            "blocked": True,
            "waf": None,
            "captcha": False,
            "error": "Connection timed out"
        }
    except Exception as exc:
        return {
            "status": 500,
            "latency_ms": int((time.time() - start) * 1000),
            "blocked": True,
            "waf": None,
            "captcha": False,
            "error": str(exc)
        }


def _check_robots_txt(base_url: str) -> Dict[str, Any]:
    """Fetches and parses robots.txt for AI crawler disallow rules."""
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, headers={"User-Agent": "AI-Audit-Engine/1.0"}, timeout=4.0)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            current_ua = ""
            ai_disallowed = False
            disallowed_bots = []

            for raw_line in lines:
                line = raw_line.strip()
                if line.lower().startswith("user-agent:"):
                    current_ua = line.split(":", 1)[1].strip().lower()
                elif line.lower().startswith("disallow:") and "/" in line:
                    if any(bot in current_ua for bot in ["gptbot", "claudebot", "perplexitybot", "ccbot"]):
                        ai_disallowed = True
                        if current_ua not in disallowed_bots:
                            disallowed_bots.append(current_ua)

            return {
                "status": 200,
                "ai_disallowed": ai_disallowed,
                "disallowed_bots": disallowed_bots,
                "content_snippet": resp.text[:600]
            }
        else:
            return {
                "status": resp.status_code,
                "ai_disallowed": False,
                "disallowed_bots": [],
                "content_snippet": f"Returned HTTP {resp.status_code}"
            }
    except Exception as exc:
        return {
            "status": 500,
            "ai_disallowed": False,
            "disallowed_bots": [],
            "content_snippet": f"Failed to fetch robots.txt: {exc}"
        }


def _generate_ai_recommendations(scoring_result: Dict[str, Any], audit_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates intelligent root cause and ready-to-use WAF / robots.txt rules.
    If S has created an AI analysis module, can delegate to it.
    """
    # Attempt to import S's module if available
    try:
        from ai_advisor import generate_recommendations as s_ai_advisor
        rec = s_ai_advisor(scoring_result, audit_context)
        if rec and isinstance(rec, dict) and "root_cause" in rec:
            return rec
    except Exception:
        # Fall back gracefully to built-in generator if S's module is absent or raises an error
        pass

    # Built-in intelligent rule-based generator
    score = scoring_result["score"]
    penalties = scoring_result.get("penalties", [])

    is_blocked_by_waf = any("Anti-Bot" in p["factor"] or "403" in p["factor"] for p in penalties)
    is_blocked_by_robots = any("Robots.txt" in p["factor"] for p in penalties)
    has_discrepancy = any("Discrepancy" in p["factor"] for p in penalties)

    root_causes = []
    action_items = []

    if is_blocked_by_waf:
        root_causes.append("Cloudflare WAF / Anti-bot rules classify generative AI search agents as untrusted scrapers and return 403 challenges.")
        action_items.append("Create a Cloudflare WAF Custom Rule with action 'Skip' or 'Allow' for verified AI search user agents.")

    if is_blocked_by_robots:
        root_causes.append("Your robots.txt disallows GPTBot, ClaudeBot, or PerplexityBot, preventing indexing in generative search.")
        action_items.append("Update robots.txt to explicitly allow AI agents on public marketing and documentation paths.")

    if not root_causes:
        root_causes.append("No critical blocking barriers detected. Site is accessible to AI search engines.")
        action_items.append("Maintain low TTFB (Time to First Byte) to preserve crawl budget.")

    # Generate Cloudflare WAF Expression Snippet
    cloudflare_waf_rule = (
        '(http.user_agent contains "GPTBot" or '
        'http.user_agent contains "ClaudeBot" or '
        'http.user_agent contains "PerplexityBot") and '
        'not cf.client.bot'
    )

    # Generate optimized robots.txt snippet
    robots_txt_fix = """# AI Search Crawler Directives (Optimized)
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

# Standard crawlers
User-agent: *
Allow: /
"""

    return {
        "root_cause": " ".join(root_causes),
        "cloudflare_waf_rule": cloudflare_waf_rule,
        "robots_txt_fix": robots_txt_fix,
        "action_items": action_items
    }


def run_audit(url: str, **kwargs) -> Dict[str, Any]:
    """
    Main Orchestrator Entrypoint for K (Frontend).

    Parameters:
        url (str): Target URL to inspect (e.g. "https://example.com" or "http://127.0.0.1:5050")

    Returns:
        Dict[str, Any]: Standardized AuditResult contract with scoring, bot matrix, and fixes.
    """
    # 1. URL Normalization
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"

    timestamp = datetime.now(timezone.utc).isoformat()

    # 2. Check if A (Crawler) has an external module ready
    bot_results = {}
    external_crawler_used = False

    try:
        from crawler import crawl_target as a_crawl_target
        raw_crawl = a_crawl_target(clean_url)
        if raw_crawl and "bots" in raw_crawl and raw_crawl["bots"]:
            bot_results = raw_crawl.get("bots", {})
            external_crawler_used = True
    except Exception:
        pass

    if not bot_results:
        # Resilient Built-in Multi-Agent Emulation
        for bot_id, bot_meta in EMULATED_AGENTS.items():
            bot_results[bot_id] = _fetch_with_agent(clean_url, bot_meta["ua"])

    # Extract browser baseline
    browser_data = bot_results.get("browser_chrome", {"status": 200, "latency_ms": 150})

    # 3. Check Robots.txt
    robots_data = _check_robots_txt(clean_url)

    # 4. Aggregate Global Detection
    global_waf = next((b.get("waf") for b in bot_results.values() if b.get("waf")), None)
    global_captcha = any(b.get("captcha") for b in bot_results.values())

    audit_payload = {
        "browser": browser_data,
        "bots": bot_results,
        "robots_txt": robots_data,
        "waf_detected": global_waf,
        "captcha_detected": global_captcha
    }

    # 5. Execute Scoring Engine
    scoring_result = calculate_score(audit_payload)

    # 6. Execute AI Diagnosis
    ai_recommendations = _generate_ai_recommendations(scoring_result, audit_payload)

    # 7. Package and return the final unified result for K
    return {
        "url": clean_url,
        "timestamp": timestamp,
        "engine_version": "1.0.0-integrator",
        "external_crawler_active": external_crawler_used,
        "summary": {
            "score": scoring_result["score"],
            "grade": scoring_result["grade"],
            "status": scoring_result["status"],
            "color": scoring_result["color"],
            "text": scoring_result["summary"]
        },
        "scoring": scoring_result,
        "bot_matrix": bot_results,
        "robots_txt": robots_data,
        "ai_recommendations": ai_recommendations,
        "status": "success"
    }


if __name__ == "__main__":
    import json
    print("Testing orchestrator against public URL...")
    test_res = run_audit("https://example.com")
    print(f"Target: {test_res['url']}")
    print(f"Score: {test_res['summary']['score']}/100 ({test_res['summary']['grade']})")
    print(f"Status: {test_res['summary']['status']}")
