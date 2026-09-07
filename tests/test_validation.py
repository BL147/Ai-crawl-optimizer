"""
tests/test_validation.py - Comprehensive Test Suite for Phase 2 Fix Validation Engine
Author: Shlok (System Integrator)

Verifies all 8 mandated MVP Validation Cases:
1. Successful robots fix (VERIFIED)
2. Failed robots fix (FAILED)
3. Result unchanged (FAILED)
4. Score improves but original issue remains (FAILED)
5. Issue was already fixed before validation (VERIFIED with baseline note)
6. Test environment unavailable (INCONCLUSIVE)
7. Inconclusive crawler result (INCONCLUSIVE)
8. Successful latency/performance fix (VERIFIED)
+ Output schema compliance
+ Live sandbox server verification (VERIFIED and FAILED scenarios)
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation import (
    FixValidationEngine,
    ValidationStatus,
    ValidationResult,
    TargetIssue,
    IssueCategory,
    FixStatus,
    compare_and_validate,
    validate_fix,
)
from sandbox.server import start_sandbox, set_mode, get_mode


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

def _fixture_robots_blocked():
    return {
        "score": 70,
        "robots_txt": {"is_allowed": False, "matching_rule": "Disallow: / for GPTBot"},
        "metrics": {"robots_allowed": False, "http_status": 200, "verdict": "ACCESSIBLE", "mechanism": "NONE"},
        "crawl": {
            "success": True,
            "robots_txt": {"is_allowed": False, "matching_rule": "Disallow: / for GPTBot"},
            "http": {"status_code": 200, "response_time_ms": 150.0},
            "detection": {"is_blocked": False, "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"}},
        },
    }


def _fixture_robots_allowed():
    return {
        "score": 100,
        "robots_txt": {"is_allowed": True, "matching_rule": "Allow: /"},
        "metrics": {"robots_allowed": True, "http_status": 200, "verdict": "ACCESSIBLE", "mechanism": "NONE"},
        "crawl": {
            "success": True,
            "robots_txt": {"is_allowed": True, "matching_rule": "Allow: /"},
            "http": {"status_code": 200, "response_time_ms": 140.0},
            "detection": {"is_blocked": False, "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"}},
        },
    }


def _fixture_waf_blocked():
    return {
        "score": 35,
        "robots_txt": {"is_allowed": True, "matching_rule": "Allow: /"},
        "metrics": {"robots_allowed": True, "http_status": 403, "verdict": "CHALLENGED", "mechanism": "CLOUDFLARE_CHALLENGE"},
        "crawl": {
            "success": True,
            "robots_txt": {"is_allowed": True, "matching_rule": "Allow: /"},
            "http": {"status_code": 403, "response_time_ms": 120.0},
            "detection": {
                "is_blocked": True,
                "inference": {"verdict": "CHALLENGED", "mechanism": "CLOUDFLARE_CHALLENGE", "confidence": 0.95},
            },
        },
    }


def _fixture_waf_accessible():
    return {
        "score": 95,
        "robots_txt": {"is_allowed": True, "matching_rule": "Allow: /"},
        "metrics": {"robots_allowed": True, "http_status": 200, "verdict": "ACCESSIBLE", "mechanism": "NONE"},
        "crawl": {
            "success": True,
            "robots_txt": {"is_allowed": True, "matching_rule": "Allow: /"},
            "http": {"status_code": 200, "response_time_ms": 130.0},
            "detection": {
                "is_blocked": False,
                "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE", "confidence": 0.0},
            },
        },
    }


class TestFixValidationEngine(unittest.TestCase):

    # -----------------------------------------------------------------------
    # SCHEMA COMPLIANCE
    # -----------------------------------------------------------------------
    def test_output_schema_guarantees_all_required_fields(self):
        """Result must contain all 9 mandated keys."""
        before = _fixture_robots_blocked()
        after = _fixture_robots_allowed()
        res = compare_and_validate(before, after, target_issue="robots_txt")

        res_dict = res.to_dict()
        required_keys = [
            "before_score",
            "after_score",
            "score_delta",
            "issue_before",
            "issue_after",
            "fix_status",
            "validation_status",
            "evidence",
            "timestamp",
        ]
        for key in required_keys:
            self.assertIn(key, res_dict, f"Missing required key '{key}' in ValidationResult")

        self.assertIsInstance(res_dict["evidence"], list)
        self.assertGreater(len(res_dict["evidence"]), 0)
        self.assertEqual(res_dict["score_delta"], res_dict["after_score"] - res_dict["before_score"])

    # -----------------------------------------------------------------------
    # MVP CASE 1: Successful Robots Fix
    # -----------------------------------------------------------------------
    def test_mvp_case_1_successful_robots_fix(self):
        """Before: robots disallow -> After: robots allow -> VERIFIED."""
        before = _fixture_robots_blocked()
        after = _fixture_robots_allowed()

        res = compare_and_validate(before, after, target_issue="robots_txt")
        self.assertEqual(res.validation_status, ValidationStatus.VERIFIED)
        self.assertGreater(res.score_delta, 0)
        self.assertTrue(any("explicitly ALLOWED" in e or "confirmed resolved" in e for e in res.evidence))

    # -----------------------------------------------------------------------
    # MVP CASE 2: Failed Robots Fix
    # -----------------------------------------------------------------------
    def test_mvp_case_2_failed_robots_fix(self):
        """Before: robots disallow -> After: robots still disallow -> FAILED."""
        before = _fixture_robots_blocked()
        after = copy.deepcopy(before)
        after["score"] = 70  # Still blocked, score unchanged

        res = compare_and_validate(before, after, target_issue="robots_txt")
        self.assertEqual(res.validation_status, ValidationStatus.FAILED)
        self.assertTrue(any("remains RESTRICTED" in e for e in res.evidence))

    # -----------------------------------------------------------------------
    # MVP CASE 3: Result Unchanged
    # -----------------------------------------------------------------------
    def test_mvp_case_3_result_unchanged(self):
        """Exact identical state before and after -> FAILED."""
        before = _fixture_waf_blocked()
        after = copy.deepcopy(before)

        res = compare_and_validate(before, after)
        self.assertEqual(res.validation_status, ValidationStatus.FAILED)
        self.assertEqual(res.score_delta, 0)
        self.assertTrue(any("UNCHANGED" in e or "persists" in e for e in res.evidence))

    # -----------------------------------------------------------------------
    # MVP CASE 4: Score Improves But Original Issue Remains
    # -----------------------------------------------------------------------
    def test_mvp_case_4_score_improves_but_original_issue_remains(self):
        """Score goes from 70 to 85 (e.g. latency improved), but robots.txt still blocks bot -> FAILED."""
        before = _fixture_robots_blocked()
        before["score"] = 70
        before["crawl"]["http"]["response_time_ms"] = 3500.0

        # After: latency dropped, so score went up to 85, BUT robots.txt is STILL disallowed!
        after = copy.deepcopy(before)
        after["score"] = 85
        after["crawl"]["http"]["response_time_ms"] = 150.0

        res = compare_and_validate(before, after, target_issue="robots_txt")

        # Crucial architectural principle: Must NOT declare success just because score improved!
        self.assertEqual(res.validation_status, ValidationStatus.FAILED)
        self.assertGreater(res.score_delta, 0)  # Score did increase
        self.assertTrue(any("remains ACTIVE" in e or "score gains do not override" in e for e in res.evidence))

    # -----------------------------------------------------------------------
    # MVP CASE 5: Issue Was Already Fixed Before Validation
    # -----------------------------------------------------------------------
    def test_mvp_case_5_issue_already_fixed_before_validation(self):
        """Baseline already had the issue resolved -> VERIFIED with explicit note."""
        before = _fixture_robots_allowed()  # Already allowed before fix
        after = _fixture_robots_allowed()

        res = compare_and_validate(before, after, target_issue="robots_txt")
        self.assertEqual(res.validation_status, ValidationStatus.VERIFIED)
        self.assertTrue(res.details.get("already_fixed_in_baseline", False))
        self.assertTrue(any("ALREADY not present" in e for e in res.evidence))

    # -----------------------------------------------------------------------
    # MVP CASE 6: Test Environment Unavailable
    # -----------------------------------------------------------------------
    def test_mvp_case_6_test_environment_unavailable(self):
        """Post-fix crawl encounters environment/server down -> INCONCLUSIVE."""
        before = _fixture_waf_blocked()
        after = {
            "score": 0,
            "status": "error",
            "error": "ConnectionRefusedError: [Errno 111] Connection refused on 127.0.0.1:5050",
            "crawl": {"success": False, "error": "ConnectionRefusedError"},
        }

        res = compare_and_validate(before, after, target_issue="waf")
        self.assertEqual(res.validation_status, ValidationStatus.INCONCLUSIVE)
        self.assertTrue(any("unavailable" in e.lower() for e in res.evidence))

    # -----------------------------------------------------------------------
    # MVP CASE 7: Inconclusive Crawler Result
    # -----------------------------------------------------------------------
    def test_mvp_case_7_inconclusive_crawler_result(self):
        """Post-fix crawl verdict is INCONCLUSIVE (e.g. standalone 403) -> INCONCLUSIVE."""
        before = _fixture_waf_blocked()
        after = {
            "score": 75,
            "metrics": {"verdict": "INCONCLUSIVE", "mechanism": "HTTP_FORBIDDEN", "http_status": 403},
            "crawl": {
                "success": True,
                "http": {"status_code": 403},
                "detection": {
                    "is_blocked": False,
                    "inference": {"verdict": "INCONCLUSIVE", "mechanism": "HTTP_FORBIDDEN"},
                },
            },
        }

        res = compare_and_validate(before, after, target_issue="waf")
        self.assertEqual(res.validation_status, ValidationStatus.INCONCLUSIVE)
        self.assertTrue(any("inconclusive" in e.lower() for e in res.evidence))

    # -----------------------------------------------------------------------
    # MVP CASE 8: Successful Latency/Performance Fix
    # -----------------------------------------------------------------------
    def test_mvp_case_8_successful_latency_fix(self):
        """Before: latency 3800ms (> 3000ms threshold) -> After: latency 220ms -> VERIFIED."""
        before = {
            "score": 65,
            "metrics": {"response_time_ms": 3800.0, "http_status": 200, "verdict": "ACCESSIBLE", "mechanism": "NONE"},
            "crawl": {
                "success": True,
                "http": {"status_code": 200, "response_time_ms": 3800.0},
                "detection": {"is_blocked": False, "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"}},
            },
        }
        after = {
            "score": 95,
            "metrics": {"response_time_ms": 220.0, "http_status": 200, "verdict": "ACCESSIBLE", "mechanism": "NONE"},
            "crawl": {
                "success": True,
                "http": {"status_code": 200, "response_time_ms": 220.0},
                "detection": {"is_blocked": False, "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"}},
            },
        }

        res = compare_and_validate(before, after, target_issue=TargetIssue(category=IssueCategory.LATENCY, threshold=3000.0))
        self.assertEqual(res.validation_status, ValidationStatus.VERIFIED)
        self.assertTrue(any("successfully reduced" in e for e in res.evidence))

    # -----------------------------------------------------------------------
    # LIVE SANDBOX END-TO-END VERIFICATION
    # -----------------------------------------------------------------------
    def test_live_sandbox_verified_scenario(self):
        """Live sandbox execution: BEFORE mode -> apply fix (AFTER mode) -> VERIFIED."""
        sandbox_url = start_sandbox(port=5065)
        set_mode("before")
        self.assertEqual(get_mode(), "before")

        # Define fix action: programmatically toggle sandbox to AFTER mode via backend function
        def apply_fix():
            set_mode("after")

        res = validate_fix(
            target_url=sandbox_url,
            target_issue="waf",
            fix_action=apply_fix,
            persona="gptbot",
            timeout_seconds=10.0,
        )

        self.assertEqual(res.validation_status, ValidationStatus.VERIFIED)
        self.assertGreater(res.after_score, res.before_score)
        self.assertEqual(res.fix_status, "APPLIED")
        print(f"\n[LIVE TEST VERIFIED] Score: {res.before_score} -> {res.after_score} | Status: {res.validation_status}")

    def test_live_sandbox_failed_scenario(self):
        """Live sandbox execution: BEFORE mode -> no-op fix (remains BEFORE mode) -> FAILED."""
        sandbox_url = start_sandbox(port=5065)
        set_mode("before")
        self.assertEqual(get_mode(), "before")

        # Fix action fails or does not resolve the issue
        def noop_fix():
            pass  # Site remains in "before" mode

        res = validate_fix(
            target_url=sandbox_url,
            target_issue="waf",
            fix_action=noop_fix,
            persona="gptbot",
            timeout_seconds=10.0,
        )

        self.assertEqual(res.validation_status, ValidationStatus.FAILED)
        print(f"\n[LIVE TEST FAILED] Score: {res.before_score} -> {res.after_score} | Status: {res.validation_status}")

    # -----------------------------------------------------------------------
    # CROSS-TEAM COMPATIBILITY: DICT-STYLE ACCESS
    # -----------------------------------------------------------------------
    def test_validation_result_dict_subscripting(self):
        """Consumers can access ValidationResult attributes via dict keys or .get()."""
        before = _fixture_robots_blocked()
        after = _fixture_robots_allowed()
        res = compare_and_validate(before, after, target_issue="robots_txt")

        # Dict key access
        self.assertEqual(res["validation_status"], ValidationStatus.VERIFIED)
        self.assertEqual(res["before_score"], 70)
        self.assertEqual(res["after_score"], 100)
        self.assertEqual(res["score_delta"], 30)
        self.assertIn("evidence", res)
        self.assertEqual(res.get("validation_status"), ValidationStatus.VERIFIED)
        self.assertIsNone(res.get("nonexistent_key"))

    # -----------------------------------------------------------------------
    # AUTO-DETECTION WHEN TARGET_ISSUE IS NONE
    # -----------------------------------------------------------------------
    def test_auto_detect_target_issue_from_baseline(self):
        """If target_issue is omitted, the engine infers it from the baseline audit."""
        before = _fixture_robots_blocked()  # Contains robots restriction
        after = _fixture_robots_allowed()

        res = compare_and_validate(before, after, target_issue=None)
        self.assertEqual(res.validation_status, ValidationStatus.VERIFIED)
        self.assertTrue(any("robots" in e.lower() for e in res.evidence))

    # -----------------------------------------------------------------------
    # PARTIALLY VERIFIED STATE
    # -----------------------------------------------------------------------
    def test_partially_verified_scenario(self):
        """When some barriers are resolved but others remain -> PARTIALLY_VERIFIED."""
        before = {
            "score": 40,
            "scoring": {
                "penalties": [
                    {"factor": "Robots.txt Disallow", "penalty": -10},
                    {"factor": "Anti-Bot Shield Block", "penalty": -20},
                ]
            },
            "robots_txt": {"is_allowed": True},  # Robots fixed
            "metrics": {"robots_allowed": True, "http_status": 403, "verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK"},
            "crawl": {
                "success": True,
                "robots_txt": {"is_allowed": True},
                "http": {"status_code": 403},
                "detection": {"is_blocked": True, "inference": {"verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK"}},
            },
        }
        # After: robots penalty is gone, but WAF penalty persists
        after = {
            "score": 75,
            "scoring": {
                "penalties": [
                    {"factor": "Anti-Bot Shield Block", "penalty": -20},
                ]
            },
            "robots_txt": {"is_allowed": True},
            "metrics": {"robots_allowed": True, "http_status": 403, "verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK"},
            "crawl": {
                "success": True,
                "robots_txt": {"is_allowed": True},
                "http": {"status_code": 403},
                "detection": {"is_blocked": True, "inference": {"verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK"}},
            },
        }

        res = compare_and_validate(before, after, target_issue=None)
        self.assertEqual(res.validation_status, ValidationStatus.PARTIALLY_VERIFIED)
        self.assertTrue(any("Partially verified" in e for e in res.evidence))

    # -----------------------------------------------------------------------
    # FIX_STATUS VS VALIDATION_STATUS INDEPENDENCE
    # -----------------------------------------------------------------------
    def test_fix_status_distinct_from_validation_status(self):
        """
        Verification: Fix Application Engine applied the fix (fix_status = APPLIED),
        but crawl validation shows issue still active -> validation_status = FAILED.
        """
        before = _fixture_robots_blocked()
        after = copy.deepcopy(before)  # Still blocked

        res = compare_and_validate(before, after, target_issue="robots_txt", fix_status=FixStatus.APPLIED.value)
        self.assertEqual(res.fix_status, "APPLIED")
        self.assertEqual(res.validation_status, ValidationStatus.FAILED)

    def test_fix_status_not_applied_forwarding(self):
        """Caller specifies fix_status = NOT_APPLIED or ERROR."""
        before = _fixture_robots_blocked()
        after = copy.deepcopy(before)

        res = compare_and_validate(before, after, target_issue="robots_txt", fix_status=FixStatus.NOT_APPLIED.value)
        self.assertEqual(res.fix_status, "NOT_APPLIED")
        self.assertEqual(res.validation_status, ValidationStatus.FAILED)

    # -----------------------------------------------------------------------
    # MULTI-PERSONA AUDIT EXTRACTION
    # -----------------------------------------------------------------------
    def test_multi_persona_baseline_structure(self):
        """Validation engine unpacks multi-persona baseline format (target_persona + baseline_browser)."""
        before = {
            "score": 60,
            "target_persona": {
                "persona": "claudebot",
                "robots_txt": {"is_allowed": False, "matching_rule": "Disallow: / for ClaudeBot"},
                "http": {"status_code": 200, "response_time_ms": 160.0},
                "detection": {"is_blocked": False, "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"}},
            },
            "baseline_browser": {
                "persona": "standard_browser",
                "http": {"status_code": 200, "response_time_ms": 150.0},
            },
        }
        after = {
            "score": 100,
            "target_persona": {
                "persona": "claudebot",
                "robots_txt": {"is_allowed": True, "matching_rule": "Allow: /"},
                "http": {"status_code": 200, "response_time_ms": 140.0},
                "detection": {"is_blocked": False, "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"}},
            },
            "baseline_browser": {
                "persona": "standard_browser",
                "http": {"status_code": 200, "response_time_ms": 150.0},
            },
        }

        res = compare_and_validate(before, after, target_issue="robots_txt")
        self.assertEqual(res.validation_status, ValidationStatus.VERIFIED)
        self.assertEqual(res.score_delta, 40)


if __name__ == "__main__":
    unittest.main()

