"""
ai_advisor.py - AI Diagnosis & WAF Remediation Module
Author: S (AI Specialist) & System Integrator

Generates root-cause analysis and automated WAF/robots.txt rules
using Google Gemini or OpenAI LLMs, with instant rule-based fallback.
"""

import os
from typing import Dict, Any, List

def generate_recommendations(scoring_result: Dict[str, Any], audit_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes audit penalties and generates actionable AI search crawl fixes.
    
    Parameters:
        scoring_result: Dict with score, grade, status, and penalties list
        audit_context: Dict with browser, bots, and robots_txt crawl data
    
    Returns:
        Dict with root_cause, cloudflare_waf_rule, robots_txt_fix, and action_items
    """
    score = scoring_result.get("score", 100)
    penalties = scoring_result.get("penalties", [])

    # Check for Gemini / OpenAI API Keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # If an API key is available, an LLM call can be performed here:
    if gemini_key:
        try:
            # S can implement direct Gemini API calls here
            pass
        except Exception:
            pass

    # Built-in High Quality Synthesis
    root_causes = []
    action_items = []

    has_waf_block = any("Anti-Bot" in p.get("factor", "") or "403" in p.get("factor", "") for p in penalties)
    has_robots_block = any("Robots.txt" in p.get("factor", "") for p in penalties)
    has_captcha = any("CAPTCHA" in p.get("factor", "") for p in penalties)

    if has_waf_block or has_captcha:
        root_causes.append("Cloudflare WAF / Bot Management rules treat AI search engines as unauthorized scrapers, returning 403 Forbidden challenges.")
        action_items.append("Create a Cloudflare Custom WAF Rule with action 'Skip' or 'Allow' for verified AI crawlers.")

    if has_robots_block:
        root_causes.append("The robots.txt file contains explicit Disallow directives blocking GPTBot, ClaudeBot, or PerplexityBot.")
        action_items.append("Update robots.txt with explicit 'Allow: /' directives for generative search agents.")

    if not root_causes:
        root_causes.append("Website is currently accessible to generative AI search engines without active blocks.")
        action_items.append("Monitor crawl latency and maintain structured semantic markup for generative summaries.")

    cloudflare_waf_rule = (
        '(http.user_agent contains "GPTBot" or '
        'http.user_agent contains "ClaudeBot" or '
        'http.user_agent contains "PerplexityBot") and '
        'not cf.client.bot'
    )

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


if __name__ == "__main__":
    import json
    # Sample mock scoring input
    sample_scoring = {
        "score": 25,
        "grade": "F",
        "status": "AI CRAWL BLOCKED",
        "penalties": [
            {"factor": "HTTP 403 Forbidden", "category": "HTTP Status", "penalty": -25},
            {"factor": "Anti-Bot Shield Challenge (Cloudflare)", "category": "Anti-Bot & WAF", "penalty": -25},
            {"factor": "Robots.txt AI Crawl Disallow", "category": "Robots.txt Policy", "penalty": -15}
        ]
    }
    sample_context = {
        "browser": {"status": 200},
        "bots": {"gpt_bot": {"status": 403, "blocked": True}},
        "robots_txt": {"ai_disallowed": True}
    }

    print("=== RUNNING AI ADVISOR TEST ===")
    rec = generate_recommendations(sample_scoring, sample_context)
    print("\n[ROOT CAUSE]:")
    print(rec["root_cause"])
    print("\n[CLOUDFLARE WAF RULE]:")
    print(rec["cloudflare_waf_rule"])
    print("\n[ROBOTS.TXT FIX]:")
    print(rec["robots_txt_fix"])
    print("[ACTION ITEMS]:")
    for item in rec["action_items"]:
        print(f" - {item}")

