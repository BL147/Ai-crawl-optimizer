"""Heuristics engine for detecting bot-block, WAF, CAPTCHA, and challenge pages."""

from typing import List, Optional
from crawler.models import (
    BlockType,
    DetectionEvidence,
    DetectionInference,
    DetectionResult,
    HttpObservation,
    PageObservation,
    RobotsDirectives,
)


class BotBlockDetector:
    """Evaluates HTTP observations and rendered DOM signals to detect bot-blocking mechanisms,
    strictly separating objective evidence from inferred conclusions."""

    @classmethod
    def detect(
        cls,
        http: HttpObservation,
        page: PageObservation,
        html_content: str = "",
        robots: Optional[RobotsDirectives] = None,
    ) -> DetectionResult:
        status = http.status_code
        headers_lower = {k.lower(): v for k, v in http.headers.items()}
        title_lower = (page.title or "").lower()
        snippet_lower = (page.snippet or "").lower()
        html_lower = html_content.lower()

        # -------------------------------------------------------------
        # 1. Collect Objective Evidence
        # -------------------------------------------------------------
        matched_headers: List[str] = []
        dom_signals: List[str] = []
        matched_keywords: List[str] = []

        # Header inspection
        if "cf-ray" in headers_lower:
            matched_headers.append(f"cf-ray: {headers_lower['cf-ray']}")
        if "server" in headers_lower and "cloudflare" in headers_lower["server"].lower():
            matched_headers.append(f"server: {headers_lower['server']}")
        if "x-datadome" in headers_lower:
            matched_headers.append(f"x-datadome: {headers_lower['x-datadome']}")
        if any("datadome=" in str(v).lower() for v in headers_lower.values()):
            matched_headers.append("cookie: datadome")
        if any(k.startswith("_px") or "perimeterx" in k for k in headers_lower):
            matched_headers.append("perimeterx header")
        if any("x-amzn-waf" in k for k in headers_lower):
            matched_headers.append("x-amzn-waf header")
        if "x-akamai-transformed" in headers_lower:
            matched_headers.append("x-akamai-transformed header")
        if "x-robots-tag" in headers_lower:
            matched_headers.append(f"x-robots-tag: {headers_lower['x-robots-tag']}")

        # DOM signals inspection
        if "cf-turnstile" in html_lower or "class=\"cf-turnstile\"" in html_lower:
            dom_signals.append(".cf-turnstile")
        if "id=\"challenge-stage\"" in html_lower or "id=\"challenge-form\"" in html_lower:
            dom_signals.append("#challenge-form")
        if "challenges.cloudflare.com" in html_lower:
            dom_signals.append("iframe[src*='challenges.cloudflare.com']")
        if "ct.datadome.co" in html_lower or "window.ddjskey" in html_lower:
            dom_signals.append("script[src*='datadome']")
        if "px-captcha" in html_lower or "id=\"px-captcha\"" in html_lower:
            dom_signals.append("#px-captcha")
        if "client.perimeterx.net" in html_lower:
            dom_signals.append("script[src*='perimeterx']")
        if "aws-waf-captcha" in html_lower or "awswafcaptcha" in html_lower:
            dom_signals.append(".aws-waf-captcha")
        if "g-recaptcha" in html_lower or "google.com/recaptcha" in html_lower:
            dom_signals.append("iframe[src*='recaptcha']")
        if "hcaptcha" in html_lower or "h-captcha" in html_lower:
            dom_signals.append("iframe[src*='hcaptcha']")

        # Keyword & text pattern matching
        cf_keywords = [
            "attention required! | cloudflare",
            "just a moment...",
            "checking your browser before accessing",
            "enable javascript and cookies to continue",
            "performance & security by cloudflare",
            "error 1020: access denied",
            "error 1015: you are being rate limited",
        ]
        for kw in cf_keywords:
            if kw in title_lower or kw in snippet_lower:
                matched_keywords.append(kw)

        explicit_bot_phrases = [
            "access to this page has been denied because we believe you are using automation tools",
            "please complete the security check to access",
            "automated access is prohibited",
            "bot traffic detected",
            "crawler access denied",
            "request blocked by aws waf",
        ]
        for phrase in explicit_bot_phrases:
            if phrase in snippet_lower or phrase in html_lower:
                matched_keywords.append(phrase)

        if status == 403 and any(t in title_lower or t in snippet_lower for t in ["forbidden", "access denied", "403"]):
            matched_keywords.append("403 Forbidden")

        robots_rule = robots.matching_rule if robots and not robots.is_allowed else None

        evidence = DetectionEvidence(
            status_code=status,
            matched_headers=matched_headers,
            dom_signals=dom_signals,
            matched_keywords=matched_keywords,
            page_title=page.title,
            snippet_preview=page.snippet[:200] if page.snippet else None,
            robots_rule=robots_rule,
        )

        # -------------------------------------------------------------
        # 2. Derive Inferences from Evidence
        # -------------------------------------------------------------

        # Check 1: Cloudflare Challenge or Block
        has_cf_headers = any("cloudflare" in h or "cf-ray" in h for h in matched_headers)
        has_cf_dom = any("cf-" in s or "cloudflare" in s for s in dom_signals)
        has_cf_kw = any(kw in matched_keywords for kw in cf_keywords)

        if has_cf_dom or (has_cf_headers and has_cf_kw):
            is_challenge = (
                "just a moment..." in matched_keywords
                or ".cf-turnstile" in dom_signals
                or "#challenge-form" in dom_signals
                or "iframe[src*='challenges.cloudflare.com']" in dom_signals
            )
            mech = BlockType.CLOUDFLARE_CHALLENGE if is_challenge else BlockType.CLOUDFLARE_BLOCK
            summary = (
                "Cloudflare interactive challenge (Turnstile / JS challenge) intercepted the crawler request."
                if is_challenge
                else "Cloudflare firewall rule blocked access to this URL."
            )
            return cls._build_result(
                evidence=evidence,
                verdict="CHALLENGED" if is_challenge else "BLOCKED",
                mechanism=mech,
                confidence=0.96,
                summary=summary,
                is_blocked=True,
            )

        # Check 2: DataDome
        if any("datadome" in h for h in matched_headers) or any("datadome" in s for s in dom_signals):
            return cls._build_result(
                evidence=evidence,
                verdict="CHALLENGED",
                mechanism=BlockType.DATADOME,
                confidence=0.95,
                summary="DataDome anti-bot challenge page detected.",
                is_blocked=True,
            )

        # Check 3: PerimeterX / HUMAN Security
        if any("perimeterx" in h for h in matched_headers) or any("perimeterx" in s or "px-captcha" in s for s in dom_signals):
            return cls._build_result(
                evidence=evidence,
                verdict="CHALLENGED",
                mechanism=BlockType.PERIMETERX,
                confidence=0.95,
                summary="PerimeterX / HUMAN Security bot challenge detected.",
                is_blocked=True,
            )

        # Check 4: AWS WAF
        if any("aws-waf" in h for h in matched_headers) or any("aws-waf" in s for s in dom_signals) or "request blocked by aws waf" in matched_keywords:
            return cls._build_result(
                evidence=evidence,
                verdict="CHALLENGED",
                mechanism=BlockType.AWS_WAF,
                confidence=0.92,
                summary="AWS WAF access challenge or block detected.",
                is_blocked=True,
            )

        # Check 5: Akamai Bot Manager
        if any("akamai" in h for h in matched_headers) and status in (403, 503):
            return cls._build_result(
                evidence=evidence,
                verdict="BLOCKED",
                mechanism=BlockType.AKAMAI,
                confidence=0.90,
                summary="Akamai Bot Manager access denial reference format detected.",
                is_blocked=True,
            )

        # Check 6: Standalone CAPTCHAs (reCAPTCHA / hCaptcha)
        if any("recaptcha" in s for s in dom_signals):
            return cls._build_result(
                evidence=evidence,
                verdict="CHALLENGED",
                mechanism=BlockType.RECAPTCHA,
                confidence=0.90,
                summary="Google reCAPTCHA verification iframe detected in DOM.",
                is_blocked=True,
            )
        if any("hcaptcha" in s for s in dom_signals):
            return cls._build_result(
                evidence=evidence,
                verdict="CHALLENGED",
                mechanism=BlockType.HCAPTCHA,
                confidence=0.90,
                summary="hCaptcha challenge widget detected in DOM.",
                is_blocked=True,
            )

        # Check 7: Explicit Bot-Blocking Keywords
        for kw in explicit_bot_phrases:
            if kw in matched_keywords:
                return cls._build_result(
                    evidence=evidence,
                    verdict="BLOCKED",
                    mechanism=BlockType.CUSTOM_BOT_BLOCK,
                    confidence=0.88,
                    summary=f"Explicit bot-blocking notification encountered: '{kw}'.",
                    is_blocked=True,
                )

        # Check 8: HTTP 429 Rate Limited
        if status == 429:
            return cls._build_result(
                evidence=evidence,
                verdict="BLOCKED",
                mechanism=BlockType.HTTP_429_RATE_LIMITED,
                confidence=0.92,
                summary="HTTP 429 Too Many Requests (Rate limit enforced by server).",
                is_blocked=True,
            )

        # Check 9: HTTP 503 Anti-DDoS / Verification
        if status == 503 and any(t in snippet_lower or t in title_lower for t in ["ddos", "security check", "verifying"]):
            return cls._build_result(
                evidence=evidence,
                verdict="CHALLENGED",
                mechanism=BlockType.HTTP_503_SERVICE_UNAVAILABLE,
                confidence=0.85,
                summary="HTTP 503 Service Unavailable with anti-DDoS / bot verification challenge.",
                is_blocked=True,
            )

        # Check 10: Standalone HTTP 403 Forbidden (Inconclusive Attribution)
        if status == 403:
            return cls._build_result(
                evidence=evidence,
                verdict="INCONCLUSIVE",
                mechanism=BlockType.HTTP_FORBIDDEN,
                confidence=0.35,
                summary="Server returned HTTP 403 Forbidden. Access is restricted, but AI-specific blocking attribution is inconclusive without baseline comparison or anti-bot challenge markers.",
                is_blocked=False,
            )

        # Check 11: Robots.txt Crawler Policy Disallow
        if robots is not None and not robots.is_allowed:
            rule_detail = robots.matching_rule or "Disallow"
            return cls._build_result(
                evidence=evidence,
                verdict="RESTRICTED",
                mechanism=BlockType.NONE,
                confidence=1.0,
                summary=f"Technically reachable (HTTP {status or 200}), but crawler policy (robots.txt) restricts crawling/indexing ({rule_detail}).",
                is_blocked=False,
            )

        # Default: Clean accessible page
        return cls._build_result(
            evidence=evidence,
            verdict="ACCESSIBLE",
            mechanism=BlockType.NONE,
            confidence=0.0,
            summary="No access restrictions detected. Page loaded successfully.",
            is_blocked=False,
        )

    @classmethod
    def _build_result(
        cls,
        evidence: DetectionEvidence,
        verdict: str,
        mechanism: BlockType,
        confidence: float,
        summary: str,
        is_blocked: bool,
    ) -> DetectionResult:
        signals: List[str] = []
        if evidence.status_code:
            signals.append(f"HTTP status code: {evidence.status_code}")
        signals.extend(evidence.matched_headers)
        signals.extend(evidence.dom_signals)
        signals.extend([f"Keyword: '{k}'" for k in evidence.matched_keywords])
        if evidence.robots_rule:
            signals.append(f"Robots policy: {evidence.robots_rule}")

        return DetectionResult(
            evidence=evidence,
            inference=DetectionInference(
                verdict=verdict,
                mechanism=mechanism,
                confidence=confidence,
                summary=summary,
            ),
            is_blocked=is_blocked,
            block_type=mechanism,
            confidence=confidence,
            signals=signals,
        )
