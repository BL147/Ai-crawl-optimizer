"""
shlok.py - System Integration Entrypoint
Author: Shlok (System Integrator)

Re-exports core integrator modules:
- run_audit: Primary function for K (Frontend)
- ScoringEngine: Mathematical scoring breakdown
- start_sandbox / set_mode: Controlled demo server
"""

import sys
import json
from orchestrator import run_audit
from scoring import ScoringEngine, calculate_score
from sandbox.server import start_sandbox, set_mode, get_mode

__all__ = ["run_audit", "ScoringEngine", "calculate_score", "start_sandbox", "set_mode", "get_mode"]

if __name__ == "__main__":
    mode_arg = None
    target = "https://example.com"

    for arg in sys.argv[1:]:
        if arg in ["--before", "-b"]:
            set_mode("before")
            mode_arg = "before"
        elif arg in ["--after", "-a"]:
            set_mode("after")
            mode_arg = "after"
        elif not arg.startswith("-"):
            target = arg

    if "5050" in target or "sandbox" in target.lower():
        start_sandbox(port=5050)
        target = "http://127.0.0.1:5050"
        print(f"[*] Started local Sandbox Server (Mode: {get_mode().upper()})")

    print(f"[*] Running AI Crawl Audit on: {target}")
    result = run_audit(target)
    print("\n" + "="*55)
    print(f"AUDIT TARGET: {result['url']}")
    print(f"SCORE: {result['summary']['score']}/100 | GRADE: {result['summary']['grade']} | STATUS: {result['summary']['status']}")
    print("="*55)
    print(f"\nSummary: {result['summary']['text']}")
    
    print("\n[BOT EMULATION MATRIX]")
    for bot, info in result["bot_matrix"].items():
        block_str = "[BLOCKED]" if info.get("blocked") else "[OK]"
        print(f"  - {bot:15}: Status {info.get('status')} {block_str} ({info.get('latency_ms')}ms)")

    print("\n[PENALTIES DEDUCTED]")
    if not result["scoring"]["penalties"]:
        print("  - None! 0 deductions recorded.")
    else:
        for p in result["scoring"]["penalties"]:
            print(f"  - ({p['penalty']} pts) {p['factor']}: {p['detail']}")

    print("\n[AI RECOMMENDATIONS]")
    print(f"Root Cause: {result['ai_recommendations']['root_cause']}")
    print("\nAction Items:")
    for action in result['ai_recommendations']['action_items']:
        print(f"  * {action}")

    print("\nCloudflare WAF Bypass Rule:")
    print(f"  {result['ai_recommendations']['cloudflare_waf_rule']}")

