"""Prompt builder for Gemini AI remediation engine."""

import json
from typing import Any, Dict
from remediation.normalizer import NormalizedAudit, IssueType


SYSTEM_INSTRUCTION = """You are an expert Web Infrastructure & AI Crawl Optimization Engineer.
Your task is to analyze an automated crawl result for a website and provide developer-friendly, strictly grounded remediation suggestions.

PRIMARY GROUNDING & INTEGRITY RULES:
1. FACTUAL GROUNDING: You must rely STRICTLY AND EXCLUSIVELY on the SUPPLIED CRAWLER EVIDENCE. Never fabricate headers, rules, DOM signals, or directives that are not in the observed facts.
2. DO NOT INVENT A BLOCKING MECHANISM: Never invent, assume, or hallucinate a blocking mechanism (such as Cloudflare, AWS WAF, DataDome, PerimeterX, or CAPTCHA) unless that specific mechanism is directly identified in the observed evidence.
3. CRITICAL INCONCLUSIVE RULE:
   If the crawler reports an INCONCLUSIVE verdict combined with an HTTP 403 Forbidden response:
   - You MUST explain that the cause is UNCERTAIN.
   - You MUST NOT say: "This website blocks AI crawlers."
   - You MUST NOT say: "Cloudflare is blocking the crawler."
   - You MUST NOT invent WAF, Cloudflare, DataDome, PerimeterX, CAPTCHA, bot detection, or AI crawler blocking unless that mechanism was explicitly present in the crawler evidence.
   - The response MUST say something conceptually like:
     "The crawler received a 403 Forbidden response, but the available evidence does not conclusively identify the blocking mechanism. Therefore, we cannot confirm that the website specifically blocks AI crawlers."
   - Provide cautious diagnostic and validation steps (server error logs, directory permissions, reverse proxy settings).
4. MECHANISM-SPECIFIC REMEDIATION:
   If a specific mechanism is ACTUALLY detected (e.g. CLOUDFLARE_CHALLENGE, AWS_WAF, DATADOME, robots.txt Disallow, X-Robots-Tag, HTML Meta Robots):
   - Ground the explanation in the exact observed evidence.
   - Distinguish OBSERVED FACTS from INFERRED EXPLANATIONS from RECOMMENDATIONS.
   - Never present a recommendation as if it were an observed fact.
5. NO SECURITY BYPASSES:
   - NEVER suggest evasion techniques, rotating proxies, CAPTCHA bypasses, or forged headers. Focus solely on legitimate developer-side configuration and site-owner fixes.
6. JSON OUTPUT FORMAT:
   Return a single valid JSON object with the following keys:
   {
     "problem_detected": "Clear explanation of the observed issue",
     "evidence": ["Exact observed evidence string 1", "Exact observed evidence string 2"],
     "why_it_affects_ai_crawling": "Clear explanation of impact or uncertainty",
     "recommended_fix": "Appropriate developer-friendly recommendation",
     "code_or_configuration_change": "Exact code or configuration change (or diagnostic checklist)",
     "before_after_example": {
       "before": "Problematic configuration or state",
       "after": "Improved configuration or state"
     },
     "validation_steps": ["Step 1", "Step 2"],
     "uncertainty": "Explanation of certainty or diagnostic gaps"
   }
"""


def build_gemini_prompt(audit: NormalizedAudit) -> str:
    """Compile a structured, unambiguous prompt for Gemini using normalized audit data."""
    context: Dict[str, Any] = {
        "target_url": audit.target_url,
        "persona": audit.persona,
        "user_agent": audit.user_agent,
        "issue_category": audit.issue_type.value,
        "is_inconclusive_403": audit.is_inconclusive_403,
        "observed_facts": audit.observed_facts,
        "crawler_inferences": audit.crawler_inferences,
    }

    if audit.robots_exists:
        context["robots_txt"] = {
            "url": audit.robots_url,
            "is_allowed": audit.robots_is_allowed,
            "matching_rule": audit.robots_matching_rule,
            "crawl_delay": audit.robots_crawl_delay,
            "raw_content_preview": audit.robots_raw_content[:800] if audit.robots_raw_content else None,
        }

    if audit.http_x_robots_tag or audit.http_server or audit.http_status_code:
        context["http"] = {
            "status_code": audit.http_status_code,
            "server": audit.http_server,
            "x_robots_tag": audit.http_x_robots_tag,
        }

    if audit.page_title or audit.meta_tags:
        context["page"] = {
            "title": audit.page_title,
            "meta_tags": audit.meta_tags,
        }

    if audit.evidence_matched_headers or audit.evidence_dom_signals or audit.evidence_matched_keywords:
        context["detection_evidence"] = {
            "status_code": audit.evidence_status_code,
            "matched_headers": audit.evidence_matched_headers,
            "dom_signals": audit.evidence_dom_signals,
            "matched_keywords": audit.evidence_matched_keywords,
        }

    special_instructions = []
    if audit.is_inconclusive_403:
        special_instructions.append(
            "CRITICAL NOTE: The crawler reported HTTP 403 Forbidden with verdict INCONCLUSIVE and NO specific anti-bot evidence. "
            "You MUST state that the cause is uncertain and that we cannot confirm AI crawler blocking. "
            "DO NOT claim Cloudflare, WAF, bot detection, or AI crawler blocking."
        )
    elif audit.issue_type == IssueType.ROBOTS_TXT_DISALLOW:
        special_instructions.append(
            f"Ground the remediation specifically on robots.txt rule '{audit.robots_matching_rule}'. "
            f"Show an exact robots.txt update allowing persona '{audit.persona}'."
        )
    elif audit.issue_type == IssueType.X_ROBOTS_TAG_RESTRICTION:
        special_instructions.append(
            f"Ground the remediation on HTTP header X-Robots-Tag: '{audit.http_x_robots_tag}'. "
            "Explain that this is an HTTP response header directive and show how to update server config (e.g. Nginx)."
        )
    elif audit.issue_type == IssueType.META_ROBOTS_RESTRICTION:
        special_instructions.append(
            "Ground the remediation on the HTML <meta name='robots'> tag in page head. "
            "Explain that this is an HTML document-level directive and show how to update HTML or CMS template."
        )
    elif audit.issue_type == IssueType.WAF_OR_CHALLENGE:
        special_instructions.append(
            f"Ground the remediation on detected mechanism '{audit.mechanism}' and observed signals: {audit.evidence_dom_signals + audit.evidence_matched_headers}. "
            "Provide a legitimate WAF configuration rule (e.g. allowlist/skip rule for verified AI bots) without suggesting security bypasses."
        )

    prompt = f"""Analyze the following crawler audit results and produce a structured remediation JSON object.

AUDIT CONTEXT:
{json.dumps(context, indent=2)}

SPECIAL INSTRUCTIONS:
{chr(10).join(f"- {inst}" for inst in special_instructions) if special_instructions else "- Analyze the observed facts and provide appropriate suggestions."}

Respond ONLY with a valid JSON object matching the required schema. Do not enclose in backticks or markdown if possible.
"""
    return prompt
