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

        if category == IssueCategory.ROBOTS_TXT:
            return cls._validate_robots_fix(
                audit_before, audit_after, resolved_target, before_score, after_score, score_delta, fix_status, now_ts
            )
        elif category == IssueCategory.X_ROBOTS_TAG:
            return cls._validate_x_robots_tag_fix(
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
        # Import Phase 1 orchestrator dynamically to reuse without duplication
        from orchestrator import run_audit

        # Step 1: Capture Baseline Audit if not provided
        if audit_before is None:
            try:
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
    # Helpers & Normalizers
    # =========================================================================

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
        """Checks if the test environment was down or unreachable (MVP Case 6)."""
        if not isinstance(audit, dict):
            return True, "Audit payload is not a valid dictionary"

        if audit.get("status") == "error":
            return True, audit.get("error") or "Audit reported error status"

        crawl = audit.get("crawl", audit)
        if isinstance(crawl, dict):
            if crawl.get("success") is False:
                return True, crawl.get("error") or "Crawler failed to complete execution"
            http_status = crawl.get("http", {}).get("status_code")
            if http_status in (502, 504):
                return True, f"HTTP {http_status} Gateway/Proxy error (environment unavailable)"

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
            return TargetIssue(category=target_issue)

        if isinstance(target_issue, str):
            s = target_issue.upper()
            if "X_ROBOTS" in s or "X-ROBOTS" in s:
                return TargetIssue(category=IssueCategory.X_ROBOTS_TAG, description=target_issue)
            elif "ROBOT" in s:
                return TargetIssue(category=IssueCategory.ROBOTS_TXT, description=target_issue)
            elif "WAF" in s or "CLOUDFLARE" in s or "CHALLENGE" in s:
                return TargetIssue(category=IssueCategory.WAF_CHALLENGE, description=target_issue)
            elif "CAPTCHA" in s or "TURNSTILE" in s:
                return TargetIssue(category=IssueCategory.CAPTCHA, description=target_issue)
            elif "LATENCY" in s or "SPEED" in s or "PERF" in s:
                return TargetIssue(category=IssueCategory.LATENCY, description=target_issue)
            elif "429" in s or "RATE" in s:
                return TargetIssue(category=IssueCategory.RATE_LIMIT, description=target_issue)
            elif "5" in s and "STATUS" in s:
                return TargetIssue(category=IssueCategory.SERVER_ERROR, description=target_issue)
            return TargetIssue(category=IssueCategory.OTHER, description=target_issue)

        if isinstance(target_issue, dict):
            cat_str = str(target_issue.get("category", "OTHER")).upper()
            cat = IssueCategory.OTHER
            for c in IssueCategory:
                if c.value == cat_str:
                    cat = c
                    break
            return TargetIssue(
                category=cat,
                persona=target_issue.get("persona"),
                expected_previous_state=target_issue.get("expected_previous_state"),
                expected_resolved_state=target_issue.get("expected_resolved_state"),
                description=target_issue.get("description"),
                threshold=target_issue.get("threshold"),
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
    def _validate_x_robots_tag_fix(
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
        before_http = (audit_before.get("http") or {}).get("x_robots_tag")
        after_http = (audit_after.get("http") or {}).get("x_robots_tag")
        resolved = bool(before_http) and not after_http
        status = ValidationStatus.VERIFIED if resolved else ValidationStatus.FAILED
        evidence = [
            f"Before X-Robots-Tag: {before_http or 'absent'}",
            f"After X-Robots-Tag: {after_http or 'absent'}",
        ]
        evidence.append(
            "Restrictive X-Robots-Tag was removed from the fresh response."
            if resolved
            else "Restrictive X-Robots-Tag remains present or was not observed before the fix."
        )
        return ValidationResult(
            before_score=before_score,
            after_score=after_score,
            score_delta=score_delta,
            issue_before={"x_robots_tag": before_http},
            issue_after={"x_robots_tag": after_http},
            fix_status=fix_status,
            validation_status=status,
            evidence=evidence,
            timestamp=timestamp,
        )

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
