"""
validation/engine.py - Fix Validation Engine for Phase 2
Author: Shlok (System Integrator)

Core Principles:
1. Reuses the existing Phase 1 crawler (CrawlerEngine / run_audit). Zero duplicate crawlers.
2. Issue-specific validation: An increase in overall score alone NEVER declares a fix successful.
   The targeted barrier must be confirmed resolved.
3. Supports all 4 validation states:
   - VERIFIED
   - PARTIALLY_VERIFIED
   - FAILED
   - INCONCLUSIVE
4. Supports all 8 MVP validation scenarios.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from validation.models import (
    FixStatus,
    IssueCategory,
    TargetIssue,
    ValidationResult,
    ValidationStatus,
)


class FixValidationEngine:
    """
    Validates whether a specific crawlability issue was resolved by comparing
    before-fix and after-fix audits produced by the Phase 1 crawler.
    """

    @classmethod
    def validate_comparison(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target_issue: Optional[Union[TargetIssue, IssueCategory, str, Dict[str, Any]]] = None,
        fix_status: str = FixStatus.APPLIED.value,
        timestamp: Optional[str] = None,
    ) -> ValidationResult:
        """
        Pure comparison validation between two audit snapshots.
        Issue-specific: never approves based on score delta alone.
        """
        audit_before = cls._as_dict(audit_before)
        audit_after = cls._as_dict(audit_after)
        now_ts = timestamp or datetime.now(timezone.utc).isoformat()

        # 1. Extract Scores
        before_score = cls._extract_score(audit_before)
        after_score = cls._extract_score(audit_after)
        score_delta = after_score - before_score

        # 2. Check for Test Environment / Crawl Failure (MVP Case 6)
        is_unavail, unavail_reason = cls._check_environment_unavailable(audit_after)
        if is_unavail:
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=cls._summarize_issue(audit_before, target_issue),
                issue_after={"status": "UNAVAILABLE", "detail": unavail_reason},
                fix_status=fix_status,
                validation_status=ValidationStatus.INCONCLUSIVE,
                evidence=[
                    f"Test environment unavailable or crawl failure encountered: {unavail_reason}",
                    "Cannot validate fix because post-fix observation could not be completed.",
                ],
                timestamp=now_ts,
                details={"error": unavail_reason},
            )

        # 3. Check for Inconclusive Post-Fix Verdict (MVP Case 7)
        is_inconcl, inconcl_detail = cls._check_inconclusive_verdict(audit_after)
        if is_inconcl:
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=cls._summarize_issue(audit_before, target_issue),
                issue_after={"verdict": "INCONCLUSIVE", "detail": inconcl_detail},
                fix_status=fix_status,
                validation_status=ValidationStatus.INCONCLUSIVE,
                evidence=[
                    f"Post-fix crawl result is inconclusive: {inconcl_detail}",
                    "Per zero-hallucination policy, cannot verify or fail without definitive evidence.",
                ],
                timestamp=now_ts,
                details={"verdict": "INCONCLUSIVE", "detail": inconcl_detail},
            )

        # 4. Resolve Target Issue Specification
        resolved_target = cls._resolve_target_issue(target_issue, audit_before)

        # 5. Route to Issue-Specific Comparators
        category = resolved_target.category

        # Phase 3 Security Restriction Comparators (ACCESSIBLE -> INTENTIONALLY RESTRICTED)
        if category == IssueCategory.AI_ROBOTS_RESTRICTION:
            result = cls._validate_security_robots_restriction(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category == IssueCategory.AI_RATE_LIMIT:
            result = cls._validate_security_rate_limit(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category == IssueCategory.AI_WAF_CHALLENGE:
            result = cls._validate_security_waf_challenge(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category == IssueCategory.AI_CAPTCHA:
            result = cls._validate_security_captcha(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category == IssueCategory.AI_AUTHENTICATION:
            result = cls._validate_security_authentication(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )

        if category in (
            IssueCategory.AI_ROBOTS_RESTRICTION,
            IssueCategory.AI_RATE_LIMIT,
            IssueCategory.AI_WAF_CHALLENGE,
            IssueCategory.AI_CAPTCHA,
            IssueCategory.AI_AUTHENTICATION,
        ):
            result = cls._apply_target_persona_guard(result, audit_after, resolved_target)
            return cls._apply_collateral_guard(result, audit_after, resolved_target)

        # Phase 2 Optimization Comparators (RESTRICTED -> ACCESSIBLE)
        elif category == IssueCategory.ROBOTS_TXT:
            return cls._validate_robots_fix(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category in (IssueCategory.WAF_CHALLENGE, IssueCategory.CAPTCHA):
            return cls._validate_waf_fix(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category == IssueCategory.LATENCY:
            return cls._validate_latency_fix(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category in (IssueCategory.RATE_LIMIT, IssueCategory.HTTP_STATUS, IssueCategory.SERVER_ERROR):
            return cls._validate_http_status_fix(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category == IssueCategory.AI_RESTRICTION:
            desc = str(resolved_target.description or "").upper()
            if "ROBOT" in desc:
                return cls._validate_robots_fix(
                    audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
                )
            elif "WAF" in desc or "CHALLENGE" in desc or "CAPTCHA" in desc:
                return cls._validate_waf_fix(
                    audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
                )
            elif "RATE" in desc or "429" in desc:
                return cls._validate_http_status_fix(
                    audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
                )
            else:
                return cls._validate_general_fix(
                    audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
                )
        else:
            # General / Composite validation
            return cls._validate_general_fix(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )

    @classmethod
    def validate_fix(
        cls,
        target_url: str,
        target_issue: Optional[Union[TargetIssue, IssueCategory, str, Dict[str, Any]]] = None,
        fix_action: Optional[Callable[[], Any]] = None,
        persona: str = "gptbot",
        audit_before: Optional[Any] = None,
        audit_after: Optional[Any] = None,
        fix_status: Optional[str] = None,
        **crawl_options: Any,
    ) -> ValidationResult:
        """
        Orchestrates full Phase 2 Flow:
        1. Capture baseline audit (or consume provided audit_before).
        2. Execute fix_action (backend service call or toggle) if provided.
        3. Audit again with the SAME Phase 1 crawler (or consume provided audit_after).
        4. Validate issue-specifically.
        """
        # Step 1: Capture Baseline Audit if not provided
        if audit_before is None:
            try:
                # Import only when a live Phase 1 crawl is required.  Snapshot
                # comparison remains usable in service/test environments that do
                # not install Playwright.
                from orchestrator import run_audit
                audit_before = run_audit(target_url, persona=persona, **crawl_options)
            except Exception as exc:
                now_ts = datetime.now(timezone.utc).isoformat()
                return ValidationResult(
                    before_score=0,
                    after_score=0,
                    score_delta=0,
                    issue_before="Unable to reach target for baseline",
                    issue_after="N/A",
                    fix_status=fix_status or FixStatus.ERROR.value,
                    validation_status=ValidationStatus.INCONCLUSIVE,
                    evidence=[f"Baseline crawl failed: {str(exc)}"],
                    timestamp=now_ts,
                    target_url=target_url,
                    persona=persona,
                )

        # Step 2: Apply Fix (or accept external fix_status)
        # This engine never treats a public target as a writable sandbox.  Callers
        # may still pass before/after observations from an externally managed
        # deployment, but an in-process Phase 3 control action is local-only.
        resolved_target = cls._resolve_target_issue(target_issue, cls._as_dict(audit_before))
        if fix_action and resolved_target.is_security and not cls._is_controlled_target(target_url):
            before_score = cls._extract_score(cls._as_dict(audit_before))
            return ValidationResult(
                before_score=before_score,
                after_score=before_score,
                score_delta=0,
                issue_before=cls._summarize_issue(cls._as_dict(audit_before), target_issue),
                issue_after="N/A",
                fix_status=FixStatus.NOT_APPLICABLE.value,
                validation_status=ValidationStatus.INCONCLUSIVE,
                evidence=[
                    "Phase 3 controls are only applied automatically to an explicit local/controlled sandbox target.",
                    "No control action was run against the external/public target; provide externally collected after-audit evidence to validate it.",
                ],
                timestamp=datetime.now(timezone.utc).isoformat(),
                target_url=target_url,
                persona=persona,
            )
        if fix_status is None:
            fix_status = FixStatus.APPLIED.value
            if fix_action:
                try:
                    fix_action()
                except Exception as exc:
                    fix_status = FixStatus.ERROR.value
        elif fix_action:
            try:
                fix_action()
            except Exception as exc:
                fix_status = FixStatus.ERROR.value

        # Step 3: Run Phase 1 Crawler Again if audit_after not provided
        if audit_after is None:
            try:
                from orchestrator import run_audit
                audit_after = run_audit(target_url, persona=persona, **crawl_options)
            except Exception as exc:
                now_ts = datetime.now(timezone.utc).isoformat()
                before_score = cls._extract_score(audit_before)
                return ValidationResult(
                    before_score=before_score,
                    after_score=0,
                    score_delta=-before_score,
                    issue_before=cls._summarize_issue(audit_before, target_issue),
                    issue_after={"status": "UNAVAILABLE", "detail": str(exc)},
                    fix_status=fix_status,
                    validation_status=ValidationStatus.INCONCLUSIVE,
                    evidence=[
                        f"Fix applied (status={fix_status}), but post-fix crawl failed: {str(exc)}",
                        "Cannot validate fix because post-fix observation could not be completed.",
                    ],
                    timestamp=now_ts,
                    target_url=target_url,
                    persona=persona,
                )

        # Step 4: Compare & Validate
        res = cls.validate_comparison(
            audit_before=audit_before,
            audit_after=audit_after,
            target_issue=target_issue,
            fix_status=fix_status,
        )
        res.target_url = target_url
        res.persona = persona
        return res

    # =========================================================================
    # Issue-Specific Comparators
    # =========================================================================

    @classmethod
    def _validate_robots_fix(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """Validates robots.txt compliance changes."""
        before_allowed, before_rule = cls._extract_robots_status(audit_before, target.persona)
        after_allowed, after_rule = cls._extract_robots_status(audit_after, target.persona)

        issue_before = {
            "category": "ROBOTS_TXT",
            "is_allowed": before_allowed,
            "matching_rule": before_rule or "None",
            "status": "ALLOWED" if before_allowed else "RESTRICTED",
        }
        issue_after = {
            "category": "ROBOTS_TXT",
            "is_allowed": after_allowed,
            "matching_rule": after_rule or "None",
            "status": "ALLOWED" if after_allowed else "RESTRICTED",
        }

        evidence: List[str] = []

        # Check if this validation is for an AI restriction
        is_restriction = (
            target.expected_resolved_state in ("RESTRICTED", "DISALLOWED")
            or target.category == IssueCategory.AI_RESTRICTION
            or "RESTRICT" in str(target.description or "").upper()
        )

        if is_restriction:
            if not after_allowed:
                evidence.append(f"Before: AI crawler was permitted (rule: {before_rule or 'None'}).")
                evidence.append(f"After: AI crawler is successfully RESTRICTED by robots.txt (rule: {after_rule or 'Disallow: /'}).")
                evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
                evidence.append("Robots.txt AI restriction confirmed active per RFC 9309 directive evaluation.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                )
            else:
                evidence.append(f"Before: AI crawler was permitted (rule: {before_rule or 'None'}).")
                evidence.append(f"After: AI crawler remains ALLOWED by robots.txt (rule: {after_rule or 'None'}).")
                evidence.append("Expected robots.txt restriction was NOT applied.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Case 5: Already fixed / not an issue before validation
        if before_allowed:
            evidence.append(
                f"Target issue (robots.txt disallow) was ALREADY not present in baseline. "
                f"Crawler was already permitted (rule: {before_rule or 'None'})."
            )
            evidence.append(f"Post-fix observation: crawler remains allowed (rule: {after_rule or 'None'}).")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
                details={"already_fixed_in_baseline": True},
            )

        # Before was RESTRICTED. Check after:
        if after_allowed:
            # Case 1: Successful robots fix
            evidence.append(f"Before: AI crawler was RESTRICTED by robots.txt (rule: {before_rule}).")
            evidence.append(f"After: AI crawler is explicitly ALLOWED (rule: {after_rule or 'Allow: /'}).")
            evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
            evidence.append("Robots.txt policy confirmed resolved per RFC 9309 directive evaluation.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )
        else:
            # Case 2 & 4: Failed robots fix
            evidence.append(f"Before: AI crawler was RESTRICTED by robots.txt (rule: {before_rule}).")
            evidence.append(f"After: AI crawler remains RESTRICTED by robots.txt (rule: {after_rule}).")

            if score_delta > 0:
                # Case 4: Score improves but original issue remains
                evidence.append(
                    f"Overall score increased by +{score_delta} points ({before_score} -> {after_score}), "
                    f"BUT original issue (robots.txt restriction) remains ACTIVE. "
                    f"Per issue-specific validation principle, score gains do not override unresolved barriers."
                )
            else:
                evidence.append("Original issue remains completely unresolved.")

            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.FAILED,
                evidence=evidence,
                timestamp=timestamp,
            )

    @classmethod
    def _validate_waf_fix(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """Validates WAF, CAPTCHA, or anti-bot challenge removals."""
        b_verdict, b_mech, b_status, b_blocked = cls._extract_detection_status(audit_before)
        a_verdict, a_mech, a_status, a_blocked = cls._extract_detection_status(audit_after)

        issue_before = {
            "verdict": b_verdict,
            "mechanism": b_mech,
            "http_status": b_status,
            "blocked": b_blocked,
        }
        issue_after = {
            "verdict": a_verdict,
            "mechanism": a_mech,
            "http_status": a_status,
            "blocked": a_blocked,
        }

        evidence: List[str] = []

        # Check if this validation is for an AI restriction
        is_restriction = (
            target.expected_resolved_state in ("CHALLENGED", "BLOCKED", "RESTRICTED")
            or target.category == IssueCategory.AI_RESTRICTION
            or "RESTRICT" in str(target.description or "").upper()
        )

        if is_restriction:
            if a_blocked or a_verdict in ("CHALLENGED", "BLOCKED") or a_status in (403, 429):
                evidence.append(f"Before: AI crawler was accessible ({b_verdict}, HTTP {b_status}).")
                evidence.append(f"After: AI crawler is successfully challenged/blocked ({a_verdict} via {a_mech}, HTTP {a_status}).")
                evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
                evidence.append("WAF/anti-bot challenge restriction confirmed active.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                )
            else:
                evidence.append(f"Before: AI crawler was accessible ({b_verdict}, HTTP {b_status}).")
                evidence.append(f"After: AI crawler remains accessible (HTTP {a_status}, {a_verdict}).")
                evidence.append("Expected WAF/anti-bot restriction was NOT applied.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Case 5: Already accessible before
        if not b_blocked and b_verdict == "ACCESSIBLE" and b_status == 200:
            evidence.append("Target WAF/bot block issue was ALREADY not present in baseline audit (HTTP 200 ACCESSIBLE).")
            evidence.append(f"Post-fix observation: remains ACCESSIBLE (HTTP {a_status}).")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
                details={"already_fixed_in_baseline": True},
            )

        # Before was challenged/blocked
        if not a_blocked and a_verdict == "ACCESSIBLE" and a_status == 200:
            # Successfully cleared
            evidence.append(f"Before: AI crawler was blocked/challenged ({b_verdict} via {b_mech}, HTTP {b_status}).")
            evidence.append(f"After: AI crawler successfully reached target (HTTP 200, {a_verdict}).")
            evidence.append(f"Score improved by {score_delta:+d} points ({before_score} -> {after_score}).")
            evidence.append("WAF/anti-bot challenge confirmed removed.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )
        elif a_blocked and a_verdict in ("CHALLENGED", "BLOCKED"):
            # Still blocked
            evidence.append(f"Before: AI crawler blocked/challenged ({b_verdict} via {b_mech}).")
            evidence.append(f"After: AI crawler remains blocked/challenged ({a_verdict} via {a_mech}, HTTP {a_status}).")
            if score_delta > 0:
                evidence.append(
                    f"Overall score increased by +{score_delta} points ({before_score} -> {after_score}), "
                    f"BUT the target WAF/anti-bot block was NOT resolved."
                )
            else:
                evidence.append("Target WAF barrier persists.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.FAILED,
                evidence=evidence,
                timestamp=timestamp,
            )
        else:
            # Partially verified or changed state
            evidence.append(f"Before: {b_verdict} via {b_mech}.")
            evidence.append(f"After: {a_verdict} via {a_mech} (HTTP {a_status}).")
            status = ValidationStatus.PARTIALLY_VERIFIED if not a_blocked else ValidationStatus.FAILED
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=status,
                evidence=evidence,
                timestamp=timestamp,
            )

    @classmethod
    def _validate_latency_fix(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """Validates latency / performance budget improvements (MVP Case 8)."""
        threshold = target.threshold or 3000.0
        before_lat = cls._extract_latency(audit_before)
        after_lat = cls._extract_latency(audit_after)

        issue_before = {"category": "LATENCY", "latency_ms": before_lat, "threshold_ms": threshold}
        issue_after = {"category": "LATENCY", "latency_ms": after_lat, "threshold_ms": threshold}

        evidence: List[str] = []

        if before_lat <= threshold:
            evidence.append(f"Baseline latency ({before_lat:.0f}ms) was ALREADY within budget (<= {threshold:.0f}ms).")
            evidence.append(f"Post-fix latency: {after_lat:.0f}ms.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
                details={"already_fixed_in_baseline": True},
            )

        if after_lat <= threshold:
            # Case 8: Successful latency fix
            evidence.append(f"Before: high latency of {before_lat:.0f}ms exceeded budget threshold ({threshold:.0f}ms).")
            evidence.append(f"After: latency successfully reduced to {after_lat:.0f}ms (under {threshold:.0f}ms threshold).")
            evidence.append(f"Score improved by {score_delta:+d} points ({before_score} -> {after_score}).")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )
        else:
            evidence.append(f"Before: latency was {before_lat:.0f}ms (threshold: {threshold:.0f}ms).")
            evidence.append(f"After: latency remains high at {after_lat:.0f}ms (threshold: {threshold:.0f}ms).")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.FAILED,
                evidence=evidence,
                timestamp=timestamp,
            )

    @classmethod
    def _validate_http_status_fix(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """Validates HTTP status issues (429 rate limit, 5xx server error, plain 403)."""
        _, _, b_status, _ = cls._extract_detection_status(audit_before)
        _, _, a_status, _ = cls._extract_detection_status(audit_after)

        issue_before = {"http_status": b_status}
        issue_after = {"http_status": a_status}

        evidence: List[str] = []

        # Check if this validation is for an AI restriction (e.g. rate limit / 429)
        is_restriction = (
            target.expected_resolved_state in ("BLOCKED", "429", "RESTRICTED")
            or target.category == IssueCategory.AI_RESTRICTION
            or "RESTRICT" in str(target.description or "").upper()
            or str(target.description or "").upper().startswith("AI_RATE_LIMIT")
        )

        if is_restriction:
            if a_status == 429 or a_status in (429, 403):
                evidence.append(f"Before: server returned HTTP {b_status}.")
                evidence.append(f"After: server successfully returned HTTP {a_status} (rate limiting active).")
                evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
                evidence.append("AI rate limit restriction confirmed active.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                )
            else:
                evidence.append(f"Before: server returned HTTP {b_status}.")
                evidence.append(f"After: server returned HTTP {a_status} (expected HTTP 429).")
                evidence.append("Expected rate limit restriction was NOT applied.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        if b_status == 200:
            evidence.append(f"Baseline HTTP status was ALREADY 200 OK. No status failure detected prior to fix.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
                details={"already_fixed_in_baseline": True},
            )

        if a_status == 200:
            evidence.append(f"Before: server returned HTTP {b_status}.")
            evidence.append(f"After: server successfully returned HTTP 200 OK.")
            evidence.append(f"Score improved by {score_delta:+d} points ({before_score} -> {after_score}).")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )
        else:
            evidence.append(f"Before: server returned HTTP {b_status}.")
            evidence.append(f"After: server continues returning HTTP {a_status} (expected HTTP 200).")
            if score_delta > 0:
                evidence.append(f"Score increased by +{score_delta} points, but HTTP failure persists.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.FAILED,
                evidence=evidence,
                timestamp=timestamp,
            )

    @classmethod
    def _validate_general_fix(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """Composite comparator when no explicit target was declared or multiple factors exist."""
        # Check if result is completely unchanged (MVP Case 3)
        b_verdict, b_mech, b_status, b_blocked = cls._extract_detection_status(audit_before)
        a_verdict, a_mech, a_status, a_blocked = cls._extract_detection_status(audit_after)
        b_robots, _ = cls._extract_robots_status(audit_before)
        a_robots, _ = cls._extract_robots_status(audit_after)

        unchanged = (
            b_verdict == a_verdict
            and b_mech == a_mech
            and b_status == a_status
            and b_blocked == a_blocked
            and b_robots == a_robots
            and before_score == after_score
        )

        issue_before = cls._summarize_issue(audit_before, target)
        issue_after = cls._summarize_issue(audit_after, target)

        if unchanged:
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.FAILED,
                evidence=[
                    "Result is completely UNCHANGED between baseline and post-fix audits.",
                    f"HTTP Status: {a_status}, Verdict: {a_verdict}, Blocked: {a_blocked}.",
                    "The fix produced no observable change in crawler accessibility.",
                ],
                timestamp=timestamp,
            )

        # Evaluate if all identified barriers in before are resolved in after
        before_penalties = cls._extract_penalties(audit_before)
        after_penalties = cls._extract_penalties(audit_after)

        resolved_count = 0
        remaining_count = 0
        evidence: List[str] = []

        for p in before_penalties:
            factor = p.get("factor", "")
            # Check if this factor is gone from after_penalties
            still_present = any(ap.get("factor") == factor for ap in after_penalties)
            if not still_present:
                resolved_count += 1
                evidence.append(f"Resolved penalty: '{factor}' (-{abs(p.get('penalty', 0))} pts).")
            else:
                remaining_count += 1
                evidence.append(f"Unresolved penalty: '{factor}' persists in post-fix audit.")

        if resolved_count > 0 and remaining_count == 0:
            val_status = ValidationStatus.VERIFIED
            evidence.append("All previously identified barriers have been confirmed resolved.")
        elif resolved_count > 0 and remaining_count > 0:
            val_status = ValidationStatus.PARTIALLY_VERIFIED
            evidence.append(f"Partially verified: {resolved_count} barrier(s) resolved, {remaining_count} barrier(s) persist.")
        else:
            val_status = ValidationStatus.FAILED
            evidence.append("Target barriers were not resolved.")

        return ValidationResult(
            before_score=before_score,
            after_score=after_score,
            score_delta=score_delta,
            issue_before=issue_before,
            issue_after=issue_after,
            fix_status=fix_status,
            validation_status=val_status,
            evidence=evidence,
            timestamp=timestamp,
        )

    # =========================================================================
    # Phase 3 Security Restriction Comparators (ACCESSIBLE -> RESTRICTED)
    # =========================================================================

    @classmethod
    def _validate_security_robots_restriction(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """
        Validates Phase 3 Security Restriction: AI_ROBOTS_RESTRICTION.
        Objective: ACCESSIBLE -> INTENTIONALLY RESTRICTED via robots.txt.
        """
        before_allowed, before_rule = cls._extract_robots_status(audit_before, target.persona)
        after_allowed, after_rule = cls._extract_robots_status(audit_after, target.persona)

        issue_before = {
            "category": "AI_ROBOTS_RESTRICTION",
            "is_allowed": before_allowed,
            "matching_rule": before_rule or "None",
            "status": "ALLOWED" if before_allowed else "RESTRICTED",
        }
        issue_after = {
            "category": "AI_ROBOTS_RESTRICTION",
            "is_allowed": after_allowed,
            "matching_rule": after_rule or "None",
            "status": "ALLOWED" if after_allowed else "RESTRICTED",
        }

        evidence: List[str] = []

        # Check unchanged state
        if before_allowed == after_allowed and before_rule == after_rule and before_score == after_score:
            if before_allowed:
                evidence.append("Result is completely UNCHANGED between baseline and post-enforcement audits.")
                evidence.append(f"AI crawler REMAINS PERMITTED by robots.txt (rule: {after_rule or 'None'}).")
                evidence.append("Expected robots.txt security restriction was not applied.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Baseline was already restricted
        if not before_allowed:
            if not after_allowed:
                evidence.append(
                    f"Target security restriction (robots.txt disallow) was ALREADY active in baseline audit. "
                    f"Crawler was already restricted (rule: {before_rule or 'None'})."
                )
                evidence.append(f"Post-enforcement observation: crawler remains restricted (rule: {after_rule or 'None'}).")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                    details={"already_restricted_in_baseline": True},
                )
            else:
                evidence.append(f"Before: AI crawler was restricted (rule: {before_rule}).")
                evidence.append(f"After: AI crawler became PERMITTED (rule: {after_rule or 'None'}).")
                evidence.append("Security restriction failed: target became more permissive instead of restricted.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Before was ALLOWED:
        if not after_allowed:
            evidence.append(f"Before: AI crawler was explicitly PERMITTED by robots.txt (rule: {before_rule or 'Allow: /'}).")
            evidence.append(f"After: AI crawler is now INTENTIONALLY RESTRICTED by robots.txt (rule: {after_rule or 'Disallow: /'}).")
            evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
            evidence.append("Robots.txt security restriction confirmed enforced per RFC 9309 directive evaluation.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )
        else:
            evidence.append(f"Before: AI crawler was permitted by robots.txt (rule: {before_rule or 'None'}).")
            evidence.append(f"After: AI crawler REMAINS PERMITTED by robots.txt (rule: {after_rule or 'None'}).")
            if score_delta != 0:
                evidence.append(
                    f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}), "
                    f"BUT expected robots restriction is ABSENT. "
                    f"Per security validation principle, score changes do not substitute for actual restriction enforcement."
                )
            else:
                evidence.append("Expected robots.txt security restriction was not applied.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.FAILED,
                evidence=evidence,
                timestamp=timestamp,
            )

    @classmethod
    def _validate_security_rate_limit(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """
        Validates Phase 3 Security Restriction: AI_RATE_LIMIT.
        Objective: ACCESSIBLE -> INTENTIONALLY BLOCKED / RATE LIMITED (HTTP 429).
        """
        b_verdict, b_mech, b_status, b_blocked = cls._extract_detection_status(audit_before)
        a_verdict, a_mech, a_status, a_blocked = cls._extract_detection_status(audit_after)

        was_rate_limited = (b_status == 429) or ("RATE" in b_mech) or ("RATE" in b_verdict)
        is_rate_limited = (a_status == 429) or ("RATE" in a_mech) or ("RATE" in a_verdict)

        issue_before = {
            "category": "AI_RATE_LIMIT",
            "http_status": b_status,
            "verdict": b_verdict,
            "mechanism": b_mech,
            "blocked": b_blocked,
            "rate_limited": was_rate_limited,
        }
        issue_after = {
            "category": "AI_RATE_LIMIT",
            "http_status": a_status,
            "verdict": a_verdict,
            "mechanism": a_mech,
            "blocked": a_blocked,
            "rate_limited": is_rate_limited,
        }

        evidence: List[str] = []

        # Check unchanged state
        if b_verdict == a_verdict and b_mech == a_mech and b_status == a_status and before_score == after_score:
            if not is_rate_limited and a_status == 200:
                evidence.append("Result is completely UNCHANGED between baseline and post-enforcement audits.")
                evidence.append(f"HTTP Status: {a_status}, Verdict: {a_verdict}. AI crawler remains unthrottled.")
                evidence.append("Expected rate-limiting restriction was not applied.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Baseline already rate limited
        if was_rate_limited:
            if is_rate_limited:
                evidence.append(f"Baseline crawler was ALREADY rate-limited (HTTP {b_status}, {b_mech}).")
                evidence.append(f"Post-enforcement observation: crawler remains rate-limited (HTTP {a_status}, {a_mech}).")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                    details={"already_restricted_in_baseline": True},
                )

        # Successful rate limiting
        if is_rate_limited:
            evidence.append(f"Before: AI crawler had normal access (HTTP {b_status}, {b_verdict}).")
            evidence.append(f"After: AI crawler is now INTENTIONALLY RATE LIMITED (HTTP {a_status}, mechanism: {a_mech}).")
            evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
            evidence.append("Rate-limiting security enforcement confirmed.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )

        # Partial verification (e.g. 403 or blocked, but not explicitly 429)
        if a_blocked or a_status in (403, 503):
            evidence.append(f"Before: HTTP {b_status} {b_verdict}.")
            evidence.append(f"After: HTTP {a_status} {a_verdict} via {a_mech}.")
            evidence.append("Partially verified: crawler access was restricted/blocked, but HTTP 429 Rate Limit was not specifically returned.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.PARTIALLY_VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )

        # Failed: Still accessible
        evidence.append(f"Before: AI crawler was accessible (HTTP {b_status}).")
        evidence.append(f"After: AI crawler REMAINS accessible (HTTP {a_status}, {a_verdict}). Expected rate limiting (HTTP 429).")
        if score_delta != 0:
            evidence.append(
                f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}), "
                f"BUT rate limit restriction was NOT observed. Actual crawler state must prove restriction."
            )
        else:
            evidence.append("Expected rate-limiting restriction did not occur.")
        return ValidationResult(
            before_score=before_score,
            after_score=after_score,
            score_delta=score_delta,
            issue_before=issue_before,
            issue_after=issue_after,
            fix_status=fix_status,
            validation_status=ValidationStatus.FAILED,
            evidence=evidence,
            timestamp=timestamp,
        )

    @classmethod
    def _validate_security_waf_challenge(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """
        Validates Phase 3 Security Restriction: AI_WAF_CHALLENGE.
        Objective: ACCESSIBLE -> INTENTIONALLY CHALLENGED / BLOCKED by WAF.
        """
        b_verdict, b_mech, b_status, b_blocked = cls._extract_detection_status(audit_before)
        a_verdict, a_mech, a_status, a_blocked = cls._extract_detection_status(audit_after)

        was_waf_challenged = cls._has_waf_evidence(b_verdict, b_mech)
        is_waf_challenged = cls._has_waf_evidence(a_verdict, a_mech)

        issue_before = {
            "category": "AI_WAF_CHALLENGE",
            "verdict": b_verdict,
            "mechanism": b_mech,
            "http_status": b_status,
            "blocked": b_blocked,
        }
        issue_after = {
            "category": "AI_WAF_CHALLENGE",
            "verdict": a_verdict,
            "mechanism": a_mech,
            "http_status": a_status,
            "blocked": a_blocked,
        }

        evidence: List[str] = []

        # Check unchanged state
        if b_verdict == a_verdict and b_mech == a_mech and b_status == a_status and b_blocked == a_blocked and before_score == after_score:
            if not is_waf_challenged and a_status == 200:
                evidence.append("Result is completely UNCHANGED between baseline and post-enforcement audits.")
                evidence.append(f"AI crawler remains accessible (HTTP {a_status}, {a_verdict}).")
                evidence.append("Expected WAF challenge security restriction was not applied.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Baseline already challenged
        if was_waf_challenged:
            if is_waf_challenged:
                evidence.append(f"Baseline crawler was ALREADY challenged/blocked by WAF ({b_verdict} via {b_mech}, HTTP {b_status}).")
                evidence.append(f"Post-enforcement observation: crawler remains challenged/blocked ({a_verdict} via {a_mech}, HTTP {a_status}).")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                    details={"already_restricted_in_baseline": True},
                )

        # Successfully challenged/blocked
        if is_waf_challenged:
            evidence.append(f"Before: AI crawler had unrestricted access (HTTP {b_status}, {b_verdict}).")
            evidence.append(f"After: AI crawler is now INTENTIONALLY CHALLENGED/BLOCKED by WAF ({a_verdict} via {a_mech}, HTTP {a_status}).")
            evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
            evidence.append("WAF challenge security policy confirmed enforced.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )

        # Failed: Still accessible
        evidence.append(f"Before: AI crawler was accessible (HTTP {b_status}).")
        evidence.append(f"After: AI crawler REMAINS accessible (HTTP 200, {a_verdict}). Expected WAF challenge.")
        if score_delta != 0:
            evidence.append(
                f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}), "
                f"BUT WAF challenge was NOT triggered. Actual crawler state must prove restriction."
            )
        else:
            evidence.append("Expected WAF challenge security restriction did not occur.")
        return ValidationResult(
            before_score=before_score,
            after_score=after_score,
            score_delta=score_delta,
            issue_before=issue_before,
            issue_after=issue_after,
            fix_status=fix_status,
            validation_status=ValidationStatus.FAILED,
            evidence=evidence,
            timestamp=timestamp,
        )

    @classmethod
    def _validate_security_captcha(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """
        Validates Phase 3 Security Restriction: AI_CAPTCHA.
        Objective: ACCESSIBLE -> INTENTIONALLY CHALLENGED with CAPTCHA / Turnstile.
        """
        b_verdict, b_mech, b_status, b_blocked = cls._extract_detection_status(audit_before)
        a_verdict, a_mech, a_status, a_blocked = cls._extract_detection_status(audit_after)

        crawl_b = audit_before.get("target_persona") or audit_before.get("crawl", audit_before)
        signals_b = cls._extract_detection_signals(crawl_b)
        was_captcha = any("captcha" in s.lower() or "turnstile" in s.lower() or "hcaptcha" in s.lower() for s in signals_b) or ("CAPTCHA" in b_mech) or ("TURNSTILE" in b_mech) or ("HCAPTCHA" in b_mech)

        crawl_a = audit_after.get("target_persona") or audit_after.get("crawl", audit_after)
        signals_a = cls._extract_detection_signals(crawl_a)
        is_captcha = any("captcha" in s.lower() or "turnstile" in s.lower() or "hcaptcha" in s.lower() for s in signals_a) or ("CAPTCHA" in a_mech) or ("TURNSTILE" in a_mech) or ("HCAPTCHA" in a_mech)

        issue_before = {
            "category": "AI_CAPTCHA",
            "verdict": b_verdict,
            "mechanism": b_mech,
            "http_status": b_status,
            "captcha_detected": was_captcha,
        }
        issue_after = {
            "category": "AI_CAPTCHA",
            "verdict": a_verdict,
            "mechanism": a_mech,
            "http_status": a_status,
            "captcha_detected": is_captcha,
        }

        evidence: List[str] = []

        # Check unchanged state
        if b_verdict == a_verdict and b_mech == a_mech and b_status == a_status and was_captcha == is_captcha and before_score == after_score:
            if not is_captcha and a_status == 200:
                evidence.append("Result is completely UNCHANGED between baseline and post-enforcement audits.")
                evidence.append(f"AI crawler accessed target without CAPTCHA challenge (HTTP {a_status}).")
                evidence.append("Expected CAPTCHA security challenge was not presented.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Baseline already had CAPTCHA
        if was_captcha:
            if is_captcha:
                evidence.append(f"Baseline crawler was ALREADY presented with CAPTCHA ({b_mech}, {b_verdict}).")
                evidence.append(f"Post-enforcement observation: CAPTCHA challenge remains active ({a_mech}, {a_verdict}).")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                    details={"already_restricted_in_baseline": True},
                )

        # Successfully presented with CAPTCHA
        if is_captcha:
            evidence.append(f"Before: AI crawler had direct access without CAPTCHA challenge (HTTP {b_status}, {b_verdict}).")
            evidence.append(f"After: AI crawler is now INTENTIONALLY CHALLENGED with CAPTCHA ({a_mech}, verdict: {a_verdict}).")
            evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
            evidence.append("CAPTCHA challenge security policy confirmed enforced.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )

        # Partially verified (e.g. challenged by general WAF, but specific CAPTCHA signal was partial)
        if a_verdict in ("CHALLENGED", "BLOCKED") or a_blocked:
            evidence.append(f"Before: HTTP {b_status} {b_verdict}.")
            evidence.append(f"After: Crawler was challenged/blocked ({a_verdict} via {a_mech}), but explicit CAPTCHA payload was partially verified.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.PARTIALLY_VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )

        # Failed: Still accessible
        evidence.append(f"Before: AI crawler was accessible (HTTP {b_status}).")
        evidence.append(f"After: AI crawler REMAINS accessible (HTTP 200, {a_verdict}). Expected CAPTCHA challenge.")
        if score_delta != 0:
            evidence.append(
                f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}), "
                f"BUT CAPTCHA challenge was NOT triggered. Actual crawler state must prove restriction."
            )
        else:
            evidence.append("Expected CAPTCHA challenge did not occur.")
        return ValidationResult(
            before_score=before_score,
            after_score=after_score,
            score_delta=score_delta,
            issue_before=issue_before,
            issue_after=issue_after,
            fix_status=fix_status,
            validation_status=ValidationStatus.FAILED,
            evidence=evidence,
            timestamp=timestamp,
        )

    @classmethod
    def _validate_security_authentication(
        cls,
        audit_before: Dict[str, Any],
        audit_after: Dict[str, Any],
        target: TargetIssue,
        before_score: int,
        after_score: int,
        score_delta: int,
        fix_status: str,
        timestamp: str,
    ) -> ValidationResult:
        """
        Validates Phase 3 Security Restriction: AI_AUTHENTICATION.
        Objective: ACCESSIBLE -> INTENTIONALLY REQUIRES AUTHENTICATION (HTTP 401 / 403 / Auth challenge).
        """
        b_verdict, b_mech, b_status, b_blocked = cls._extract_detection_status(audit_before)
        a_verdict, a_mech, a_status, a_blocked = cls._extract_detection_status(audit_after)

        crawl_a = audit_after.get("target_persona") or audit_after.get("crawl", audit_after)
        headers_a = crawl_a.get("http", {}).get("headers", {}) if isinstance(crawl_a, dict) else {}
        auth_header_a = any("www-authenticate" in k.lower() or "authorization" in k.lower() for k in headers_a)

        was_auth_required = (b_status in (401, 407))
        is_auth_required = (a_status in (401, 407)) or auth_header_a or (a_status == 403 and "auth" in a_mech.lower())

        issue_before = {
            "category": "AI_AUTHENTICATION",
            "http_status": b_status,
            "verdict": b_verdict,
            "auth_required": was_auth_required,
        }
        issue_after = {
            "category": "AI_AUTHENTICATION",
            "http_status": a_status,
            "verdict": a_verdict,
            "auth_required": is_auth_required,
        }

        evidence: List[str] = []

        # Check unchanged state
        if b_status == a_status and b_verdict == a_verdict and before_score == after_score:
            if not is_auth_required and a_status == 200:
                evidence.append("Result is completely UNCHANGED between baseline and post-enforcement audits.")
                evidence.append(f"AI crawler accessed target without authentication (HTTP {a_status}).")
                evidence.append("Expected authentication requirement was not enforced.")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.FAILED,
                    evidence=evidence,
                    timestamp=timestamp,
                )

        # Baseline already required authentication
        if was_auth_required:
            if is_auth_required:
                evidence.append(f"Baseline crawler was ALREADY required to authenticate (HTTP {b_status}).")
                evidence.append(f"Post-enforcement observation: authentication requirement remains active (HTTP {a_status}).")
                return ValidationResult(
                    before_score=before_score,
                    after_score=after_score,
                    score_delta=score_delta,
                    issue_before=issue_before,
                    issue_after=issue_after,
                    fix_status=fix_status,
                    validation_status=ValidationStatus.VERIFIED,
                    evidence=evidence,
                    timestamp=timestamp,
                    details={"already_restricted_in_baseline": True},
                )

        # Successfully requires authentication
        if is_auth_required:
            evidence.append(f"Before: AI crawler had unauthenticated access (HTTP {b_status}, {b_verdict}).")
            evidence.append(f"After: AI crawler access now INTENTIONALLY REQUIRES AUTHENTICATION (HTTP {a_status}).")
            evidence.append(f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}).")
            evidence.append("Authentication access control confirmed enforced.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )

        # Partial verification (e.g. redirect towards login or 403)
        if a_status in (301, 302, 307, 403):
            evidence.append(f"Before: HTTP {b_status} {b_verdict}.")
            evidence.append(f"After: HTTP {a_status} {a_verdict}. Access restricted, partially verified authentication challenge.")
            return ValidationResult(
                before_score=before_score,
                after_score=after_score,
                score_delta=score_delta,
                issue_before=issue_before,
                issue_after=issue_after,
                fix_status=fix_status,
                validation_status=ValidationStatus.PARTIALLY_VERIFIED,
                evidence=evidence,
                timestamp=timestamp,
            )

        # Failed: Still accessible
        evidence.append(f"Before: AI crawler was unauthenticated (HTTP {b_status}).")
        evidence.append(f"After: AI crawler continues receiving HTTP {a_status} without authentication requirement.")
        if score_delta != 0:
            evidence.append(
                f"Score changed by {score_delta:+d} points ({before_score} -> {after_score}), "
                f"BUT authentication requirement was NOT enforced."
            )
        else:
            evidence.append("Expected authentication requirement did not occur.")
        return ValidationResult(
            before_score=before_score,
            after_score=after_score,
            score_delta=score_delta,
            issue_before=issue_before,
            issue_after=issue_after,
            fix_status=fix_status,
            validation_status=ValidationStatus.FAILED,
            evidence=evidence,
            timestamp=timestamp,
        )

    # =========================================================================
    # Helpers & Normalizers
    # =========================================================================

    @classmethod
    def _is_controlled_target(cls, target_url: str) -> bool:
        """Whether an in-process control action may safely target this URL."""
        from urllib.parse import urlparse

        host = (urlparse(target_url).hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "::1"}

    @classmethod
    def _has_waf_evidence(cls, verdict: str, mechanism: str) -> bool:
        """Require a detector-recognized WAF/challenge mechanism, not HTTP 403 alone."""
        mechanism = mechanism.upper()
        waf_markers = ("WAF", "CLOUDFLARE", "DATADOME", "PERIMETERX", "AKAMAI", "CUSTOM_BOT_BLOCK")
        return verdict in ("CHALLENGED", "BLOCKED") and any(marker in mechanism for marker in waf_markers)

    @classmethod
    def _extract_detection_signals(cls, crawl: Any) -> List[str]:
        """Collect top-level and evidence-layer detector signals from CrawlResult."""
        if not isinstance(crawl, dict):
            return []
        detection = crawl.get("detection", {})
        if not isinstance(detection, dict):
            return []
        evidence = detection.get("evidence", {})
        signals = list(detection.get("signals", []) or [])
        if isinstance(evidence, dict):
            for key in ("dom_signals", "matched_keywords", "matched_headers"):
                signals.extend(evidence.get(key, []) or [])
        return [str(signal) for signal in signals]

    @classmethod
    def _persona_observations(cls, audit: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract named Phase 1 crawl observations from supported aggregate schemas."""
        observations: Dict[str, Dict[str, Any]] = {}

        def add(candidate: Any, fallback: Optional[str] = None) -> None:
            if not isinstance(candidate, dict):
                return
            name = str(candidate.get("persona") or fallback or "").lower()
            if name:
                observations[name] = candidate

        add(audit.get("target_persona"))
        add(audit.get("baseline_browser"), "standard_browser")
        add(audit.get("crawl"))
        for key in ("raw_results", "results", "personas"):
            value = audit.get(key)
            if isinstance(value, list):
                for candidate in value:
                    add(candidate)
            elif isinstance(value, dict):
                for name, candidate in value.items():
                    add(candidate, str(name))
        # crawl_target() stores the underlying CrawlResult under bots.<name>.raw.
        bots = audit.get("bots", {})
        if isinstance(bots, dict):
            for name, candidate in bots.items():
                if isinstance(candidate, dict):
                    add(candidate.get("raw"), str(name))
        return observations

    @classmethod
    def _persona_is_accessible(cls, crawl: Dict[str, Any]) -> bool:
        verdict, _, status, blocked = cls._extract_detection_status(crawl)
        allowed, _ = cls._extract_robots_status(crawl)
        return allowed and not blocked and verdict == "ACCESSIBLE" and 200 <= status < 300

    @classmethod
    def _persona_is_restricted(cls, crawl: Dict[str, Any]) -> bool:
        """Whether a Phase 1 observation proves the persona was restricted."""
        verdict, _, status, blocked = cls._extract_detection_status(crawl)
        allowed, _ = cls._extract_robots_status(crawl)
        return not allowed or blocked or verdict in ("RESTRICTED", "BLOCKED", "CHALLENGED") or status in (401, 429)

    @classmethod
    def _apply_target_persona_guard(
        cls, result: ValidationResult, audit_after: Dict[str, Any], target: TargetIssue
    ) -> ValidationResult:
        """Require every explicitly targeted persona to be observed as restricted."""
        if not target.target_personas or result.validation_status not in (
            ValidationStatus.VERIFIED,
            ValidationStatus.PARTIALLY_VERIFIED,
        ):
            return result

        observations = cls._persona_observations(audit_after)
        missing, still_accessible = [], []
        for persona in target.target_personas:
            crawl = observations.get(persona.lower())
            if crawl is None:
                missing.append(persona)
            elif not cls._persona_is_restricted(crawl):
                verdict, mechanism, status, _ = cls._extract_detection_status(crawl)
                still_accessible.append(f"{persona} (HTTP {status}, {verdict} via {mechanism})")

        if missing:
            result.validation_status = ValidationStatus.INCONCLUSIVE
            result.evidence.append(
                "Target-persona restriction check is inconclusive: no post-control crawler observation for "
                + ", ".join(missing) + "."
            )
        elif still_accessible:
            result.validation_status = ValidationStatus.PARTIALLY_VERIFIED
            result.evidence.append(
                "Partial enforcement: explicitly targeted personas remain accessible: "
                + ", ".join(still_accessible) + "."
            )
            result.details["unrestricted_target_personas"] = still_accessible
        return result

    @classmethod
    def _apply_collateral_guard(
        cls, result: ValidationResult, audit_after: Dict[str, Any], target: TargetIssue
    ) -> ValidationResult:
        """Downgrade a target success when declared allowed traffic was blocked or unobserved."""
        if not target.allowed_personas or result.validation_status not in (
            ValidationStatus.VERIFIED,
            ValidationStatus.PARTIALLY_VERIFIED,
        ):
            return result

        observations = cls._persona_observations(audit_after)
        missing, impacted = [], []
        for persona in target.allowed_personas:
            crawl = observations.get(persona.lower())
            if crawl is None:
                missing.append(persona)
            elif not cls._persona_is_accessible(crawl):
                verdict, mechanism, status, _ = cls._extract_detection_status(crawl)
                impacted.append(f"{persona} (HTTP {status}, {verdict} via {mechanism})")

        if missing:
            result.validation_status = ValidationStatus.INCONCLUSIVE
            result.evidence.append(
                "Allowed-traffic collateral check is inconclusive: no post-control crawler observation for "
                + ", ".join(missing) + "."
            )
        if impacted:
            result.validation_status = ValidationStatus.PARTIALLY_VERIFIED
            result.evidence.append(
                "Collateral impact detected: target restriction was observed, but explicitly allowed traffic was also restricted: "
                + ", ".join(impacted) + "."
            )
            result.details["collateral_impacted_personas"] = impacted
        return result

    @classmethod
    def _extract_score(cls, audit: Dict[str, Any]) -> int:
        """Safely pulls the 0-100 score from an audit or scoring dict."""
        if not isinstance(audit, dict):
            return 0
        if "score" in audit and isinstance(audit["score"], (int, float)):
            return int(audit["score"])
        scoring = audit.get("scoring", {})
        if isinstance(scoring, dict) and "score" in scoring:
            return int(scoring.get("score", 0))
        summary = audit.get("summary", {})
        if isinstance(summary, dict) and "score" in summary:
            return int(summary.get("score", 0))
        return 0

    @classmethod
    def _extract_latency(cls, audit: Dict[str, Any]) -> float:
        """Extracts latency in milliseconds from audit."""
        if not isinstance(audit, dict):
            return 0.0
        # Check metrics
        metrics = audit.get("metrics", {})
        if "response_time_ms" in metrics:
            return float(metrics.get("response_time_ms") or 0.0)
        # Check crawl.http
        crawl = audit.get("crawl", audit)
        http_data = crawl.get("http", {}) if isinstance(crawl, dict) else {}
        return float(http_data.get("response_time_ms") or 0.0)

    @classmethod
    def _extract_robots_status(cls, audit: Dict[str, Any], persona: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Returns (is_allowed, matching_rule)."""
        if not isinstance(audit, dict):
            return True, None

        # Check multi-persona target_persona, top-level, or crawl-level robots_txt
        crawl = audit.get("target_persona") or audit.get("crawl", audit)
        robots = crawl.get("robots_txt") if isinstance(crawl, dict) else None
        if not robots:
            robots = audit.get("robots_txt", {})
        if isinstance(robots, dict):
            is_allowed = robots.get("is_allowed")
            if is_allowed is not None:
                return bool(is_allowed), robots.get("matching_rule")
            if "ai_disallowed" in robots:
                return not bool(robots.get("ai_disallowed")), robots.get("details")

        # Check scoring / metrics
        metrics = audit.get("metrics", {})
        if "robots_allowed" in metrics:
            return bool(metrics["robots_allowed"]), None

        return True, None

    @classmethod
    def _extract_detection_status(cls, audit: Dict[str, Any]) -> Tuple[str, str, int, bool]:
        """Returns (verdict, mechanism, http_status, is_blocked)."""
        if not isinstance(audit, dict):
            return "ACCESSIBLE", "NONE", 200, False

        crawl = audit.get("target_persona") or audit.get("crawl", audit)
        det = crawl.get("detection", {}) if isinstance(crawl, dict) else {}
        inf = det.get("inference", {}) if isinstance(det, dict) else {}
        http_data = crawl.get("http", {}) if isinstance(crawl, dict) else {}

        verdict = str(inf.get("verdict") or audit.get("metrics", {}).get("verdict") or "ACCESSIBLE").upper()
        mechanism = str(inf.get("mechanism") or audit.get("metrics", {}).get("mechanism") or "NONE").upper()
        raw_status = http_data.get("status_code") or audit.get("metrics", {}).get("http_status") or 200
        status = raw_status if isinstance(raw_status, int) else 200
        is_blocked = det.get("is_blocked", False) or verdict in ["BLOCKED", "CHALLENGED"] or status in [403, 429]

        return verdict, mechanism, status, is_blocked

    @classmethod
    def _check_environment_unavailable(cls, audit: Dict[str, Any]) -> Tuple[bool, str]:
        """Checks if the test environment was down, unreachable, or rejected connection (MVP Case 6)."""
        if not isinstance(audit, dict):
            return True, "Audit payload is not a valid dictionary"

        if audit.get("status") == "error":
            return True, audit.get("error") or "Audit reported error status"

        if "error" in audit and audit["error"] and audit.get("status") != "success":
            return True, str(audit["error"])

        crawl = audit.get("crawl", audit)
        if isinstance(crawl, dict):
            if crawl.get("success") is False:
                return True, crawl.get("error") or "Crawler failed to complete execution"
            if crawl.get("error"):
                return True, str(crawl.get("error"))
            http_status = crawl.get("http", {}).get("status_code")
            if http_status in (502, 504):
                return True, f"HTTP {http_status} Gateway/Proxy error (environment unavailable or target rejected connection)"
            if http_status == 503 and crawl.get("success") is False:
                return True, "HTTP 503 Service Unavailable (environment unavailable or target rejected connection)"

        return False, ""

    @classmethod
    def _check_inconclusive_verdict(cls, audit: Dict[str, Any]) -> Tuple[bool, str]:
        """Checks if crawler observation resulted in an inconclusive finding (MVP Case 7)."""
        if not isinstance(audit, dict):
            return False, ""
        verdict, mech, status, _ = cls._extract_detection_status(audit)
        if verdict == "INCONCLUSIVE":
            return True, f"Crawler returned verdict=INCONCLUSIVE (mechanism: {mech}, status: {status})"
        return False, ""

    @classmethod
    def _extract_penalties(cls, audit: Dict[str, Any]) -> List[Dict[str, Any]]:
        scoring = audit.get("scoring", audit)
        if isinstance(scoring, dict) and "penalties" in scoring:
            return scoring.get("penalties") or []
        return []

    @classmethod
    def _resolve_target_issue(
        cls,
        target_issue: Optional[Union[TargetIssue, IssueCategory, str, Dict[str, Any]]],
        audit_before: Dict[str, Any],
    ) -> TargetIssue:
        """Standardizes target issue into a TargetIssue model."""
        if isinstance(target_issue, TargetIssue):
            return target_issue

        if isinstance(target_issue, IssueCategory):
            is_sec = target_issue in (
                IssueCategory.AI_ROBOTS_RESTRICTION,
                IssueCategory.AI_RATE_LIMIT,
                IssueCategory.AI_WAF_CHALLENGE,
                IssueCategory.AI_CAPTCHA,
                IssueCategory.AI_AUTHENTICATION,
            )
            return TargetIssue(category=target_issue, is_security_restriction=is_sec)

        if isinstance(target_issue, str):
            s = target_issue.upper().replace("-", "_").strip()
            is_sec = "RESTRICT" in s or "SECURITY" in s or s.startswith("AI_") or "AI_" in s

            # Phase 3 Security Restrictions (ACCESSIBLE -> INTENTIONALLY RESTRICTED)
            if s == "AI_ROBOTS_RESTRICTION" or ("ROBOT" in s and is_sec):
                return TargetIssue(
                    category=IssueCategory.AI_ROBOTS_RESTRICTION,
                    expected_resolved_state="RESTRICTED",
                    description=target_issue,
                    is_security_restriction=True,
                )
            elif s == "AI_RATE_LIMIT" or ("RATE" in s and is_sec) or ("429" in s and is_sec):
                return TargetIssue(
                    category=IssueCategory.AI_RATE_LIMIT,
                    expected_resolved_state="BLOCKED",
                    description=target_issue,
                    is_security_restriction=True,
                )
            elif s == "AI_WAF_CHALLENGE" or ("WAF" in s and is_sec) or ("CLOUDFLARE" in s and is_sec) or ("CHALLENGE" in s and is_sec and "CAPTCHA" not in s):
                return TargetIssue(
                    category=IssueCategory.AI_WAF_CHALLENGE,
                    expected_resolved_state="CHALLENGED",
                    description=target_issue,
                    is_security_restriction=True,
                )
            elif s == "AI_CAPTCHA" or ("CAPTCHA" in s and is_sec) or ("TURNSTILE" in s and is_sec):
                return TargetIssue(
                    category=IssueCategory.AI_CAPTCHA,
                    expected_resolved_state="CHALLENGED",
                    description=target_issue,
                    is_security_restriction=True,
                )
            elif s == "AI_AUTHENTICATION" or ("AUTH" in s and is_sec):
                return TargetIssue(
                    category=IssueCategory.AI_AUTHENTICATION,
                    expected_resolved_state="RESTRICTED",
                    description=target_issue,
                    is_security_restriction=True,
                )
            elif is_sec:
                return TargetIssue(
                    category=IssueCategory.AI_RESTRICTION,
                    expected_resolved_state="RESTRICTED",
                    description=target_issue,
                    is_security_restriction=True,
                )

            # Phase 2 Optimization (RESTRICTED -> ACCESSIBLE)
            elif "ROBOT" in s:
                return TargetIssue(
                    category=IssueCategory.ROBOTS_TXT,
                    expected_resolved_state="ALLOWED",
                    description=target_issue,
                )
            elif "WAF" in s or "CLOUDFLARE" in s or ("CHALLENGE" in s and "CAPTCHA" not in s):
                return TargetIssue(
                    category=IssueCategory.WAF_CHALLENGE,
                    expected_resolved_state="ACCESSIBLE",
                    description=target_issue,
                )
            elif "CAPTCHA" in s or "TURNSTILE" in s:
                return TargetIssue(
                    category=IssueCategory.CAPTCHA,
                    expected_resolved_state="ACCESSIBLE",
                    description=target_issue,
                )
            elif "LATENCY" in s or "SPEED" in s or "PERF" in s:
                return TargetIssue(category=IssueCategory.LATENCY, description=target_issue)
            elif "429" in s or "RATE" in s:
                return TargetIssue(
                    category=IssueCategory.RATE_LIMIT,
                    expected_resolved_state="200",
                    description=target_issue,
                )
            elif "5" in s and "STATUS" in s:
                return TargetIssue(category=IssueCategory.SERVER_ERROR, description=target_issue)

            return TargetIssue(category=IssueCategory.OTHER, description=target_issue)

        if isinstance(target_issue, dict):
            cat_str = str(target_issue.get("category", target_issue.get("control_id", "OTHER"))).upper().replace("-", "_").strip()
            cat = IssueCategory.OTHER
            for c in IssueCategory:
                if c.value == cat_str:
                    cat = c
                    break

            is_sec = (
                bool(target_issue.get("is_security_restriction"))
                or bool(target_issue.get("is_restriction"))
                or cat in (
                    IssueCategory.AI_ROBOTS_RESTRICTION,
                    IssueCategory.AI_RATE_LIMIT,
                    IssueCategory.AI_WAF_CHALLENGE,
                    IssueCategory.AI_CAPTCHA,
                    IssueCategory.AI_AUTHENTICATION,
                    IssueCategory.AI_RESTRICTION,
                )
                or "RESTRICT" in cat_str
                or "SECURITY" in cat_str
                or cat_str.startswith("AI_")
            )

            exp_state = target_issue.get("expected_resolved_state")
            if not exp_state and is_sec:
                if "ROBOT" in cat_str or cat == IssueCategory.AI_ROBOTS_RESTRICTION:
                    exp_state = "RESTRICTED"
                elif "WAF" in cat_str or "CAPTCHA" in cat_str or "CHALLENGE" in cat_str or cat in (IssueCategory.AI_WAF_CHALLENGE, IssueCategory.AI_CAPTCHA):
                    exp_state = "CHALLENGED"
                elif "RATE" in cat_str or "429" in cat_str or cat == IssueCategory.AI_RATE_LIMIT:
                    exp_state = "BLOCKED"
                else:
                    exp_state = "RESTRICTED"

            if cat == IssueCategory.OTHER and is_sec:
                if "ROBOT" in cat_str:
                    cat = IssueCategory.AI_ROBOTS_RESTRICTION
                elif "RATE" in cat_str or "429" in cat_str:
                    cat = IssueCategory.AI_RATE_LIMIT
                elif "WAF" in cat_str or ("CHALLENGE" in cat_str and "CAPTCHA" not in cat_str):
                    cat = IssueCategory.AI_WAF_CHALLENGE
                elif "CAPTCHA" in cat_str or "TURNSTILE" in cat_str:
                    cat = IssueCategory.AI_CAPTCHA
                elif "AUTH" in cat_str:
                    cat = IssueCategory.AI_AUTHENTICATION
                else:
                    cat = IssueCategory.AI_RESTRICTION

            return TargetIssue(
                category=cat,
                persona=target_issue.get("persona"),
                expected_previous_state=target_issue.get("expected_previous_state"),
                expected_resolved_state=exp_state,
                description=target_issue.get("description") or target_issue.get("control_id"),
                threshold=target_issue.get("threshold"),
                is_security_restriction=bool(is_sec),
                target_personas=target_issue.get("target_personas") or [],
                allowed_personas=target_issue.get("allowed_personas") or [],
            )

        # Auto-infer from audit_before
        penalties = cls._extract_penalties(audit_before)
        if len(penalties) > 1:
            return TargetIssue(category=IssueCategory.OTHER, description="Multi-barrier baseline audit")

        robots_allowed, _ = cls._extract_robots_status(audit_before)
        if not robots_allowed:
            return TargetIssue(category=IssueCategory.ROBOTS_TXT, description="Robots.txt disallow in baseline")

        verdict, mech, status, blocked = cls._extract_detection_status(audit_before)
        if "CAPTCHA" in mech or "TURNSTILE" in mech:
            return TargetIssue(category=IssueCategory.CAPTCHA, description=f"CAPTCHA / Turnstile in baseline ({mech})")
        if blocked or verdict in ("BLOCKED", "CHALLENGED"):
            return TargetIssue(category=IssueCategory.WAF_CHALLENGE, description=f"WAF Challenge in baseline ({mech})")
        if status == 429 or "RATE" in mech:
            return TargetIssue(category=IssueCategory.RATE_LIMIT, description=f"HTTP 429 Rate limiting in baseline")
        if status >= 500:
            return TargetIssue(category=IssueCategory.SERVER_ERROR, description=f"HTTP {status} Server error in baseline")

        latency = cls._extract_latency(audit_before)
        if latency > 3000:
            return TargetIssue(category=IssueCategory.LATENCY, description=f"High latency ({latency:.0f}ms)")

        return TargetIssue(category=IssueCategory.OTHER, description="General accessibility validation")

    @classmethod
    def _as_dict(cls, obj: Any) -> Dict[str, Any]:
        """Safely normalizes Pydantic models or dict-like objects into standard dicts."""
        if obj is None:
            return {}
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            d = obj.to_dict()
        elif hasattr(obj, "model_dump") and callable(obj.model_dump):
            d = obj.model_dump(mode="json")
        elif isinstance(obj, dict):
            d = dict(obj)
        elif hasattr(obj, "__dict__"):
            d = vars(obj)
        else:
            return {}

        # Normalize nested crawl if present as an object
        if "crawl" in d and not isinstance(d["crawl"], dict):
            crawl_obj = d["crawl"]
            if hasattr(crawl_obj, "to_dict") and callable(crawl_obj.to_dict):
                d["crawl"] = crawl_obj.to_dict()
            elif hasattr(crawl_obj, "model_dump") and callable(crawl_obj.model_dump):
                d["crawl"] = crawl_obj.model_dump(mode="json")

        return d

    @classmethod
    def _summarize_issue(cls, audit: Dict[str, Any], target: Optional[Any]) -> Union[str, Dict[str, Any]]:
        verdict, mech, status, blocked = cls._extract_detection_status(audit)
        robots_allowed, rule = cls._extract_robots_status(audit)
        return {
            "verdict": verdict,
            "mechanism": mech,
            "http_status": status,
            "blocked": blocked,
            "robots_allowed": robots_allowed,
            "robots_rule": rule,
            "score": cls._extract_score(audit),
        }
