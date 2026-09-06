"""
orchestrator.py - Master Backend Orchestrator
Author: Shlok (System Integrator)

Architecture:
URL + persona
      ↓
Anshul's actual crawler (from crawler import crawl_sync, crawl_with_baseline_sync)
      ↓
Shlok's scoring engine (from scoring import calculate_score)
      ↓
Kavish's remediation engine (from remediation import generate_remediation)
      ↓
Combined integration result

Single orchestration interface:
    run_audit(url, persona)
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from crawler import crawl_sync, crawl_with_baseline_sync
from scoring import calculate_score
from remediation import generate_remediation


def run_audit(url: str, persona: str = "gptbot", **kwargs) -> Dict[str, Any]:
    """
    Single orchestration interface:
    URL + persona -> Anshul Crawler -> Shlok Scoring -> Kavish Remediation -> Combined Result.

    Parameters:
        url (str): Target URL to audit (e.g. "https://example.com" or "http://127.0.0.1:5050").
        persona (str): Bot persona to emulate ("gptbot", "claudebot", "perplexitybot", etc.). Defaults to "gptbot".
        **kwargs: Optional parameters (include_baseline=True, timeout_seconds=12.0, api_key=None, model="gemini-1.5-flash").

    Returns:
        Dict[str, Any]: Combined integration result conforming to:
        {
            "crawl": ...,
            "score": ...,
            "risk_level": ...,
            "reasons": ...,
            "metrics": ...,
            "remediation": ...
        }
    """
    # 1. URL Normalization
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"

    clean_persona = (persona or "gptbot").strip().lower()
    timestamp = datetime.now(timezone.utc).isoformat()
    include_baseline = kwargs.get("include_baseline", True)
    timeout_seconds = kwargs.get("timeout_seconds", 12.0)
    api_key = kwargs.get("api_key") or os.getenv("GEMINI_API_KEY")

    # 2. Stage 1: Anshul's Actual Crawler
    crawl_result: Dict[str, Any]
    primary_crawl: Dict[str, Any]

    if include_baseline:
        try:
            crawl_result = crawl_with_baseline_sync(
                clean_url,
                persona=clean_persona,
                timeout_seconds=timeout_seconds,
            )
            primary_crawl = crawl_result.get("target_persona", crawl_result)
        except Exception as exc:
            # Fallback to single persona crawl if baseline encounter an issue
            primary_crawl = crawl_sync(
                clean_url,
                persona=clean_persona,
                timeout_seconds=timeout_seconds,
            )
            crawl_result = primary_crawl
    else:
        primary_crawl = crawl_sync(
            clean_url,
            persona=clean_persona,
            timeout_seconds=timeout_seconds,
        )
        crawl_result = primary_crawl

    # 3. Stage 2: Shlok's Scoring Engine
    score_result = calculate_score(crawl_result)

    # 4. Stage 3: Kavish's Remediation Engine
    # Directly invokes Kavish's generate_remediation with authentic crawler output
    remediation_result = generate_remediation(primary_crawl, api_key=api_key)

    # 5. Build bot_matrix mapping for contract & UI compatibility
    baseline_browser = crawl_result.get("baseline_browser", {}) if isinstance(crawl_result, dict) else {}
    browser_status = baseline_browser.get("http", {}).get("status_code", 200)
    browser_latency = int(baseline_browser.get("http", {}).get("response_time_ms", 150) or 150)
    browser_blocked = baseline_browser.get("detection", {}).get("is_blocked", False)

    http_info = primary_crawl.get("http", {})
    det_info = primary_crawl.get("detection", {})
    inf_info = det_info.get("inference", {})
    mech_str = str(inf_info.get("mechanism", "NONE"))
    waf_val = mech_str if mech_str not in ["NONE", ""] else None

    primary_bot_entry = {
        "status": http_info.get("status_code", 200),
        "latency_ms": int(http_info.get("response_time_ms", 0) or 0),
        "blocked": det_info.get("is_blocked", False) or inf_info.get("verdict") in ["BLOCKED", "CHALLENGED"],
        "verdict": inf_info.get("verdict", "ACCESSIBLE"),
        "mechanism": mech_str,
        "waf": waf_val,
        "captcha": any("turnstile" in s.lower() or "captcha" in s.lower() for s in det_info.get("signals", [])),
        "headers": http_info.get("headers", {}),
        "raw": primary_crawl,
    }

    bot_matrix = {
        clean_persona: primary_bot_entry,
        "browser_chrome": {
            "status": browser_status,
            "latency_ms": browser_latency,
            "blocked": browser_blocked,
            "waf": None,
            "captcha": False,
        },
    }

    # Common aliases for UI dashboards expecting gpt_bot / claude_bot keys
    if "gpt" in clean_persona:
        bot_matrix["gpt_bot"] = primary_bot_entry
    elif "claude" in clean_persona:
        bot_matrix["claude_bot"] = primary_bot_entry
    elif "perplexity" in clean_persona:
        bot_matrix["perplexity_bot"] = primary_bot_entry

    if "gpt_bot" not in bot_matrix:
        bot_matrix["gpt_bot"] = dict(primary_bot_entry)
    if "claude_bot" not in bot_matrix:
        bot_matrix["claude_bot"] = dict(primary_bot_entry)

    # 6. Combined Integration Result
    combined_result = {
        # Mandated Minimum Contract
        "crawl": primary_crawl,
        "score": score_result["score"],
        "risk_level": score_result["risk_level"],
        "reasons": score_result["reasons"],
        "metrics": score_result["metrics"],
        "remediation": remediation_result,

        # Extended integration fields for full system compatibility
        "url": clean_url,
        "persona": clean_persona,
        "timestamp": timestamp,
        "grade": score_result["grade"],
        "status": "success",
        "summary": {
            "score": score_result["score"],
            "grade": score_result["grade"],
            "status": score_result["status"],
            "color": score_result["color"],
            "text": score_result["summary"],
        },
        "scoring": score_result,
        "bot_matrix": bot_matrix,
        "robots_txt": primary_crawl.get("robots_txt", {}),
        "ai_recommendations": {
            "root_cause": remediation_result.get("problem_detected") or remediation_result.get("problem", ""),
            "cloudflare_waf_rule": remediation_result.get("code_or_configuration_change") or remediation_result.get("code_or_config", ""),
            "robots_txt_fix": remediation_result.get("before_after_example", {}).get("after", ""),
            "action_items": remediation_result.get("validation_steps", []),
        },
        "full_baseline": crawl_result if include_baseline else None,
    }

    return combined_result


if __name__ == "__main__":
    import json
    print("Testing single orchestration interface run_audit('https://example.com', 'gptbot')...")
    res = run_audit("https://example.com", "gptbot")
    print(f"Target:     {res['url']} (Persona: {res['persona']})")
    print(f"Score:      {res['score']}/100 ({res['grade']})")
    print(f"Risk Level: {res['risk_level']}")
    print("Reasons:")
    for r in res["reasons"]:
        print(f"  - {r}")
    print("Metrics:   ", res["metrics"])
    print("Remediation problem: ", res["remediation"].get("problem_detected"))
