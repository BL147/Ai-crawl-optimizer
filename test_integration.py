"""
test_integration.py - End-to-End System Integration Test
Author: Shlok (System Integrator)

Verifies the full pipeline:
Sandbox Server (BEFORE vs AFTER) -> Orchestrator (run_audit) -> Scoring Engine -> Contract Validation
"""

import sys
import time
from sandbox.server import start_sandbox, set_mode, get_mode
from orchestrator import run_audit

def run_system_integration_test():
    print("=" * 60)
    print("STARTING SYSTEM INTEGRATION TEST")
    print("=" * 60)

    # 1. Start sandbox server on port 5055 (isolated test port)
    sandbox_url = start_sandbox(port=5055)
    print(f"[1] Sandbox server started at: {sandbox_url}")
    time.sleep(0.5)

    # -------------------------------------------------------------
    # PHASE 1: TEST 'BEFORE' MODE (AI Crawl Blocked)
    # -------------------------------------------------------------
    print("\n[2] Testing BEFORE Mode (Simulating Cloudflare 403 on AI Bots)...")
    set_mode("before")
    assert get_mode() == "before"

    audit_before = run_audit(sandbox_url)
    
    score_before = audit_before["summary"]["score"]
    grade_before = audit_before["summary"]["grade"]
    status_before = audit_before["summary"]["status"]
    bot_matrix_before = audit_before["bot_matrix"]

    print(f"    --> Score: {score_before}/100 (Grade: {grade_before}) - Status: {status_before}")
    print(f"    --> Chrome Browser Status: {bot_matrix_before['browser_chrome']['status']}")
    print(f"    --> GPTBot Status: {bot_matrix_before['gpt_bot']['status']} (Blocked: {bot_matrix_before['gpt_bot']['blocked']})")
    print(f"    --> ClaudeBot Status: {bot_matrix_before['claude_bot']['status']} (Blocked: {bot_matrix_before['claude_bot']['blocked']})")

    # Assertions for BEFORE mode
    assert bot_matrix_before["browser_chrome"]["status"] == 200, "Browser should get 200 OK"
    assert bot_matrix_before["gpt_bot"]["status"] == 403, "GPTBot should be blocked with 403"
    assert bot_matrix_before["claude_bot"]["status"] == 403, "ClaudeBot should be blocked with 403"
    assert score_before < 50, f"Expected low score in BEFORE mode, got {score_before}"
    assert grade_before == "F", f"Expected Grade F, got {grade_before}"
    assert len(audit_before["scoring"]["penalties"]) > 0, "Penalties should be recorded"
    print("    [PASS] Phase 1 (BEFORE mode) passed all assertions!")

    # -------------------------------------------------------------
    # PHASE 2: TEST 'AFTER' MODE (AI Optimized 200 OK)
    # -------------------------------------------------------------
    print("\n[3] Testing AFTER Mode (Simulating WAF bypass / AI Optimized)...")
    set_mode("after")
    assert get_mode() == "after"

    audit_after = run_audit(sandbox_url)

    score_after = audit_after["summary"]["score"]
    grade_after = audit_after["summary"]["grade"]
    status_after = audit_after["summary"]["status"]
    bot_matrix_after = audit_after["bot_matrix"]

    print(f"    --> Score: {score_after}/100 (Grade: {grade_after}) - Status: {status_after}")
    print(f"    --> Chrome Browser Status: {bot_matrix_after['browser_chrome']['status']}")
    print(f"    --> GPTBot Status: {bot_matrix_after['gpt_bot']['status']} (Blocked: {bot_matrix_after['gpt_bot']['blocked']})")
    print(f"    --> ClaudeBot Status: {bot_matrix_after['claude_bot']['status']} (Blocked: {bot_matrix_after['claude_bot']['blocked']})")

    # Assertions for AFTER mode
    assert bot_matrix_after["browser_chrome"]["status"] == 200, "Browser should get 200 OK"
    assert bot_matrix_after["gpt_bot"]["status"] == 200, "GPTBot should get 200 OK in AFTER mode"
    assert bot_matrix_after["claude_bot"]["status"] == 200, "ClaudeBot should get 200 OK in AFTER mode"
    assert score_after >= 90, f"Expected Grade A score in AFTER mode, got {score_after}"
    assert grade_after == "A", f"Expected Grade A, got {grade_after}"
    print("    [PASS] Phase 2 (AFTER mode) passed all assertions!")

    # -------------------------------------------------------------
    # PHASE 3: CONTRACT INTEGRITY VERIFICATION FOR K (FRONTEND)
    # -------------------------------------------------------------
    print("\n[4] Verifying Frontend Data Contract for K...")
    required_keys = ["url", "timestamp", "summary", "scoring", "bot_matrix", "robots_txt", "ai_recommendations", "status"]
    for key in required_keys:
        assert key in audit_after, f"Missing contract key '{key}' for K"

    assert "score" in audit_after["summary"]
    assert "grade" in audit_after["summary"]
    assert "status" in audit_after["summary"]
    assert "color" in audit_after["summary"]
    assert "penalties" in audit_after["scoring"]
    assert "root_cause" in audit_after["ai_recommendations"]
    assert "cloudflare_waf_rule" in audit_after["ai_recommendations"]
    assert "robots_txt_fix" in audit_after["ai_recommendations"]

    print("    [PASS] Data contract is 100% complete and compliant!")

    print("\n" + "=" * 60)
    print("ALL INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    run_system_integration_test()
