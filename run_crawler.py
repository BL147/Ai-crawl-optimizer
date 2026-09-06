#!/usr/bin/env python3
"""CLI utility to run the AI Crawl Optimizer crawler on any website."""

import argparse
import asyncio
import json
import sys
from typing import Any, Dict

from crawler import (
    crawl_url,
    crawl_all_personas,
    crawl_with_baseline,
    list_personas,
)


def print_summary(res: Dict[str, Any]) -> None:
    """Pretty print an audit result to terminal."""
    target = res.get("target_url")
    persona = res.get("persona")
    success = res.get("success")
    error = res.get("error")
    http = res.get("http", {})
    robots = res.get("robots_txt", {})
    page = res.get("page", {})
    detection = res.get("detection", {})

    print("\n" + "=" * 60)
    print(f"  AI CRAWL OPTIMIZER - AUDIT REPORT")
    print("=" * 60)
    print(f"Target URL : {target}")
    print(f"Persona    : {persona}")
    print(f"Timestamp  : {res.get('timestamp')}")
    print(f"Success    : {'YES' if success else 'NO'}")
    if error:
        print(f"Error      : {error}")

    print("\n[ROBOTS.TXT]")
    print(f"  Exists       : {robots.get('exists')}")
    print(f"  URL          : {robots.get('url')}")
    print(f"  Allowed      : {'ALLOWED' if robots.get('is_allowed') else 'DISALLOWED'}")
    if robots.get("matching_rule"):
        print(f"  Rule         : {robots.get('matching_rule')}")
    if robots.get("crawl_delay"):
        print(f"  Crawl-Delay  : {robots.get('crawl_delay')}s")
    if robots.get("sitemaps"):
        print(f"  Sitemaps     : {', '.join(robots.get('sitemaps'))}")
    if robots.get("ai_specific_rules"):
        print(f"  AI Directives: {list(robots.get('ai_specific_rules').keys())}")

    print("\n[HTTP OBSERVATIONS]")
    print(f"  Status Code  : {http.get('status_code')}")
    print(f"  Final URL    : {http.get('final_url')}")
    print(f"  Redirects    : {http.get('redirect_count')}")
    print(f"  Latency      : {http.get('response_time_ms')} ms")
    if http.get("server"):
        print(f"  Server       : {http.get('server')}")
    if http.get("x_robots_tag"):
        print(f"  X-Robots-Tag : {http.get('x_robots_tag')}")

    print("\n[PAGE OBSERVATIONS]")
    print(f"  Title        : {page.get('title')}")
    print(f"  Text Length  : {page.get('text_length')} characters")
    if page.get("snippet"):
        snippet_preview = page.get("snippet")[:160].replace("\n", " ")
        print(f"  Snippet      : \"{snippet_preview}...\"")

    evidence = detection.get("evidence", {})
    inference = detection.get("inference", {})

    print("\n[OBSERVED EVIDENCE]")
    if evidence.get("status_code"):
        print(f"  Status Code      : {evidence.get('status_code')}")
    if evidence.get("matched_headers"):
        print(f"  Matched Headers  : {', '.join(evidence.get('matched_headers'))}")
    if evidence.get("dom_signals"):
        print(f"  DOM Signals      : {', '.join(evidence.get('dom_signals'))}")
    if evidence.get("matched_keywords"):
        print(f"  Matched Keywords : {', '.join(evidence.get('matched_keywords'))}")
    if not any([evidence.get("matched_headers"), evidence.get("dom_signals"), evidence.get("matched_keywords")]):
        print("  None (No anti-bot or challenge signatures detected)")

    print("\n[INFERRED CONCLUSION]")
    verdict = inference.get("verdict", "ACCESSIBLE")
    mechanism = inference.get("mechanism", "NONE")
    if hasattr(mechanism, "value"):
        mechanism = mechanism.value
    confidence = inference.get("confidence", 0.0)
    summary = inference.get("summary", "")

    print(f"  Verdict          : {verdict}")
    print(f"  Mechanism        : {mechanism}")
    print(f"  Confidence       : {round(confidence * 100, 1)}%")
    if summary:
        print(f"  Summary          : {summary}")
    print("=" * 60 + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI Crawl Optimizer - CLI Crawler")
    parser.add_argument("url", nargs="?", help="Target URL to crawl")
    parser.add_argument(
        "--persona",
        "-p",
        default="gptbot",
        help="Persona to simulate (e.g. gptbot, claudebot, perplexitybot, bytespider, standard_browser)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Audit across all standard AI crawler personas",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Compare AI persona against standard desktop browser baseline",
    )
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="List all supported personas and exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Path to save result JSON",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Timeout in seconds for page navigation",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode (UI visible)",
    )

    args = parser.parse_args()

    if args.list_personas:
        personas = list_personas()
        print(json.dumps(personas, indent=2))
        return

    if not args.url:
        parser.print_help()
        sys.exit(1)

    url = args.url
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headless = not args.headful

    if args.all:
        results = await crawl_all_personas(url, headless=headless, timeout_seconds=args.timeout)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                print_summary(r)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output}")
        return

    if args.baseline:
        result = await crawl_with_baseline(
            url, persona=args.persona, headless=headless, timeout_seconds=args.timeout
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\n>>> TARGET AI PERSONA AUDIT:")
            print_summary(result["target_persona"])
            print(">>> BASELINE DESKTOP BROWSER AUDIT:")
            print_summary(result["baseline_browser"])
            print(
                f"Selective AI Block Detected: {'YES (AI bot discriminated)' if result['selective_ai_block_detected'] else 'NO (Consistent behavior)'}"
            )
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Results saved to {args.output}")
        return

    result = await crawl_url(
        url, persona=args.persona, headless=headless, timeout_seconds=args.timeout
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_summary(result)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
