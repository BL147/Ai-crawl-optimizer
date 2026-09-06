"""
scoring.py - AI Crawlability Scoring Engine
Author: Shlok (System Integrator)

Calculates a standardized 0-100 crawlability score based on:
1. HTTP Status Code Penalties (403, 429, 5xx)
2. WAF & Anti-Bot Detection (Cloudflare, Turnstile, CAPTCHA, DataDome)
3. AI Bot Discrepancy (Browser 200 vs AI bot 403/block)
4. Robots.txt Compliance & AI crawler directives
5. Latency & Crawl Budget Performance
"""

from typing import Dict, List, Any, Optional

class ScoringEngine:
    """
    Computes an AI Crawlability Score (0 - 100), letter grade, and detailed breakdown.
    """

    # Base score
    BASE_SCORE = 100

    # Weight definitions (exact spec from prompt)
    PENALTY_HTTP_403 = 20
    PENALTY_HTTP_429 = 10
    PENALTY_HTTP_5XX = 15
    PENALTY_WAF_CHALLENGE = 20
    PENALTY_CAPTCHA = 25
    PENALTY_AI_DISCREPANCY = 20
    PENALTY_ROBOTS_AI_BLOCKED = 10
    PENALTY_HIGH_LATENCY = 10

    @classmethod
    def calculate(cls, audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates the score and generates full breakdown.

        Expected audit_data format:
        {
            "browser": {"status": 200, "latency_ms": 210},
            "bots": {
                "gpt_bot": {"status": 403, "waf": "Cloudflare", "captcha": True, "latency_ms": 120, "blocked": True},
                "claude_bot": {"status": 403, "waf": "Cloudflare", "captcha": True, "latency_ms": 115, "blocked": True},
                "perplexity_bot": {"status": 403, "waf": "Cloudflare", "captcha": True, "latency_ms": 130, "blocked": True},
                "google_bot": {"status": 200, "waf": None, "captcha": False, "latency_ms": 180, "blocked": False}
            },
            "robots_txt": {
                "status": 200,
                "ai_disallowed": True, # or list of disallowed bot names
                "details": "Disallow: / for GPTBot"
            },
            "waf_detected": "Cloudflare", # or None
            "captcha_detected": True # or False
        }
        """
        score = cls.BASE_SCORE
        penalties: List[Dict[str, Any]] = []

        # Normalize input to handle Anshul's crawler models, baseline audits, or legacy dicts
        normalized = cls._normalize_input(audit_data)
        bots_data = normalized["bots"]
        browser_data = normalized["browser"]
        robots_data = normalized["robots_txt"]
        global_waf = normalized["waf_detected"]
        global_captcha = normalized["captcha_detected"]
        selective_ai_block = normalized.get("selective_ai_block_detected", False)

        # 1. Check HTTP Status Across AI Bots
        blocked_bots = []
        inconclusive_403_bots = []
        rate_limited_bots = []
        server_error_bots = []

        for bot_name, bot_info in bots_data.items():
            status = bot_info.get("status", 200)
            verdict = bot_info.get("verdict", "")
            is_blocked = bot_info.get("blocked", False) or (status in [401, 403] and verdict != "INCONCLUSIVE")

            if is_blocked or verdict in ["BLOCKED", "CHALLENGED"]:
                blocked_bots.append(bot_name)
            elif status == 403 and verdict == "INCONCLUSIVE":
                inconclusive_403_bots.append(bot_name)
            elif status == 429 or bot_info.get("mechanism") == "HTTP_429_RATE_LIMITED":
                rate_limited_bots.append(bot_name)
            elif status >= 500:
                server_error_bots.append(bot_name)

        # Apply 403 / Access Denied penalty
        if blocked_bots:
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 403 Forbidden (Access Denied)",
                "penalty": -cls.PENALTY_HTTP_403,
                "severity": "CRITICAL",
                "detail": f"AI search crawlers blocked for: {', '.join(blocked_bots)}"
            })
            score -= cls.PENALTY_HTTP_403
        elif inconclusive_403_bots:
            # Anshul Rule 11: Inconclusive 403 without active bot challenge
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 403 Forbidden (Inconclusive)",
                "penalty": -15,
                "severity": "HIGH",
                "detail": f"HTTP 403 returned without conclusive bot-shield signatures for: {', '.join(inconclusive_403_bots)}"
            })
            score -= 15

        # Apply 429 penalty
        if rate_limited_bots:
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 429 Too Many Requests (Rate Limited)",
                "penalty": -cls.PENALTY_HTTP_429,
                "severity": "HIGH",
                "detail": f"Rate limit / throttling triggered for: {', '.join(rate_limited_bots)}"
            })
            score -= cls.PENALTY_HTTP_429

        # Apply 5xx penalty
        if server_error_bots:
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 5xx Server Error",
                "penalty": -cls.PENALTY_HTTP_5XX,
                "severity": "HIGH",
                "detail": f"Server failure during crawl for: {', '.join(server_error_bots)}"
            })
            score -= cls.PENALTY_HTTP_5XX

        # 2. WAF & Challenge Detection (only penalize if WAF challenged or blocked bots)
        waf_challenging = any(
            b.get("verdict") == "CHALLENGED" or
            (b.get("mechanism") and b.get("mechanism") not in ["NONE", "HTTP_FORBIDDEN", "INCONCLUSIVE"]) or
            (b.get("waf") and (b.get("blocked") or b.get("status") in [403, 429] or b.get("captcha")))
            for b in bots_data.values()
        )
        if waf_challenging or (global_waf and any(b.get("blocked") for b in bots_data.values())):
            waf_name = next(
                (b.get("waf") or b.get("mechanism") for b in bots_data.values() if b.get("waf") or (b.get("mechanism") and b.get("mechanism") != "NONE")),
                global_waf or "WAF"
            )
            penalties.append({
                "category": "Anti-Bot & WAF",
                "factor": f"Anti-Bot Shield Challenge ({waf_name})",
                "penalty": -cls.PENALTY_WAF_CHALLENGE,
                "severity": "CRITICAL",
                "detail": f"Automated JS challenge / managed rule ({waf_name}) intercepts AI crawlers."
            })
            score -= cls.PENALTY_WAF_CHALLENGE

        # 3. CAPTCHA Detection
        has_captcha = global_captcha or any(
            b.get("captcha", False) or
            any("turnstile" in s.lower() or "captcha" in s.lower() for s in b.get("signals", []))
            for b in bots_data.values()
        )
        if has_captcha:
            penalties.append({
                "category": "Anti-Bot & WAF",
                "factor": "Interactive CAPTCHA / Turnstile",
                "penalty": -cls.PENALTY_CAPTCHA,
                "severity": "CRITICAL",
                "detail": "Headless AI agents cannot solve visual/interactive challenges and abandon crawl."
            })
            score -= cls.PENALTY_CAPTCHA

        # 4. AI-Specific Failure / Discrepancy (Browser 200 vs AI Bot Block)
        browser_ok = browser_data.get("status") == 200 and not browser_data.get("blocked", False)
        ai_blocked_while_browser_ok = selective_ai_block or (browser_ok and len(blocked_bots) > 0)
        if ai_blocked_while_browser_ok:
            penalties.append({
                "category": "AI Crawler Parity",
                "factor": "AI Bot Discrepancy (Browser 200 vs Bot 403)",
                "penalty": -cls.PENALTY_AI_DISCREPANCY,
                "severity": "CRITICAL",
                "detail": "Site serves human visitors normally but selectively blocks generative AI search crawlers."
            })
            score -= cls.PENALTY_AI_DISCREPANCY

        # 5. Robots.txt Check (RFC 9309 Compliance)
        robots_ai_disallowed = robots_data.get("ai_disallowed", False) or (robots_data.get("is_allowed") is False)
        if robots_ai_disallowed:
            matching_rule = robots_data.get("matching_rule") or robots_data.get("details") or "Disallow: /"
            penalties.append({
                "category": "Robots.txt Policy",
                "factor": "Robots.txt AI Crawl Disallow",
                "penalty": -cls.PENALTY_ROBOTS_AI_BLOCKED,
                "severity": "MEDIUM",
                "detail": f"Robots.txt policy instructs AI search agents not to index ({matching_rule})."
            })
            score -= cls.PENALTY_ROBOTS_AI_BLOCKED

        # 6. Latency Check
        high_latency_bots = [
            b for b, data in bots_data.items()
            if data.get("latency_ms", 0) > 3000
        ]
        if high_latency_bots or browser_data.get("latency_ms", 0) > 3000:
            penalties.append({
                "category": "Performance",
                "factor": "High Response Latency (> 3.0s)",
                "penalty": -cls.PENALTY_HIGH_LATENCY,
                "severity": "LOW",
                "detail": f"Slow response degrades AI crawl budget: {', '.join(high_latency_bots) if high_latency_bots else 'Server'}"
            })
            score -= cls.PENALTY_HIGH_LATENCY

        # Clamp score between 0 and 100
        final_score = max(0, min(100, score))

        # Determine grade and visual badge status
        grade, status, color = cls._get_grade(final_score)

        return {
            "score": final_score,
            "grade": grade,
            "status": status,
            "color": color,
            "base_score": cls.BASE_SCORE,
            "total_deductions": cls.BASE_SCORE - final_score,
            "penalties": penalties,
            "summary": cls._build_summary(final_score, penalties)
        }

    @classmethod
    def _normalize_input(cls, audit_data: Any) -> Dict[str, Any]:
        """
        Normalizes diverse input shapes into a standardized audit contract:
        1. Baseline audit dict: {"target_persona": {...}, "baseline_browser": {...}, "selective_ai_block_detected": bool}
        2. Single Anshul CrawlResult dict: {"persona": "gptbot", "detection": {...}, "http": {...}, ...}
        3. List of Anshul CrawlResults
        4. Legacy dict: {"bots": {...}, "browser": {...}, "robots_txt": {...}}
        """
        if not isinstance(audit_data, dict):
            return {
                "bots": {},
                "browser": {"status": 200, "latency_ms": 100},
                "robots_txt": {"is_allowed": True},
                "waf_detected": None,
                "captcha_detected": False,
                "selective_ai_block_detected": False,
            }

        # Case 1: Baseline comparison format (crawl_with_baseline)
        if "target_persona" in audit_data and isinstance(audit_data["target_persona"], dict):
            tp = audit_data["target_persona"]
            bb = audit_data.get("baseline_browser", {})
            bot_entry = cls._extract_single_bot(tp)
            browser_entry = cls._extract_single_bot(bb)
            return {
                "bots": {tp.get("persona", "gptbot"): bot_entry},
                "browser": browser_entry,
                "robots_txt": tp.get("robots_txt", {}),
                "waf_detected": bot_entry.get("waf"),
                "captcha_detected": bot_entry.get("captcha", False),
                "selective_ai_block_detected": audit_data.get("selective_ai_block_detected", False),
            }

        # Case 2: Direct single Anshul CrawlResult dict
        if "detection" in audit_data and "http" in audit_data:
            bot_entry = cls._extract_single_bot(audit_data)
            persona_name = audit_data.get("persona", "gptbot")
            return {
                "bots": {persona_name: bot_entry},
                "browser": {"status": 200, "latency_ms": 150},
                "robots_txt": audit_data.get("robots_txt", {}),
                "waf_detected": bot_entry.get("waf"),
                "captcha_detected": bot_entry.get("captcha", False),
                "selective_ai_block_detected": False,
            }

        # Case 3: List of results (e.g. crawl_all_personas) wrapped in a dict or raw
        if "results" in audit_data and isinstance(audit_data["results"], list):
            bots = {}
            browser = {"status": 200, "latency_ms": 150}
            robots_txt = {}
            for item in audit_data["results"]:
                p = item.get("persona", "unknown")
                entry = cls._extract_single_bot(item)
                if p == "standard_browser":
                    browser = entry
                else:
                    bots[p] = entry
                if item.get("robots_txt") and not robots_txt:
                    robots_txt = item.get("robots_txt")
            global_waf = next((b.get("waf") for b in bots.values() if b.get("waf")), None)
            global_cap = any(b.get("captcha") for b in bots.values())
            return {
                "bots": bots,
                "browser": browser,
                "robots_txt": robots_txt,
                "waf_detected": global_waf,
                "captcha_detected": global_cap,
                "selective_ai_block_detected": any(b.get("blocked") for b in bots.values()) and browser.get("status") == 200,
            }

        # Case 4: Standard legacy dictionary format
        return {
            "bots": audit_data.get("bots", {}),
            "browser": audit_data.get("browser", {"status": 200, "latency_ms": 150}),
            "robots_txt": audit_data.get("robots_txt", {}),
            "waf_detected": audit_data.get("waf_detected"),
            "captcha_detected": audit_data.get("captcha_detected", False),
            "selective_ai_block_detected": audit_data.get("selective_ai_block_detected", False),
        }

    @staticmethod
    def _extract_single_bot(res: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts normalized metrics from Anshul's CrawlResult dictionary."""
        http_data = res.get("http", {})
        det = res.get("detection", {})
        inf = det.get("inference", {})
        ev = det.get("evidence", {})

        status = http_data.get("status_code", 200)
        latency = http_data.get("response_time_ms", 0) or 0
        verdict = str(inf.get("verdict", "ACCESSIBLE")).upper()
        mechanism = str(inf.get("mechanism", "NONE")).upper()
        confidence = float(inf.get("confidence", 0.0))

        dom_signals = ev.get("dom_signals", [])
        matched_headers = ev.get("matched_headers", [])
        matched_keywords = ev.get("matched_keywords", [])

        is_blocked = det.get("is_blocked", False) or verdict in ["BLOCKED", "CHALLENGED"]
        has_captcha = any(
            "turnstile" in s.lower() or "captcha" in s.lower() or "challenge" in s.lower()
            for s in (dom_signals + matched_keywords + [mechanism])
        )

        waf_name = None
        if "CLOUDFLARE" in mechanism:
            waf_name = "Cloudflare"
        elif "DATADOME" in mechanism:
            waf_name = "DataDome"
        elif "PERIMETERX" in mechanism:
            waf_name = "PerimeterX"
        elif "AWS_WAF" in mechanism:
            waf_name = "AWS WAF"
        elif "AKAMAI" in mechanism:
            waf_name = "Akamai"
        elif any("cloudflare" in h.lower() for h in matched_headers):
            waf_name = "Cloudflare"
        elif mechanism != "NONE" and "HTTP" not in mechanism:
            waf_name = mechanism

        return {
            "status": status,
            "latency_ms": int(latency),
            "blocked": is_blocked,
            "verdict": verdict,
            "mechanism": mechanism,
            "confidence": confidence,
            "waf": waf_name,
            "captcha": has_captcha,
            "signals": dom_signals + matched_headers + matched_keywords,
            "raw": res,
        }

    @staticmethod
    def _get_grade(score: int):
        if score >= 90:
            return "A", "AI OPTIMIZED", "#10B981"  # Emerald Green
        elif score >= 75:
            return "B", "PARTIALLY ACCESSIBLE", "#3B82F6"  # Blue
        elif score >= 50:
            return "C", "DEGRADED ACCESS", "#F59E0B"  # Amber
        else:
            return "F", "AI CRAWL BLOCKED", "#EF4444"  # Red

    @staticmethod
    def _build_summary(score: int, penalties: List[Dict[str, Any]]) -> str:
        if score >= 90:
            return "Excellent AI crawlability! Search agents (ChatGPT, Perplexity, Claude) can index your site seamlessly."
        elif score >= 75:
            return "Good baseline accessibility, but minor friction points (rate limits or robots rules) may reduce AI crawl coverage."
        elif score >= 50:
            return "Substantial AI accessibility issues detected. Crawlers encounter challenges or delays that harm AI visibility."
        else:
            critical_reasons = [p['factor'] for p in penalties if p.get('severity') == 'CRITICAL']
            reasons_str = ", ".join(critical_reasons[:2]) if critical_reasons else "strict anti-bot barriers"
            return f"Severe AI Crawl Blockage: AI agents are blocked due to {reasons_str}. Your site is invisible to generative AI search."


# Helper convenience function
def calculate_score(audit_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience functional interface for scoring."""
    return ScoringEngine.calculate(audit_data)


if __name__ == "__main__":
    # Quick self-test
    mock_blocked = {
        "browser": {"status": 200, "latency_ms": 180},
        "bots": {
            "gpt_bot": {"status": 403, "waf": "Cloudflare", "captcha": True, "latency_ms": 95, "blocked": True},
            "claude_bot": {"status": 403, "waf": "Cloudflare", "captcha": True, "latency_ms": 90, "blocked": True},
            "perplexity_bot": {"status": 403, "waf": "Cloudflare", "captcha": True, "latency_ms": 110, "blocked": True},
            "google_bot": {"status": 200, "waf": None, "captcha": False, "latency_ms": 150, "blocked": False}
        },
        "robots_txt": {"status": 200, "ai_disallowed": True},
        "waf_detected": "Cloudflare",
        "captcha_detected": True
    }
    result = calculate_score(mock_blocked)
    print("=== TEST BLOCKED (BEFORE) ===")
    print(f"Score: {result['score']}/100 (Grade: {result['grade']}) - {result['status']}")
    for p in result['penalties']:
        print(f"  [{p['severity']}] {p['factor']} ({p['penalty']} pts)")

    mock_optimized = {
        "browser": {"status": 200, "latency_ms": 150},
        "bots": {
            "gpt_bot": {"status": 200, "waf": None, "captcha": False, "latency_ms": 140, "blocked": False},
            "claude_bot": {"status": 200, "waf": None, "captcha": False, "latency_ms": 135, "blocked": False},
            "perplexity_bot": {"status": 200, "waf": None, "captcha": False, "latency_ms": 145, "blocked": False},
            "google_bot": {"status": 200, "waf": None, "captcha": False, "latency_ms": 140, "blocked": False}
        },
        "robots_txt": {"status": 200, "ai_disallowed": False},
        "waf_detected": None,
        "captcha_detected": False
    }
    result_opt = calculate_score(mock_optimized)
    print("\n=== TEST OPTIMIZED (AFTER) ===")
    print(f"Score: {result_opt['score']}/100 (Grade: {result_opt['grade']}) - {result_opt['status']}")
