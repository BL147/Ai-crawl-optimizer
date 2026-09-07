"""
test_integration.py - Checkpoint 2 Full Integration Test Suite
Author: Shlok (System Integrator)

Verifies the complete pipeline:
URL + persona -> Anshul's Crawler -> Scoring -> Kavish's Remediation -> Combined Result

Verifications:
1. Crawler result is correctly received by scoring.
2. Scoring produces score, risk_level, reasons, and metrics.
3. Remediation engine receives required compatible inputs.
4. Final combined object contains: crawl, score, risk_level, reasons, metrics, remediation.
5. No duplicate crawler is used in the production integration path.
6. Real crawler execution against Sandbox BEFORE vs AFTER modes.
7. Controlled schema fixtures matching Anshul's crawler output.
"""

import inspect
import sys
import time
from typing import Dict, Any

from sandbox.server import start_sandbox, set_mode, get_mode
from orchestrator import run_audit
from scoring import ScoringEngine, calculate_score
from remediation import generate_remediation
import orchestrator


# ============================================================================
# TEST SUITE 1: CONTROLLED SCHEMA FIXTURES (ANSHUL'S CRAWLER CONTRACT)
# ============================================================================

def test_controlled_crawler_schema_pipeline():
    print("\n--- [TEST SUITE 1] Controlled Anshul Schema Fixtures ---")

    # Fixture 1: WAF Challenge (Cloudflare Turnstile, HTTP 403)
    waf_challenge_fixture = {
        "target_url": "https://protected-enterprise.com",
        "persona": "gptbot",
        "user_agent": "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)",
        "timestamp": "2026-09-06T12:00:00Z",
        "success": True,
        "error": None,
        "robots_txt": {
            "exists": True,
            "url": "https://protected-enterprise.com/robots.txt",
            "status_code": 200,
            "is_allowed": True,
            "matching_rule": "Allow: /",
            "crawl_delay": None,
            "sitemaps": [],
            "ai_specific_rules": {},
            "raw_content": "User-agent: *\nAllow: /"
        },
        "http": {
            "status_code": 403,
            "final_url": "https://protected-enterprise.com",
            "redirect_count": 0,
            "redirects": [],
            "headers": {"server": "cloudflare", "cf-ray": "8c4599a1bc23-SJC"},
            "content_type": "text/html",
            "response_time_ms": 120.0,
            "server": "cloudflare",
            "x_robots_tag": None
        },
        "page": {
            "title": "Just a moment...",
            "meta_tags": {},
            "text_length": 45,
            "snippet": "Checking your browser before accessing the website.",
            "has_javascript_requirement": True
        },
        "detection": {
            "evidence": {
                "status_code": 403,
                "matched_headers": ["cf-ray: 8c4599a1bc23-SJC", "server: cloudflare"],
                "dom_signals": [".cf-turnstile", "#challenge-form"],
                "matched_keywords": ["just a moment..."],
                "page_title": "Just a moment...",
                "snippet_preview": "Checking your browser before accessing..."
            },
            "inference": {
                "verdict": "CHALLENGED",
                "mechanism": "CLOUDFLARE_CHALLENGE",
                "confidence": 0.96,
                "summary": "Cloudflare interactive challenge intercepted the crawler request."
            },
            "is_blocked": True,
            "block_type": "CLOUDFLARE_CHALLENGE",
            "confidence": 0.96,
            "signals": ["cf-ray", ".cf-turnstile"]
        }
    }

    # Step A: Scoring receives crawler result
    score_res = calculate_score(waf_challenge_fixture)
    assert "score" in score_res, "Scoring must produce 'score'"
    assert "risk_level" in score_res, "Scoring must produce 'risk_level'"
    assert "reasons" in score_res, "Scoring must produce 'reasons'"
    assert "metrics" in score_res, "Scoring must produce 'metrics'"
    assert score_res["score"] <= 75, f"Expected penalty score <= 75, got {score_res['score']}"
    assert score_res["risk_level"] in ["MEDIUM", "HIGH", "CRITICAL"], f"Expected elevated risk, got {score_res['risk_level']}"
    assert len(score_res["reasons"]) > 0, "Reasons must not be empty"
    assert score_res["metrics"]["verdict"] == "CHALLENGED"
    print("  [PASS] 1.1 WAF Challenge: Scoring correctly processed Anshul's CrawlResult schema")

    # Step B: Remediation receives crawler result
    rem_res = generate_remediation(waf_challenge_fixture)
    assert "problem_detected" in rem_res or "problem" in rem_res
    assert "code_or_configuration_change" in rem_res or "code_or_config" in rem_res
    assert "validation_steps" in rem_res
    print("  [PASS] 1.2 WAF Challenge: Kavish's remediation produced grounded recommendations")

    # Fixture 2: Inconclusive standalone 403 (Anshul Rule 11)
    inconclusive_fixture = {
        "target_url": "https://example.com/private",
        "persona": "gptbot",
        "robots_txt": {"exists": False, "is_allowed": True},
        "http": {"status_code": 403, "response_time_ms": 90.0, "headers": {}},
        "page": {"title": "403 Forbidden", "text_length": 50, "snippet": "Access Denied"},
        "detection": {
            "evidence": {"status_code": 403, "matched_headers": [], "dom_signals": [], "matched_keywords": []},
            "inference": {
                "verdict": "INCONCLUSIVE",
                "mechanism": "HTTP_FORBIDDEN",
                "confidence": 0.35,
                "summary": "Standalone HTTP 403 Forbidden without confirmed anti-bot challenge evidence."
            },
            "is_blocked": False
        }
    }
    inconcl_score = calculate_score(inconclusive_fixture)
    assert inconcl_score["score"] >= 70, f"Inconclusive 403 should only have limited penalty, got {inconcl_score['score']}"
    assert any("Inconclusive" in r for r in inconcl_score["reasons"]), "Reasons should explicitly note inconclusive nature"
    print("  [PASS] 1.3 Inconclusive 403: Properly respected Anshul's Rule 11 (limited penalty, no false claim)")

    # Fixture 3: Baseline Comparison Fixture (Selective AI Block)
    baseline_fixture = {
        "url": "https://example.com",
        "selective_ai_block_detected": True,
        "target_persona": waf_challenge_fixture,
        "baseline_browser": {
            "persona": "standard_browser",
            "http": {"status_code": 200, "response_time_ms": 110.0},
            "detection": {"is_blocked": False, "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"}}
        }
    }
    base_score = calculate_score(baseline_fixture)
    assert any("Discrepancy" in p["factor"] for p in base_score["penalties"]), "Baseline discrepancy must trigger AI Discrepancy penalty"
    print("  [PASS] 1.4 Baseline comparison: Selective AI block discrepancy penalty evaluated")


# ============================================================================
# TEST SUITE 2: LIVE PIPELINE ON SANDBOX (BEFORE VS AFTER)
# ============================================================================

def test_live_pipeline_sandbox():
    print("\n--- [TEST SUITE 2] Live Pipeline on Sandbox Server ---")

    # Start sandbox server on isolated port 5058
    sandbox_url = start_sandbox(port=5058)
    print(f"  [>] Sandbox server started at: {sandbox_url}")
    time.sleep(0.5)

    # -------------------------------------------------------------
    # PHASE A: BEFORE MODE (AI Crawl Blocked)
    # -------------------------------------------------------------
    print("  [>] Testing BEFORE Mode (Simulated WAF Challenge / 403 on AI Bots)...")
    set_mode("before")
    assert get_mode() == "before"

    result_before = run_audit(sandbox_url, persona="gptbot")

    # 1. Verify Minimum Mandated Keys
    mandated_keys = ["crawl", "score", "risk_level", "reasons", "metrics", "remediation"]
    for k in mandated_keys:
        assert k in result_before, f"Missing mandated key '{k}' in run_audit result"

    # 2. Verify Scoring Output
    assert isinstance(result_before["score"], (int, float)), "Score must be numeric"
    assert result_before["score"] < 50, f"Expected Grade F in BEFORE mode, got {result_before['score']}"
    assert result_before["risk_level"] in ["CRITICAL", "HIGH"], f"Expected high/critical risk, got {result_before['risk_level']}"
    assert isinstance(result_before["reasons"], list) and len(result_before["reasons"]) > 0

    # 3. Verify Metrics Output
    m_before = result_before["metrics"]
    assert "http_status" in m_before
    assert "verdict" in m_before
    assert "mechanism" in m_before
    assert "robots_allowed" in m_before

    # 4. Verify Remediation Output
    rem_before = result_before["remediation"]
    assert isinstance(rem_before, dict)
    assert "problem_detected" in rem_before or "problem" in rem_before
    assert "code_or_configuration_change" in rem_before or "code_or_config" in rem_before

    print(f"    --> Score: {result_before['score']}/100 | Risk: {result_before['risk_level']}")
    print(f"    --> Reasons count: {len(result_before['reasons'])}")
    print("  [PASS] 2.1 Live BEFORE Mode verified with full pipeline")

    # -------------------------------------------------------------
    # PHASE B: AFTER MODE (AI Optimized / 200 OK)
    # -------------------------------------------------------------
    print("  [>] Testing AFTER Mode (AI Optimized 200 OK)...")
    set_mode("after")
    assert get_mode() == "after"

    result_after = run_audit(sandbox_url, persona="gptbot")

    for k in mandated_keys:
        assert k in result_after, f"Missing mandated key '{k}' in run_audit result"

    assert result_after["score"] >= 90, f"Expected Grade A (>=90) in AFTER mode, got {result_after['score']}"
    assert result_after["risk_level"] == "LOW", f"Expected LOW risk in AFTER mode, got {result_after['risk_level']}"
    assert result_after["metrics"]["http_status"] == 200

    print(f"    --> Score: {result_after['score']}/100 | Risk: {result_after['risk_level']}")
    print("  [PASS] 2.2 Live AFTER Mode verified with full pipeline")


# ============================================================================
# TEST SUITE 3: NO DUPLICATE CRAWLER IN PRODUCTION PATH
# ============================================================================

def test_no_duplicate_crawler_in_production():
    print("\n--- [TEST SUITE 3] Duplicate Crawler Check ---")
    source_lines = inspect.getsource(orchestrator.run_audit)

    # Assert production path imports from crawler module
    assert "from crawler import crawl_sync, crawl_with_baseline_sync" in inspect.getsource(orchestrator)
    assert "crawl_with_baseline_sync" in source_lines or "crawl_sync" in source_lines

    # Assert no legacy requests fetchers in orchestrator
    assert "_fetch_with_agent" not in dir(orchestrator), "Duplicate _fetch_with_agent should not exist in orchestrator"
    assert "EMULATED_AGENTS" not in dir(orchestrator), "Duplicate EMULATED_AGENTS should not exist in orchestrator"
    print("  [PASS] 3.1 Verified: No duplicate crawler in production path; Anshul's crawler is the sole engine")


# ============================================================================
# MAIN ENTRYPOINT
# ============================================================================

def run_all_tests():
    print("=" * 70)
    print("CHECKPOINT 2: FULL SYSTEM INTEGRATION VERIFICATION")
    print("=" * 70)

    test_controlled_crawler_schema_pipeline()
    test_live_pipeline_sandbox()
    test_no_duplicate_crawler_in_production()

    print("\n" + "=" * 70)
    print("ALL CHECKPOINT 2 INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
