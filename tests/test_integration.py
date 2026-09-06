"""Integration tests for RemediationEngine with actual crawler result contracts.

Verifies:
1. Real/representative crawler results pass into RemediationEngine.
2. RemediationEngine returns the predictable output contract with all required keys:
   problem, evidence, why_it_affects_ai_crawling, recommended_fix, code_or_config, validation_steps.
3. Actual crawler evidence directly reaches remediation logic and suggestions.
4. INCONCLUSIVE remains uncertain.
5. HTTP_FORBIDDEN without mechanism evidence does not claim AI crawler blocking, Cloudflare, WAF, or CAPTCHA.
6. Crawl with baseline comparison format (target_persona wrapper) is supported.
7. Pydantic-like objects with .to_dict() or .model_dump() are fully compatible.
"""

import unittest
from remediation import RemediationEngine, generate_remediation


class MockPydanticCrawlResult:
    """Simulates Anshul's Pydantic CrawlResult model."""
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self) -> dict:
        return self._data

    def model_dump(self, mode: str = "json") -> dict:
        return self._data


class TestCrawlerRemediationIntegration(unittest.TestCase):

    def setUp(self):
        self.engine = RemediationEngine()

    def test_real_crawler_result_structure_and_required_keys(self):
        """Verify real crawler result structure yields all required keys in the output contract."""
        # Exact schema produced by crawler.models.CrawlResult.to_dict()
        real_crawl_result = {
            "target_url": "https://example.com/docs/intro",
            "persona": "gptbot",
            "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
            "timestamp": "2026-09-06T12:00:00Z",
            "success": True,
            "error": None,
            "robots_txt": {
                "exists": True,
                "url": "https://example.com/robots.txt",
                "status_code": 200,
                "is_allowed": False,
                "matching_rule": "Disallow: /docs/",
                "crawl_delay": 5.0,
                "sitemaps": ["https://example.com/sitemap.xml"],
                "ai_specific_rules": {
                    "gptbot": {"defined": True, "rules_count": 1, "crawl_delay": 5.0}
                },
                "raw_content": "User-agent: GPTBot\nDisallow: /docs/\nCrawl-delay: 5\n",
            },
            "http": {
                "status_code": 200,
                "final_url": "https://example.com/docs/intro",
                "redirect_count": 0,
                "redirects": [],
                "headers": {"server": "nginx/1.24.0", "content-type": "text/html; charset=utf-8"},
                "content_type": "text/html; charset=utf-8",
                "response_time_ms": 145.2,
                "server": "nginx/1.24.0",
                "x_robots_tag": None,
            },
            "page": {
                "title": "Introduction | Documentation",
                "meta_tags": {"viewport": "width=device-width, initial-scale=1.0"},
                "text_length": 3400,
                "snippet": "Welcome to our API documentation...",
                "has_javascript_requirement": False,
            },
            "detection": {
                "evidence": {
                    "status_code": 200,
                    "matched_headers": [],
                    "dom_signals": [],
                    "matched_keywords": [],
                    "page_title": "Introduction | Documentation",
                    "snippet_preview": "Welcome to our API documentation...",
                },
                "inference": {
                    "verdict": "ACCESSIBLE",
                    "mechanism": "NONE",
                    "confidence": 0.0,
                    "summary": "No access restrictions detected.",
                },
                "is_blocked": False,
                "block_type": "NONE",
                "confidence": 0.0,
                "signals": ["HTTP status code: 200"],
            },
        }

        result = self.engine.remediate(real_crawl_result)

        # 1. Output structure contains AT LEAST the required contract fields
        self.assertIn("problem", result)
        self.assertIn("evidence", result)
        self.assertIn("why_it_affects_ai_crawling", result)
        self.assertIn("recommended_fix", result)
        self.assertIn("code_or_config", result)
        self.assertIn("validation_steps", result)

        # 2. Backwards-compatibility aliases preserved
        self.assertIn("problem_detected", result)
        self.assertIn("code_or_configuration_change", result)
        self.assertIn("before_after_example", result)
        self.assertIn("uncertainty", result)

        # 3. Grounded in actual crawler evidence
        self.assertIn("Disallow", result["problem"])
        self.assertTrue(any("Disallow: /docs/" in e for e in result["evidence"]))
        self.assertIn("user-agent: gptbot", result["code_or_config"].lower())
        self.assertIn("Allow: /", result["code_or_config"])

    def test_crawler_evidence_reaches_remediation_waf(self):
        """Verify observed WAF evidence reaches the remediation output without hallucinating."""
        crawl_result = {
            "target_url": "https://example.com/protected-page",
            "persona": "claudebot",
            "user_agent": "ClaudeBot/1.0",
            "timestamp": "2026-09-06T12:00:00Z",
            "success": True,
            "error": None,
            "robots_txt": {"exists": True, "is_allowed": True},
            "http": {
                "status_code": 403,
                "server": "cloudflare",
                "headers": {"server": "cloudflare", "cf-ray": "8c4599a1bc23-SJC"},
            },
            "page": {
                "title": "Just a moment...",
                "snippet": "Checking your browser before accessing...",
            },
            "detection": {
                "evidence": {
                    "status_code": 403,
                    "matched_headers": ["cf-ray: 8c4599a1bc23-SJC", "server: cloudflare"],
                    "dom_signals": [".cf-turnstile", "#challenge-form"],
                    "matched_keywords": ["just a moment..."],
                },
                "inference": {
                    "verdict": "CHALLENGED",
                    "mechanism": "CLOUDFLARE_CHALLENGE",
                    "confidence": 0.96,
                    "summary": "Cloudflare interactive challenge intercepted the crawler request.",
                },
                "is_blocked": True,
            },
        }

        result = generate_remediation(crawl_result)

        # Exact evidence reached remediation
        self.assertIn("CLOUDFLARE_CHALLENGE", result["problem"])
        self.assertTrue(any("cf-ray" in e for e in result["evidence"]))
        self.assertTrue(any(".cf-turnstile" in e for e in result["evidence"]))
        self.assertIn("Cloudflare", result["recommended_fix"])
        self.assertIn("cf.client.bot", result["code_or_config"])

    def test_inconclusive_http_403_preserves_uncertainty(self):
        """
        Verify INCONCLUSIVE + HTTP 403 preserves uncertainty and does NOT
        claim AI crawler blocking, Cloudflare, DataDome, PerimeterX, or AWS WAF.
        """
        inconclusive_crawl = {
            "target_url": "https://example.com/admin/login",
            "persona": "gptbot",
            "user_agent": "GPTBot/1.2",
            "timestamp": "2026-09-06T12:00:00Z",
            "success": True,
            "error": None,
            "robots_txt": {"exists": False, "is_allowed": True},
            "http": {
                "status_code": 403,
                "server": "Apache/2.4.52",
                "headers": {"server": "Apache/2.4.52"},
            },
            "page": {
                "title": "403 Forbidden",
                "snippet": "You don't have permission to access this resource.",
            },
            "detection": {
                "evidence": {
                    "status_code": 403,
                    "matched_headers": [],
                    "dom_signals": [],
                    "matched_keywords": ["403 Forbidden"],
                    "page_title": "403 Forbidden",
                },
                "inference": {
                    "verdict": "INCONCLUSIVE",
                    "mechanism": "HTTP_FORBIDDEN",
                    "confidence": 0.35,
                    "summary": "Server returned HTTP 403 Forbidden without conclusive anti-bot challenge evidence.",
                },
                "is_blocked": False,
            },
        }

        result = self.engine.remediate(inconclusive_crawl)

        why = result["why_it_affects_ai_crawling"].lower()
        problem = result["problem"].lower()
        uncertainty = result["uncertainty"].lower()

        # 1. Uncertainty preserved
        self.assertTrue("uncertain" in why or "uncertain" in uncertainty)
        self.assertIn("cannot confirm that the website specifically blocks ai crawlers", why)

        # 2. No false claim of AI crawler blocking
        self.assertNotIn("this website blocks ai crawlers", why)
        self.assertNotIn("blocks ai crawlers", problem)

        # 3. No invented firewalls
        self.assertNotIn("cloudflare", why)
        self.assertNotIn("cloudflare", problem)
        self.assertNotIn("datadome", why)
        self.assertNotIn("datadome", problem)
        self.assertNotIn("perimeterx", why)
        self.assertNotIn("perimeterx", problem)
        self.assertNotIn("aws", why)
        self.assertNotIn("captcha", why)

        # 4. Diagnostic guidance provided
        self.assertTrue(any("log" in step.lower() for step in result["validation_steps"]))
        self.assertTrue(any("baseline" in step.lower() for step in result["validation_steps"]))

    def test_crawl_with_baseline_dict_compatibility(self):
        """Verify baseline comparison format from crawl_with_baseline is automatically unwrapped."""
        baseline_result = {
            "url": "https://example.com/item",
            "selective_ai_block_detected": True,
            "target_persona": {
                "target_url": "https://example.com/item",
                "persona": "claudebot",
                "user_agent": "ClaudeBot/1.0",
                "robots_txt": {
                    "exists": True,
                    "is_allowed": False,
                    "matching_rule": "Disallow: /item",
                },
                "http": {"status_code": 200},
                "page": {"title": "Item Page"},
                "detection": {
                    "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"},
                    "is_blocked": False,
                },
            },
            "baseline_browser": {
                "target_url": "https://example.com/item",
                "persona": "standard_browser",
                "robots_txt": {"is_allowed": True},
                "http": {"status_code": 200},
            },
        }

        result = self.engine.remediate(baseline_result)

        self.assertIn("problem", result)
        self.assertIn("Disallow", result["problem"])
        self.assertIn("user-agent: claudebot", result["code_or_config"].lower())

    def test_pydantic_model_compatibility(self):
        """Verify RemediationEngine can directly consume CrawlResult Pydantic instances."""
        sample_dict = {
            "target_url": "https://example.com/page",
            "persona": "perplexitybot",
            "user_agent": "PerplexityBot/1.0",
            "robots_txt": {"exists": True, "is_allowed": True},
            "http": {
                "status_code": 200,
                "x_robots_tag": "noindex, nofollow",
                "headers": {"x-robots-tag": "noindex, nofollow"},
            },
            "page": {"title": "Sample"},
            "detection": {
                "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"},
                "is_blocked": False,
            },
        }

        mock_model = MockPydanticCrawlResult(sample_dict)
        result = self.engine.remediate(mock_model)

        self.assertIn("problem", result)
        self.assertIn("X-Robots-Tag", result["problem"])
        self.assertIn("noindex", result["problem"].lower())


    def test_actual_crawler_sync_live_execution(self):
        """
        Checkpoint 2 Live Integration:
        Executes Anshul's real crawl_sync(...) function with an actual test target,
        passes the real CrawlResult output directly into generate_remediation(...),
        and verifies the resulting remediation structure.
        """
        from crawler import crawl_sync

        # Safe, stable target containing rendered title, meta tags, and body text
        target_url = (
            "data:text/html,<html><head><title>Integration Test Page</title>"
            "<meta name='robots' content='index, follow'></head>"
            "<body><h1>AI Crawl Optimizer Test</h1>"
            "<p>Accessible content for automated AI crawler verification.</p></body></html>"
        )

        # 1. Execute Anshul's actual crawler
        real_crawl_result = crawl_sync(target_url, persona="gptbot")

        # 2. Verify real crawler output properties
        self.assertIsInstance(real_crawl_result, dict)
        self.assertEqual(real_crawl_result.get("target_url"), target_url)
        self.assertEqual(real_crawl_result.get("persona"), "gptbot")
        self.assertIn("detection", real_crawl_result)
        self.assertIn("inference", real_crawl_result["detection"])
        self.assertEqual(real_crawl_result["detection"]["inference"].get("verdict"), "ACCESSIBLE")

        # 3. Pass REAL crawler output directly into generate_remediation
        remediation_result = generate_remediation(real_crawl_result)

        # 4. Verify predictable output structure with all required fields
        self.assertIsInstance(remediation_result, dict)
        self.assertIn("problem", remediation_result)
        self.assertIn("evidence", remediation_result)
        self.assertIn("why_it_affects_ai_crawling", remediation_result)
        self.assertIn("recommended_fix", remediation_result)
        self.assertIn("code_or_config", remediation_result)
        self.assertIn("validation_steps", remediation_result)

        # 5. Verify backwards-compatible alias fields
        self.assertIn("problem_detected", remediation_result)
        self.assertIn("code_or_configuration_change", remediation_result)
        self.assertIn("before_after_example", remediation_result)
        self.assertIn("uncertainty", remediation_result)

        # 6. Verify non-empty meaningful content
        self.assertTrue(len(remediation_result["problem"]) > 0)
        self.assertTrue(len(remediation_result["evidence"]) > 0)
        self.assertTrue(len(remediation_result["recommended_fix"]) > 0)
        self.assertTrue(len(remediation_result["validation_steps"]) > 0)

        # 7. Grounding verification: clean accessible target must not invent WAF / blocks
        self.assertNotIn("cloudflare", remediation_result["problem"].lower())
        self.assertNotIn("blocked", remediation_result["problem"].lower())


if __name__ == "__main__":
    unittest.main()
