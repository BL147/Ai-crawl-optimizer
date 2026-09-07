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
        Event-based scoring: one compound penalty per access event category.
        WAF + HTTP 403 from the same bot are ONE event, not two separate penalties.
        Selective AI discrimination only fires when a REAL browser baseline exists.
        total_deductions = sum(points_deducted) — invariant always holds.
        """
        penalties: List[Dict[str, Any]] = []

        normalized = cls._normalize_input(audit_data)
        bots_data: Dict[str, Any] = normalized["bots"]
        browser_data: Dict[str, Any] = normalized["browser"]
        robots_data: Dict[str, Any] = normalized["robots_txt"]
        selective_ai_block: bool = normalized.get("selective_ai_block_detected", False)
        has_real_baseline: bool = browser_data.get("is_real", False)

        # ====================================================================
        # STEP 1: Classify each bot into ONE mutually exclusive event type
        # (highest severity wins per bot — prevents double-categorisation)
        # ====================================================================
        bot_events: Dict[str, Dict[str, Any]] = {}
        for bot_name, bot_info in bots_data.items():
            raw_status = bot_info.get("status")
            status: Optional[int] = raw_status if isinstance(raw_status, int) else None
            verdict: str = str(bot_info.get("verdict", "")).upper()
            mechanism: str = str(bot_info.get("mechanism", "NONE")).upper()

            is_blocked = bot_info.get("blocked", False) or verdict == "BLOCKED"
            is_challenged = verdict == "CHALLENGED"
            is_inconclusive = (
                verdict == "INCONCLUSIVE" or
                (status == 403 and not is_blocked and not is_challenged)
            )

            # WAF: explicit waf field OR a named mechanism (not generic HTTP codes)
            _mech_is_waf = (
                mechanism not in ("NONE", "", "HTTP_FORBIDDEN",
                                   "HTTP_429_RATE_LIMITED", "INCONCLUSIVE")
                and "HTTP" not in mechanism
            )
            has_waf = bool(bot_info.get("waf")) or _mech_is_waf

            has_captcha = bool(bot_info.get("captcha")) or any(
                ("captcha" in s.lower() or "turnstile" in s.lower() or
                 "challenge" in s.lower())
                for s in bot_info.get("signals", [])
            )
            waf_name = (
                bot_info.get("waf") or
                (mechanism if _mech_is_waf else None)
            )

            # Assign event (highest severity first)
            if status == 429:
                event_type = "RATE_LIMITED"
            elif status is not None and status >= 500:
                event_type = "SERVER_ERROR"
            elif (is_blocked or is_challenged) and has_captcha:
                event_type = "CAPTCHA_BLOCK"
            elif (is_blocked or is_challenged) and has_waf:
                event_type = "WAF_BLOCK"
            elif is_blocked or is_challenged:
                event_type = "BLOCK"
            elif is_inconclusive and status == 403:
                event_type = "INCONCLUSIVE_403"
            else:
                event_type = "ACCESSIBLE"

            bot_events[bot_name] = {
                "event_type": event_type,
                "status": status,
                "verdict": verdict,
                "mechanism": mechanism,
                "has_waf": has_waf,
                "has_captcha": has_captcha,
                "waf_name": waf_name,
            }

        # ====================================================================
        # STEP 2: ACCESS DENIAL PENALTIES — one compound penalty per group.
        # HTTP 403 + WAF from the same event = ONE penalty, not two.
        # ====================================================================
        captcha_bots = [
            b for b, e in bot_events.items() if e["event_type"] == "CAPTCHA_BLOCK"
        ]
        waf_bots = [
            b for b, e in bot_events.items() if e["event_type"] == "WAF_BLOCK"
        ]
        plain_blocked_bots = [
            b for b, e in bot_events.items() if e["event_type"] == "BLOCK"
        ]
        inconclusive_403_bots = [
            b for b, e in bot_events.items() if e["event_type"] == "INCONCLUSIVE_403"
        ]
        rate_limited_bots = [
            b for b, e in bot_events.items() if e["event_type"] == "RATE_LIMITED"
        ]
        server_error_bots = [
            b for b, e in bot_events.items() if e["event_type"] == "SERVER_ERROR"
        ]
        # All confirmed-denied bots (used for discrimination check)
        access_denied_bots = captcha_bots + waf_bots + plain_blocked_bots

        # 2a. CAPTCHA block (absorbs HTTP 403 + CAPTCHA evidence — single penalty)
        if captcha_bots:
            waf_names = sorted({
                bot_events[b]["waf_name"] for b in captcha_bots
                if bot_events[b]["waf_name"]
            })
            waf_detail = f" via {', '.join(waf_names)}" if waf_names else ""
            _pts = cls.PENALTY_CAPTCHA
            penalties.append({
                "category": "Access Denial",
                "factor": f"CAPTCHA / Turnstile Block{waf_detail}",
                "reason": (
                    f"AI crawlers intercepted by interactive CAPTCHA/Turnstile{waf_detail}. "
                    f"HTTP status + challenge evidence confirm one compound event."
                ),
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "CRITICAL",
                "detail": (
                    f"Headless AI agents cannot solve interactive challenges. "
                    f"Affects: {', '.join(captcha_bots)}"
                ),
                "evidence": [
                    f"{b}: HTTP {bot_events[b]['status']} verdict={bot_events[b]['verdict']}"
                    for b in captcha_bots
                ],
            })

        # 2b. WAF block (absorbs HTTP 403 + WAF fingerprint — single penalty)
        if waf_bots:
            waf_names = sorted({
                bot_events[b]["waf_name"] for b in waf_bots
                if bot_events[b]["waf_name"]
            })
            waf_str = f" ({', '.join(waf_names)})" if waf_names else ""
            _pts = cls.PENALTY_WAF_CHALLENGE
            penalties.append({
                "category": "Access Denial",
                "factor": f"WAF / Anti-Bot Shield Block{waf_str}",
                "reason": (
                    f"WAF managed rules deny AI crawler access{waf_str}. "
                    f"HTTP status + WAF fingerprint confirm one compound event."
                ),
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "CRITICAL",
                "detail": (
                    f"WAF challenge/block intercepts AI crawlers without bypass. "
                    f"Affects: {', '.join(waf_bots)}"
                ),
                "evidence": [
                    f"{b}: HTTP {bot_events[b]['status']} mechanism={bot_events[b]['mechanism']}"
                    for b in waf_bots
                ],
            })

        # 2c. Plain block (no WAF/CAPTCHA evidence)
        if plain_blocked_bots:
            _pts = cls.PENALTY_HTTP_403
            penalties.append({
                "category": "Access Denial",
                "factor": "HTTP Access Denied (No Challenge Signature)",
                "reason": (
                    "AI crawlers denied access. HTTP 403 or blocked verdict "
                    "without specific WAF/CAPTCHA evidence."
                ),
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "CRITICAL",
                "detail": (
                    f"AI crawlers received explicit access denial. "
                    f"Affects: {', '.join(plain_blocked_bots)}"
                ),
                "evidence": [
                    f"{b}: HTTP {bot_events[b]['status']} verdict={bot_events[b]['verdict']}"
                    for b in plain_blocked_bots
                ],
            })

        # 2d. Inconclusive 403
        if inconclusive_403_bots:
            _pts = 15
            penalties.append({
                "category": "Access Concern",
                "factor": "HTTP 403 \u2014 Inconclusive (No Challenge Evidence)",
                "reason": (
                    "HTTP 403 returned without definitive WAF/bot-shield signatures. "
                    "Preserved as INCONCLUSIVE per zero-hallucination policy."
                ),
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "HIGH",
                "detail": (
                    f"Access uncertain \u2014 system will NOT fabricate a block claim without concrete evidence. "
                    f"Affects: {', '.join(inconclusive_403_bots)}"
                ),
                "evidence": [
                    f"{b}: HTTP 403 verdict=INCONCLUSIVE" for b in inconclusive_403_bots
                ],
            })

        # 2e. Rate limiting
        if rate_limited_bots:
            _pts = cls.PENALTY_HTTP_429
            penalties.append({
                "category": "Rate Limiting",
                "factor": "HTTP 429 Too Many Requests",
                "reason": "AI crawl budget throttled by server-side rate limiting.",
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "HIGH",
                "detail": (
                    f"Rate limiting reduces AI crawl frequency. "
                    f"Affects: {', '.join(rate_limited_bots)}"
                ),
                "evidence": [f"{b}: HTTP 429" for b in rate_limited_bots],
            })

        # 2f. Server errors
        if server_error_bots:
            _pts = cls.PENALTY_HTTP_5XX
            penalties.append({
                "category": "Server Errors",
                "factor": "HTTP 5xx Server Error",
                "reason": "Server failures encountered during crawl attempt.",
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "HIGH",
                "detail": (
                    f"Server errors prevent AI indexing. "
                    f"Affects: {', '.join(server_error_bots)}"
                ),
                "evidence": [
                    f"{b}: HTTP {bot_events[b]['status']}" for b in server_error_bots
                ],
            })

        # ====================================================================
        # STEP 3: SELECTIVE AI DISCRIMINATION
        # ONLY fires when a REAL browser baseline was collected.
        # ====================================================================
        if has_real_baseline:
            browser_ok = (
                browser_data.get("status") == 200 and
                not browser_data.get("blocked", False)
            )
            if browser_ok and access_denied_bots:
                _pts = cls.PENALTY_AI_DISCREPANCY
                penalties.append({
                    "category": "Selective AI Discrimination",
                    "factor": "Selective AI Crawler Blocking",
                    "reason": (
                        "Site serves human browsers (HTTP 200) but denies AI crawlers. "
                        "Evidence of deliberate AI discrimination."
                    ),
                    "penalty": -_pts,
                    "points_deducted": _pts,
                    "severity": "CRITICAL",
                    "detail": (
                        f"Browser baseline: HTTP {browser_data.get('status')} (accessible). "
                        f"AI crawlers denied: {', '.join(access_denied_bots[:3])}"
                        + (f" (+{len(access_denied_bots)-3} more)" if len(access_denied_bots) > 3 else "")
                    ),
                    "evidence": [
                        f"Browser: HTTP {browser_data.get('status')}",
                        f"Blocked AI: {', '.join(access_denied_bots)}",
                    ],
                })
        elif selective_ai_block:
            # Explicitly flagged upstream (e.g. crawl_with_baseline_sync)
            _pts = cls.PENALTY_AI_DISCREPANCY
            penalties.append({
                "category": "Selective AI Discrimination",
                "factor": "Selective AI Blocking (Reported by Crawler)",
                "reason": (
                    "Crawler reported selective AI blocking based on "
                    "differential response evidence."
                ),
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "CRITICAL",
                "detail": (
                    "Site differentiates between human browsers and AI crawler "
                    "user-agents."
                ),
                "evidence": ["selective_ai_block_detected=True reported by crawler"],
            })

        # ====================================================================
        # STEP 4: ROBOTS.TXT
        # ====================================================================
        robots_ai_disallowed = (
            robots_data.get("ai_disallowed", False) or
            (robots_data.get("is_allowed") is False)
        )
        if robots_ai_disallowed:
            matching_rule = (
                robots_data.get("matching_rule") or
                robots_data.get("details") or
                "Disallow: /"
            )
            _pts = cls.PENALTY_ROBOTS_AI_BLOCKED
            penalties.append({
                "category": "Robots.txt Policy",
                "factor": "Robots.txt AI Crawl Disallow",
                "reason": "robots.txt explicitly disallows AI crawler indexing.",
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "MEDIUM",
                "detail": (
                    f"Robots.txt instructs AI search agents not to index. "
                    f"Rule: {matching_rule}"
                ),
                "evidence": [f"Matching directive: {matching_rule}"],
            })

        # ====================================================================
        # STEP 5: LATENCY
        # ====================================================================
        high_latency_bots = [
            b for b, data in bots_data.items()
            if (data.get("latency_ms") or 0) > 3000
        ]
        browser_slow = (browser_data.get("latency_ms") or 0) > 3000
        if high_latency_bots or browser_slow:
            _pts = cls.PENALTY_HIGH_LATENCY
            penalties.append({
                "category": "Performance",
                "factor": "High Response Latency (> 3.0s)",
                "reason": "High response latency degrades AI crawl budget efficiency.",
                "penalty": -_pts,
                "points_deducted": _pts,
                "severity": "LOW",
                "detail": (
                    f"Slow responses reduce AI crawl frequency. "
                    f"Affected: {', '.join(high_latency_bots) if high_latency_bots else 'baseline server'}"
                ),
                "evidence": (
                    [f"{b}: {bots_data[b].get('latency_ms')}ms" for b in high_latency_bots]
                    or [f"Server: {browser_data.get('latency_ms')}ms"]
                ),
            })

        # ====================================================================
        # FINALIZE — total_deductions = sum(points_deducted) always
        # ====================================================================
        total_deductions = sum(p["points_deducted"] for p in penalties)
        final_score = max(0, min(100, cls.BASE_SCORE - total_deductions))

        grade, status_str, color = cls._get_grade(final_score)
        risk_level = cls._get_risk_level(final_score)

        reasons = [
            f"[{p['severity']}] {p['factor']}: {p['detail']} ({p['penalty']} pts)"
            for p in penalties
        ]
        if not reasons:
            reasons = [
                "No critical access barriers detected. "
                "Website is accessible to AI search crawlers."
            ]

        primary_bot = next(iter(bots_data.values()), {})
        metrics = {
            "http_status": primary_bot.get("status"),
            "response_time_ms": primary_bot.get("latency_ms", 0),
            "verdict": primary_bot.get("verdict", "ACCESSIBLE"),
            "mechanism": primary_bot.get("mechanism", "NONE"),
            "confidence": primary_bot.get("confidence", 0.0),
            "robots_allowed": robots_data.get("is_allowed", not robots_ai_disallowed),
            "selective_block_detected": selective_ai_block or bool(
                access_denied_bots and has_real_baseline
            ),
            "page_text_length": primary_bot.get("text_length", 0),
        }

        return {
            "score": final_score,
            "grade": grade,
            "risk_level": risk_level,
            "status": status_str,
            "color": color,
            "reasons": reasons,
            "metrics": metrics,
            "base_score": cls.BASE_SCORE,
            "total_deductions": total_deductions,
            "penalties": penalties,
            "summary": cls._build_summary(final_score, penalties),
        }

    @staticmethod
    def _get_risk_level(score: int) -> str:
        """Determines risk level from final score."""
        if score >= 90:
            return "LOW"
        elif score >= 75:
            return "MEDIUM"
        elif score >= 50:
            return "HIGH"
        else:
            return "CRITICAL"

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
                "browser": {"status": None, "latency_ms": 0, "is_real": False},
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

        # Case 2: Direct single Anshul CrawlResult dict (no real baseline available)
        if "detection" in audit_data and "http" in audit_data:
            bot_entry = cls._extract_single_bot(audit_data)
            persona_name = audit_data.get("persona", "gptbot")
            return {
                "bots": {persona_name: bot_entry},
                # No real browser baseline — do NOT fabricate 200 OK
                "browser": {"status": None, "latency_ms": 0, "is_real": False},
                "robots_txt": audit_data.get("robots_txt", {}),
                "waf_detected": bot_entry.get("waf"),
                "captcha_detected": bot_entry.get("captcha", False),
                "selective_ai_block_detected": False,
            }

        # Case 3: List of results (e.g. crawl_all_personas) wrapped in a dict
        if "results" in audit_data and isinstance(audit_data["results"], list):
            bots = {}
            # Start with no real baseline — only upgrade if standard_browser found
            browser: Dict[str, Any] = {"status": None, "latency_ms": 0, "is_real": False}
            robots_txt: Dict[str, Any] = {}
            for item in audit_data["results"]:
                p = item.get("persona", "unknown")
                entry = cls._extract_single_bot(item)
                if p == "standard_browser":
                    browser = dict(entry)
                    browser["is_real"] = True
                else:
                    bots[p] = entry
                if item.get("robots_txt") and not robots_txt:
                    robots_txt = item.get("robots_txt")
            global_waf = next((b.get("waf") for b in bots.values() if b.get("waf")), None)
            global_cap = any(b.get("captcha") for b in bots.values())
            has_real = browser.get("is_real", False)
            selective = (
                has_real and
                browser.get("status") == 200 and
                any(b.get("blocked") for b in bots.values())
            )
            return {
                "bots": bots,
                "browser": browser,
                "robots_txt": robots_txt,
                "waf_detected": global_waf,
                "captcha_detected": global_cap,
                "selective_ai_block_detected": selective,
            }

        # Case 4: Standard legacy / aggregate dict format
        browser = audit_data.get("browser", {"status": None, "latency_ms": 0, "is_real": False})
        # If is_real not specified, infer from whether status is an actual int
        if "is_real" not in browser:
            browser = dict(browser)
            browser["is_real"] = isinstance(browser.get("status"), int) and browser.get("status") is not None
        return {
            "bots": audit_data.get("bots", {}),
            "browser": browser,
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

        text_length = res.get("page", {}).get("text_length", 0) if isinstance(res.get("page"), dict) else 0

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
            "text_length": text_length,
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
