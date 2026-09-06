"""Unified backend entry point for the Streamlit audit UI."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from crawler import crawl_sync, crawl_with_baseline_sync
from remediation import generate_remediation
from scoring import calculate_score


_CHALLENGE_MECHANISMS = {
    "CLOUDFLARE_CHALLENGE",
    "CLOUDFLARE_BLOCK",
    "DATADOME",
    "PERIMETERX",
    "AKAMAI",
    "AWS_WAF",
    "RECAPTCHA",
    "HCAPTCHA",
    "CUSTOM_BOT_BLOCK",
}


def _scoring_payload(crawl_result: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    http = crawl_result.get("http", {})
    detection = crawl_result.get("detection", {})
    inference = detection.get("inference", {})
    mechanism = str(inference.get("mechanism", "NONE")).upper()
    status_code = http.get("status_code")
    verdict = str(inference.get("verdict", "")).upper()
    blocked = bool(detection.get("is_blocked")) or (
        status_code in {401, 429} and verdict != "INCONCLUSIVE"
    )
    latency = http.get("response_time_ms") or 0

    baseline_http = (baseline or {}).get("http", {})
    browser_status = baseline_http.get("status_code", status_code)
    browser_latency = baseline_http.get("response_time_ms", latency)
    robots = crawl_result.get("robots_txt", {})

    return {
        "browser": {"status": browser_status or 0, "latency_ms": browser_latency or 0},
        "bots": {
            crawl_result.get("persona", "ai_crawler"): {
                "status": status_code or 0,
                "latency_ms": latency,
                "blocked": blocked,
                "waf": mechanism if mechanism in _CHALLENGE_MECHANISMS else None,
                "captcha": mechanism in {"RECAPTCHA", "HCAPTCHA"},
            }
        },
        "robots_txt": {
            "status": robots.get("status_code", 0),
            "ai_disallowed": not robots.get("is_allowed", True),
        },
        "waf_detected": mechanism if mechanism in _CHALLENGE_MECHANISMS else None,
        "captcha_detected": mechanism in {"RECAPTCHA", "HCAPTCHA"},
    }


def run_audit(
    url: str,
    persona: str = "gptbot",
    include_baseline: bool = False,
    **crawl_options: Any,
) -> Dict[str, Any]:
    """Run the real crawler, scorer, and remediation engine as one audit."""
    clean_url = url.strip()
    if not urlparse(clean_url).scheme:
        clean_url = f"https://{clean_url}"

    baseline = None
    if include_baseline:
        paired = crawl_with_baseline_sync(
            clean_url,
            persona=persona,
            headless=crawl_options.get("headless", True),
            timeout_seconds=crawl_options.get("timeout_seconds", 12.0),
        )
        crawl_result = paired["target_persona"]
        baseline = paired["baseline_browser"]
    else:
        crawl_result = crawl_sync(
            clean_url,
            persona=persona,
            headless=crawl_options.get("headless", True),
            timeout_seconds=crawl_options.get("timeout_seconds", 15.0),
            wait_after_load_ms=crawl_options.get("wait_after_load_ms", 1500),
        )

    scoring = calculate_score(_scoring_payload(crawl_result, baseline))
    remediation = generate_remediation(crawl_result)
    risk_level = "HIGH RISK" if scoring["score"] < 50 else "MEDIUM RISK" if scoring["score"] < 75 else "LOW RISK"

    return {
        "url": clean_url,
        "persona": persona,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "crawl": crawl_result,
        "http": crawl_result.get("http", {}),
        "robots_txt": crawl_result.get("robots_txt", {}),
        "page": crawl_result.get("page", {}),
        "detection": crawl_result.get("detection", {}),
        "scoring": scoring,
        "summary": {
            "score": scoring["score"],
            "grade": scoring["grade"],
            "status": scoring["status"],
            "risk_level": risk_level,
            "text": scoring["summary"],
        },
        "remediation": remediation,
        "baseline": baseline,
        "status": "success" if crawl_result.get("success", False) else "error",
    }
