"""
ai_advisor.py - AI Diagnosis & Remediation Adapter
Author: System Integrator & Kavish (AI Specialist)

Integrates Kavish's authoritative remediation package (remediation/)
into the unified audit architecture.
"""

import os
from typing import Dict, Any, List
from remediation import generate_remediation as kavish_generate_remediation


def generate_recommendations(scoring_result: Dict[str, Any], audit_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapter function that invokes Kavish's Gemini remediation engine
    and maps the structured output for backward compatibility.
    """
    gptbot_info = audit_context.get("bots", {}).get("gpt_bot", {})
    target_url = audit_context.get("url", "https://target-website.com")
    robots_data = audit_context.get("robots_txt", {})
    waf_detected = audit_context.get("waf_detected") or gptbot_info.get("waf")
    status_code = gptbot_info.get("status", 200)
    is_blocked = gptbot_info.get("blocked", False) or (status_code in [401, 403, 429])

    # If authentic crawler result is present in context, pass it directly
    raw_crawler = audit_context.get("raw_crawler_result") or gptbot_info.get("raw")
    if raw_crawler and isinstance(raw_crawler, dict):
        crawler_payload = raw_crawler
    else:
        crawler_payload = {
            "target_url": target_url,
            "persona": "gptbot",
            "http": {
                "status_code": status_code,
                "headers": gptbot_info.get("headers", {}),
                "server": "cloudflare" if waf_detected == "Cloudflare" else None,
                "response_time_ms": gptbot_info.get("latency_ms", 0),
            },
            "robots_txt": {
                "exists": robots_data.get("status") == 200,
                "is_allowed": not robots_data.get("ai_disallowed", False),
                "matching_rule": "Disallow: /" if robots_data.get("ai_disallowed") else "Allow: /",
            },
            "detection": {
                "is_blocked": is_blocked,
                "evidence": {
                    "status_code": status_code,
                    "matched_headers": ["server: cloudflare"] if waf_detected == "Cloudflare" else [],
                    "dom_signals": [".cf-turnstile"] if gptbot_info.get("captcha") else [],
                },
                "inference": {
                    "verdict": "CHALLENGED" if (waf_detected or gptbot_info.get("captcha")) else ("BLOCKED" if is_blocked else "ACCESSIBLE"),
                    "mechanism": "CLOUDFLARE_CHALLENGE" if waf_detected == "Cloudflare" else ("NONE" if not is_blocked else "HTTP_FORBIDDEN"),
                    "confidence": 0.95 if is_blocked else 0.0,
                },
            },
        }

    try:
        rem = kavish_generate_remediation(crawler_payload)
        code_change = rem.get("code_or_configuration_change") or rem.get("code_or_config", "")
        if not code_change:
            code_change = '(http.user_agent contains "GPTBot" or http.user_agent contains "ClaudeBot") and not cf.client.bot'

        problem_text = rem.get("problem_detected") or rem.get("problem") or "Access barrier detected"
        why_text = rem.get("why_it_affects_ai_crawling", "")
        root_cause = f"{problem_text} - {why_text}".strip(" -")

        before_after = rem.get("before_after_example", {})
        robots_fix = before_after.get("after") if ("User-agent" in before_after.get("after", "")) else (
            "User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /\n\nUser-agent: *\nAllow: /\n"
        )

        return {
            "root_cause": root_cause,
            "problem": problem_text,
            "cloudflare_waf_rule": code_change,
            "robots_txt_fix": robots_fix,
            "action_items": rem.get("validation_steps") or [rem.get("recommended_fix", "Configure edge WAF to allow AI search crawlers.")],
            "recommended_fix": rem.get("recommended_fix", ""),
            "uncertainty": rem.get("uncertainty", ""),
            "remediation_details": rem,
        }
    except Exception as exc:
        # Fallback if remediation encounter an error
        return {
            "root_cause": "Cloudflare WAF / Anti-bot rules classify generative AI search agents as untrusted scrapers.",
            "cloudflare_waf_rule": '(http.user_agent contains "GPTBot" or http.user_agent contains "ClaudeBot") and not cf.client.bot',
            "robots_txt_fix": "User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /\n\nUser-agent: *\nAllow: /\n",
            "action_items": ["Create a Cloudflare WAF Custom Rule with action 'Skip' for verified AI search user agents."],
            "error": str(exc),
        }


if __name__ == "__main__":
    mock_scoring = {"score": 25, "grade": "F", "penalties": [{"factor": "HTTP 403 Forbidden"}]}
    mock_context = {
        "url": "http://127.0.0.1:5050",
        "bots": {"gpt_bot": {"status": 403, "blocked": True, "waf": "Cloudflare", "captcha": True}},
        "robots_txt": {"status": 200, "ai_disallowed": True},
        "waf_detected": "Cloudflare",
    }
    rec = generate_recommendations(mock_scoring, mock_context)
    print("=== AI ADVISOR TEST RESULT (VIA KAVISH REMEDIATION) ===")
    print("Root Cause:", rec["root_cause"])
    print("Cloudflare Rule:\n", rec["cloudflare_waf_rule"])
    print("Validation Steps:", rec["action_items"])
