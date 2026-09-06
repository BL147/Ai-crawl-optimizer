"""
shlok.py - AI Crawl Optimizer: Master System Integration
Author: Shlok (System Integrator)
Branch: shlok

Contains all System Integrator backend responsibilities in one self-contained file:
1. Scoring Engine: Base 100, exact deduction weights, letter grades.
2. Backend Orchestrator: run_audit(url) -> dict for frontend consumption.
3. Demo Sandbox: Controlled server demonstrating BEFORE (AI 403) vs AFTER (AI 200).
4. Integration Self-Test: Automated test verifying BEFORE vs AFTER transitions.

Usage for Frontend (K):
    from shlok import run_audit
    result = run_audit("https://example.com")
"""

import sys
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import requests
from flask import Flask, request, Response, jsonify

__all__ = [
    "run_audit",
    "calculate_score",
    "ScoringEngine",
    "start_sandbox",
    "set_mode",
    "get_mode",
    "run_integration_test"
]

# =====================================================================
# 1. SCORING ENGINE (Exact Hackathon Deduction Weights)
# =====================================================================

class ScoringEngine:
    """
    Computes an AI Crawlability Score (0 - 100), letter grade, and penalty logs.
    """
    BASE_SCORE = 100

    # Exact weights from specification:
    PENALTY_HTTP_403 = 20           # 403 -> -20
    PENALTY_HTTP_429 = 10           # 429 -> -10
    PENALTY_WAF_CHALLENGE = 20      # challenge -> -20
    PENALTY_CAPTCHA = 25            # captcha -> -25
    PENALTY_AI_DISCREPANCY = 20     # AI-specific failure -> -20
    PENALTY_ROBOTS_ISSUE = 10       # robots issue -> -10
    PENALTY_HTTP_5XX = 15
    PENALTY_HIGH_LATENCY = 10

    @classmethod
    def calculate(cls, audit_data: Dict[str, Any]) -> Dict[str, Any]:
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
            if bot_name == "browser_chrome" or bot_name == "google_bot":
                continue
            status = bot_info.get("status", 200)
            if status == 403 or bot_info.get("blocked", False):
                blocked_bots.append(bot_name)
            elif status == 429:
                rate_limited_bots.append(bot_name)
            elif status >= 500:
                server_error_bots.append(bot_name)

        # 403 Penalty (-20)
        if blocked_bots:
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 403 Forbidden",
                "penalty": -cls.PENALTY_HTTP_403,
                "severity": "CRITICAL",
                "detail": f"Access denied for AI bots: {', '.join(blocked_bots)}"
            })
            score -= cls.PENALTY_HTTP_403

        # 429 Penalty (-10)
        if rate_limited_bots:
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 429 Rate Limited",
                "penalty": -cls.PENALTY_HTTP_429,
                "severity": "HIGH",
                "detail": f"Rate limit triggered for: {', '.join(rate_limited_bots)}"
            })
            score -= cls.PENALTY_HTTP_429

        # 5xx Penalty (-15)
        if server_error_bots:
            penalties.append({
                "category": "HTTP Status",
                "factor": "HTTP 5xx Server Error",
                "penalty": -cls.PENALTY_HTTP_5XX,
                "severity": "HIGH",
                "detail": f"Server errors during crawl: {', '.join(server_error_bots)}"
            })
            score -= cls.PENALTY_HTTP_5XX

        # 2. WAF Challenge Penalty (-20)
        waf_challenging = any(b.get("waf") and (b.get("blocked") or b.get("status") in [403, 429] or b.get("captcha")) for b in bots_data.values())
        if waf_challenging or (global_waf and any(b.get("blocked") for b in bots_data.values())):
            waf_name = next((b.get("waf") for b in bots_data.values() if b.get("waf")), global_waf or "Cloudflare")
            penalties.append({
                "category": "Anti-Bot & WAF",
                "factor": f"WAF Challenge Detected ({waf_name})",
                "penalty": -cls.PENALTY_WAF_CHALLENGE,
                "severity": "CRITICAL",
                "detail": f"JS Challenge / Managed Rule from {waf_name} interferes with AI crawlers."
            })
            score -= cls.PENALTY_WAF_CHALLENGE

        # 3. CAPTCHA Penalty (-25)
        has_captcha = global_captcha or any(b.get("captcha", False) for b in bots_data.values())
        if has_captcha:
            penalties.append({
                "category": "Anti-Bot & WAF",
                "factor": "CAPTCHA / Turnstile Challenge",
                "penalty": -cls.PENALTY_CAPTCHA,
                "severity": "CRITICAL",
                "detail": "Headless AI search agents cannot solve visual/interactive challenges."
            })
            score -= cls.PENALTY_CAPTCHA

        # 4. AI-Specific Failure (-20)
        # Browser gets 200 OK, but AI bots are blocked
        browser_ok = browser_data.get("status") == 200
        if browser_ok and len(blocked_bots) > 0:
            penalties.append({
                "category": "AI Crawler Parity",
                "factor": "AI-Specific Crawl Block (Browser 200 vs AI 403)",
                "penalty": -cls.PENALTY_AI_DISCREPANCY,
                "severity": "CRITICAL",
                "detail": "Site serves humans normally but selectively blocks generative AI search crawlers."
            })
            score -= cls.PENALTY_AI_DISCREPANCY

        # 5. Robots.txt Issue (-10)
        if robots_data.get("ai_disallowed", False):
            penalties.append({
                "category": "Robots.txt Policy",
                "factor": "Robots.txt Disallow on AI Bots",
                "penalty": -cls.PENALTY_ROBOTS_ISSUE,
                "severity": "MEDIUM",
                "detail": "Robots.txt instructs AI search engines (GPTBot, ClaudeBot, CCBot) not to index."
            })
            score -= cls.PENALTY_ROBOTS_ISSUE

        # 6. Latency Penalty (-10)
        high_latency = [b for b, d in bots_data.items() if d.get("latency_ms", 0) > 3000]
        if high_latency:
            penalties.append({
                "category": "Performance",
                "factor": "High Latency (> 3.0s)",
                "penalty": -cls.PENALTY_HIGH_LATENCY,
                "severity": "LOW",
                "detail": f"Slow response degrades crawl budget: {', '.join(high_latency)}"
            })
            score -= cls.PENALTY_HIGH_LATENCY

        # Final score clamped between 0 and 100
        final_score = max(0, min(100, score))
        grade, status_text, color = cls._get_grade(final_score)

        return {
            "score": final_score,
            "grade": grade,
            "status": status_text,
            "color": color,
            "base_score": cls.BASE_SCORE,
            "total_deductions": cls.BASE_SCORE - final_score,
            "penalties": penalties,
            "summary": cls._build_summary(final_score, penalties)
        }

    @staticmethod
    def _get_grade(score: int):
        if score >= 90:
            return "A", "AI OPTIMIZED", "#10B981"
        elif score >= 75:
            return "B", "PARTIALLY ACCESSIBLE", "#3B82F6"
        elif score >= 50:
            return "C", "DEGRADED ACCESS", "#F59E0B"
        else:
            return "F", "AI CRAWL BLOCKED", "#EF4444"

    @staticmethod
    def _build_summary(score: int, penalties: List[Dict[str, Any]]) -> str:
        if score >= 90:
            return "Excellent AI crawlability! Search agents (ChatGPT, Claude, Perplexity) can index seamlessly."
        elif score >= 75:
            return "Good baseline accessibility, but minor friction points exist."
        elif score >= 50:
            return "Substantial AI accessibility issues detected. Crawlers encounter challenges."
        else:
            reasons = [p['factor'] for p in penalties if p.get('severity') == 'CRITICAL']
            reasons_str = ", ".join(reasons[:2]) if reasons else "strict WAF barriers"
            return f"Severe AI Crawl Blockage: AI agents are blocked due to {reasons_str}."


def calculate_score(audit_data: Dict[str, Any]) -> Dict[str, Any]:
    return ScoringEngine.calculate(audit_data)


# =====================================================================
# 2. DEMO SANDBOX SERVER (BEFORE vs AFTER)
# =====================================================================

sandbox_app = Flask("sandbox_demo")
_SANDBOX_MODE = "before"
_SANDBOX_THREAD = None

AI_AGENTS = ["gptbot", "chatgpt", "claudebot", "claude-web", "perplexitybot", "ccbot", "bytespider"]

SANDBOX_CLOUDFLARE_HTML = """<!DOCTYPE html>
<html>
<head><title>Just a moment... | Cloudflare Challenge</title></head>
<body style="font-family:sans-serif; text-align:center; padding:50px; background:#f4f4f5;">
    <div style="background:white; max-width:500px; margin:auto; padding:30px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <h2 style="color:#d97706;">Checking your browser before accessing apexcloud.io</h2>
        <p>This process is automatic. Cloudflare Ray ID: <strong>89f4c3a218d0-BOM</strong></p>
        <p style="font-size:12px; color:#888;">Performance &amp; security by Cloudflare &bull; cf-mitigated: challenge</p>
    </div>
</body>
</html>"""

SANDBOX_WEBSITE_HTML = """<!DOCTYPE html>
<html>
<head><title>ApexCloud AI - Enterprise Cloud Infrastructure</title></head>
<body style="font-family:sans-serif; background:#0f172a; color:#f8fafc; padding:40px;">
    <h1>⚡ ApexCloud Enterprise GPU Infrastructure</h1>
    <p>Powers Fortune 500 AI pipelines with distributed H100 clusters and sub-millisecond inference.</p>
</body>
</html>"""

@sandbox_app.route("/", methods=["GET"])
def _sandbox_home():
    global _SANDBOX_MODE
    ua = request.headers.get("User-Agent", "").lower()
    is_ai = any(bot in ua for bot in AI_AGENTS)

    # BEFORE MODE: AI crawlers get 403 with Cloudflare challenge
    if _SANDBOX_MODE == "before" and is_ai:
        headers = {
            "Server": "cloudflare",
            "cf-ray": "89f4c3a218d0-BOM",
            "cf-mitigated": "challenge",
            "Content-Type": "text/html"
        }
        return Response(SANDBOX_CLOUDFLARE_HTML, status=403, headers=headers)

    # AFTER MODE OR BROWSER: 200 OK
    headers = {"Server": "cloudflare", "Content-Type": "text/html"}
    if _SANDBOX_MODE == "after" and is_ai:
        headers["x-ai-optimized"] = "true"
    return Response(SANDBOX_WEBSITE_HTML, status=200, headers=headers)

@sandbox_app.route("/robots.txt", methods=["GET"])
def _sandbox_robots():
    global _SANDBOX_MODE
    if _SANDBOX_MODE == "before":
        body = "User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nDisallow: /\n\nUser-agent: ClaudeBot\nDisallow: /\n"
    else:
        body = "User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /\n"
    return Response(body, mimetype="text/plain")

@sandbox_app.route("/api/sandbox/mode", methods=["GET", "POST"])
def _sandbox_api_mode():
    global _SANDBOX_MODE
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        mode = data.get("mode", "").lower()
        if mode in ["before", "after"]:
            _SANDBOX_MODE = mode
            return jsonify({"status": "success", "mode": _SANDBOX_MODE})
    return jsonify({"mode": _SANDBOX_MODE})

@sandbox_app.route("/api/sandbox/toggle", methods=["POST", "GET"])
def _sandbox_api_toggle():
    global _SANDBOX_MODE
    _SANDBOX_MODE = "after" if _SANDBOX_MODE == "before" else "before"
    return jsonify({"status": "success", "mode": _SANDBOX_MODE})

def set_mode(mode: str):
    global _SANDBOX_MODE
    if mode in ["before", "after"]:
        _SANDBOX_MODE = mode

def get_mode() -> str:
    global _SANDBOX_MODE
    return _SANDBOX_MODE

def start_sandbox(port: int = 5050) -> str:
    global _SANDBOX_THREAD
    if _SANDBOX_THREAD is None or not _SANDBOX_THREAD.is_alive():
        _SANDBOX_THREAD = threading.Thread(
            target=lambda: sandbox_app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
            daemon=True
        )
        _SANDBOX_THREAD.start()
        time.sleep(0.8)
    return f"http://127.0.0.1:{port}"


# =====================================================================
# 3. BACKEND ORCHESTRATOR (run_audit)
# =====================================================================

EMULATION_PROFILES = {
    "browser_chrome": {
        "name": "Standard Chrome Browser",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    },
    "gpt_bot": {
        "name": "OpenAI GPTBot",
        "ua": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)"
    },
    "claude_bot": {
        "name": "Anthropic ClaudeBot",
        "ua": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"
    },
    "perplexity_bot": {
        "name": "Perplexity AI Crawler",
        "ua": "PerplexityBot/1.0 (+https://perplexity.ai/perplexitybot)"
    },
    "google_bot": {
        "name": "Googlebot",
        "ua": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    }
}

def _fetch_agent(url: str, ua: str, timeout: float = 5.0) -> Dict[str, Any]:
    headers = {"User-Agent": ua, "Accept": "text/html,*/*"}
    start = time.time()
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        latency_ms = int((time.time() - start) * 1000)
        h_lower = {k.lower(): v.lower() for k, v in resp.headers.items()}
        t_lower = resp.text[:4000].lower()

        waf = None
        if "cf-ray" in h_lower or ("server" in h_lower and "cloudflare" in h_lower["server"]):
            waf = "Cloudflare"

        captcha = (
            ("cf-mitigated" in h_lower and h_lower["cf-mitigated"] == "challenge") or
            any(sig in t_lower for sig in ["turnstile", "recaptcha", "checking your browser", "just a moment..."])
        )

        blocked = (resp.status_code in [401, 403, 429]) or captcha

        return {
            "status": resp.status_code,
            "latency_ms": latency_ms,
            "blocked": blocked,
            "waf": waf if blocked else None,
            "captcha": captcha,
            "headers": dict(resp.headers),
            "snippet": resp.text[:400]
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

def _fetch_robots(base_url: str) -> Dict[str, Any]:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=4.0)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            current_ua = ""
            ai_disallowed = False
            for line in lines:
                l = line.strip().lower()
                if l.startswith("user-agent:"):
                    current_ua = l.split(":", 1)[1].strip()
                elif l.startswith("disallow:") and "/" in l:
                    if any(bot in current_ua for bot in ["gptbot", "claudebot", "perplexitybot"]):
                        ai_disallowed = True
            return {"status": 200, "ai_disallowed": ai_disallowed, "snippet": resp.text[:400]}
        return {"status": resp.status_code, "ai_disallowed": False, "snippet": f"HTTP {resp.status_code}"}
    except Exception:
        return {"status": 500, "ai_disallowed": False, "snippet": "Failed to fetch robots.txt"}

def _generate_fixes(scoring_result: Dict[str, Any]) -> Dict[str, Any]:
    penalties = scoring_result.get("penalties", [])
    has_waf = any("WAF" in p["factor"] or "403" in p["factor"] for p in penalties)
    has_robots = any("Robots" in p["factor"] for p in penalties)

    root_causes = []
    actions = []

    if has_waf:
        root_causes.append("Cloudflare WAF managed challenge blocks AI search crawlers by default.")
        actions.append("Add Cloudflare WAF Custom Rule with action 'Skip' for AI user agents.")
    if has_robots:
        root_causes.append("Robots.txt contains explicit disallow rules for AI agents.")
        actions.append("Update robots.txt with 'Allow: /' for GPTBot and ClaudeBot.")
    if not root_causes:
        root_causes.append("Site is accessible to AI search engines.")
        actions.append("Maintain low TTFB response latency.")

    waf_rule = '(http.user_agent contains "GPTBot" or http.user_agent contains "ClaudeBot") and not cf.client.bot'
    robots_txt = "User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /\n\nUser-agent: *\nAllow: /\n"

    return {
        "root_cause": " ".join(root_causes),
        "cloudflare_waf_rule": waf_rule,
        "robots_txt_fix": robots_txt,
        "action_items": actions
    }

def run_audit(url: str) -> Dict[str, Any]:
    """
    Main Orchestrator Entrypoint.
    Usage for K (Frontend):
        result = run_audit(url)
    """
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"

    # Auto-start sandbox if auditing localhost:5050
    if "5050" in clean_url or "sandbox" in clean_url.lower():
        start_sandbox(port=5050)
        clean_url = "http://127.0.0.1:5050"

    timestamp = datetime.now(timezone.utc).isoformat()

    # 1. Multi-bot crawl
    bot_results = {}
    for bot_id, meta in EMULATION_PROFILES.items():
        bot_results[bot_id] = _fetch_agent(clean_url, meta["ua"])

    browser_data = bot_results.get("browser_chrome", {"status": 200, "latency_ms": 150})

    # 2. Check robots.txt
    robots_data = _fetch_robots(clean_url)

    # 3. Detection
    global_waf = next((b.get("waf") for b in bot_results.values() if b.get("waf")), None)
    global_captcha = any(b.get("captcha") for b in bot_results.values())

    audit_payload = {
        "browser": browser_data,
        "bots": bot_results,
        "robots_txt": robots_data,
        "waf_detected": global_waf,
        "captcha_detected": global_captcha
    }

    # 4. Scoring Engine
    scoring_result = calculate_score(audit_payload)

    # 5. Fixes
    recommendations = _generate_fixes(scoring_result)

    # 6. Contract package for K
    return {
        "url": clean_url,
        "timestamp": timestamp,
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
        "ai_recommendations": recommendations,
        "status": "success"
    }


# =====================================================================
# 4. INTEGRATION TEST
# =====================================================================

def run_integration_test():
    """Runs automated integration test verifying BEFORE and AFTER modes."""
    print("=" * 60)
    print("RUNNING SYSTEM INTEGRATOR SELF-TEST")
    print("=" * 60)

    sandbox_url = start_sandbox(port=5055)
    print(f"[1] Sandbox running on {sandbox_url}")

    # Phase 1: BEFORE mode
    set_mode("before")
    audit_before = run_audit(sandbox_url)
    score_b = audit_before["summary"]["score"]
    grade_b = audit_before["summary"]["grade"]
    print(f"[2] BEFORE Mode Audit -> Score: {score_b}/100, Grade: {grade_b}")
    assert score_b < 50, f"Expected low score in BEFORE mode, got {score_b}"
    assert grade_b == "F", f"Expected Grade F, got {grade_b}"
    assert audit_before["bot_matrix"]["gpt_bot"]["status"] == 403, "GPTBot should be 403"
    print("    [PASS] BEFORE mode verified (AI blocked with 403).")

    # Phase 2: AFTER mode
    set_mode("after")
    audit_after = run_audit(sandbox_url)
    score_a = audit_after["summary"]["score"]
    grade_a = audit_after["summary"]["grade"]
    print(f"[3] AFTER Mode Audit -> Score: {score_a}/100, Grade: {grade_a}")
    assert score_a >= 90, f"Expected Grade A score in AFTER mode, got {score_a}"
    assert grade_a == "A", f"Expected Grade A, got {grade_a}"
    assert audit_after["bot_matrix"]["gpt_bot"]["status"] == 200, "GPTBot should be 200"
    print("    [PASS] AFTER mode verified (AI optimized with 200).")

    # Phase 3: Contract verification for K
    for key in ["url", "summary", "scoring", "bot_matrix", "ai_recommendations"]:
        assert key in audit_after, f"Missing key {key}"
    print("    [PASS] Frontend data contract verified for K.")

    print("=" * 60)
    print("ALL INTEGRATION TESTS PASSED 100%!")
    print("=" * 60)


# =====================================================================
# 5. CLI RUNNER
# =====================================================================

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--test" in args or "test" in args:
        run_integration_test()
        sys.exit(0)

    target = "http://127.0.0.1:5050"
    if "--after" in args or "-a" in args:
        set_mode("after")
    elif "--before" in args or "-b" in args:
        set_mode("before")

    for a in args:
        if not a.startswith("-") and a != "sandbox":
            target = a

    if "5050" in target or "sandbox" in target.lower():
        start_sandbox(port=5050)
        target = "http://127.0.0.1:5050"
        print(f"[*] Sandbox Server Active (Mode: {get_mode().upper()})")

    print(f"[*] Auditing: {target}")
    res = run_audit(target)
    s = res["summary"]
    print("\n" + "=" * 55)
    print(f"AUDIT TARGET: {res['url']}")
    print(f"SCORE: {s['score']}/100 | GRADE: {s['grade']} | STATUS: {s['status']}")
    print("=" * 55)
    print(f"\nDiagnosis: {s['text']}")
    print("\nBot Responses:")
    for b_id, info in res["bot_matrix"].items():
        state = "BLOCKED" if info.get("blocked") else "OK"
        print(f"  - {b_id:15}: Status {info.get('status')} [{state}] ({info.get('latency_ms')}ms)")

    print("\nPenalties:")
    if not res["scoring"]["penalties"]:
        print("  - None (0 deductions)")
    else:
        for p in res["scoring"]["penalties"]:
            print(f"  - ({p['penalty']} pts) {p['factor']}: {p['detail']}")

    print("\nAI Fixes:")
    print(f"  * WAF Rule: {res['ai_recommendations']['cloudflare_waf_rule']}")
