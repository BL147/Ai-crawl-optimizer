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

    # Weight definitions
    PENALTY_HTTP_403 = 25
    PENALTY_HTTP_429 = 15
    PENALTY_HTTP_5XX = 20
    PENALTY_WAF_CHALLENGE = 25
    PENALTY_CAPTCHA = 20
    PENALTY_AI_DISCREPANCY = 20
    PENALTY_ROBOTS_AI_BLOCKED = 15
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

        bots_data = audit_data.get("bots", {})
        browser_data = audit_data.get("browser", {})
        robots_data = audit_data.get("robots_txt", {})
        global_waf = audit_data.get("waf_detected")
        global_captcha = audit_data.get("captcha_detected", False)

        # 1. Check HTTP Status Across AI Bots
        blocked_bots = []
        rate_limited_bots = []
        server_error_bots = []

        for bot_name, bot_info in bots_data.items():
            status = bot_info.get("status", 200)
            if status == 403 or bot_info.get("blocked", False):
                blocked_bots.append(bot_name)
            elif status == 429:
                rate_limited_bots.append(bot_name)
            elif status >= 500:
                server_error_bots.append(bot_name)

        # Apply 403 penalty
        if blocked_bots:
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 403 Forbidden (Access Denied)",
                "penalty": -cls.PENALTY_HTTP_403,
                "severity": "CRITICAL",
                "detail": f"Forbidden status received for: {', '.join(blocked_bots)}"
            })
            score -= cls.PENALTY_HTTP_403

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
        waf_challenging = any(b.get("waf") and (b.get("blocked") or b.get("status") in [403, 429] or b.get("captcha")) for b in bots_data.values())
        if waf_challenging or (global_waf and any(b.get("blocked") for b in bots_data.values())):
            waf_name = next((b.get("waf") for b in bots_data.values() if b.get("waf")), global_waf or "WAF")
            penalties.append({
                "category": "Anti-Bot & WAF",
                "factor": f"Anti-Bot Shield Challenge ({waf_name})",
                "penalty": -cls.PENALTY_WAF_CHALLENGE,
                "severity": "CRITICAL",
                "detail": f"Automated JS challenge / managed rule from {waf_name} interferes with AI crawlers."
            })
            score -= cls.PENALTY_WAF_CHALLENGE

        # 3. CAPTCHA Detection
        has_captcha = global_captcha or any(b.get("captcha", False) for b in bots_data.values())
        if has_captcha:
            penalties.append({
                "category": "Anti-Bot & WAF",
                "factor": "Interactive CAPTCHA / Turnstile",
                "penalty": -cls.PENALTY_CAPTCHA,
                "severity": "CRITICAL",
                "detail": "Headless AI agents cannot solve visual/interactive challenges and abandon crawl."
            })
            score -= cls.PENALTY_CAPTCHA

        # 4. AI-Specific Failure / Discrepancy
        # If regular browser gets 200 OK, but AI bots are blocked
        browser_ok = browser_data.get("status") == 200
        ai_blocked_while_browser_ok = browser_ok and len(blocked_bots) > 0
        if ai_blocked_while_browser_ok:
            penalties.append({
                "category": "AI Crawler Parity",
                "factor": "AI Bot Discrepancy (Browser 200 vs Bot 403)",
                "penalty": -cls.PENALTY_AI_DISCREPANCY,
                "severity": "CRITICAL",
                "detail": "Site serves human visitors normally but selectively blocks generative AI search crawlers."
            })
            score -= cls.PENALTY_AI_DISCREPANCY

        # 5. Robots.txt Check
        robots_ai_disallowed = robots_data.get("ai_disallowed", False)
        if robots_ai_disallowed:
            penalties.append({
                "category": "Robots.txt Policy",
                "factor": "Robots.txt AI Crawl Disallow",
                "penalty": -cls.PENALTY_ROBOTS_AI_BLOCKED,
                "severity": "MEDIUM",
                "detail": "Robots.txt policy instructs AI search agents (GPTBot/ClaudeBot/CCBot) not to index."
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
