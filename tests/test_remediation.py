"""Tests for the AI Crawl Optimizer Remediation Engine.

Verifies:
1. robots.txt disallow issue
2. X-Robots-Tag HTTP header issue
3. HTML <meta name="robots"> issue
4. Detected WAF/challenge mechanism (Cloudflare Challenge & AWS WAF)
5. INCONCLUSIVE + HTTP 403 Forbidden (verifying NO false claims of AI blocking, Cloudflare, WAF, or CAPTCHA)
6. Resilience against missing fields and malformed dicts
"""

import unittest
from remediation import generate_remediation, normalize_crawler_result, IssueType


class TestRemediationEngine(unittest.TestCase):

    def test_robots_txt_disallow_issue(self):
        """1. robots.txt issue: Must identify rule, explain impact, and provide before/after."""
        crawler_result = {
            "target_url": "https://example.com/blog/article",
            "persona": "gptbot",
            "user_agent": "Mozilla/5.0 ... GPTBot/1.2",
            "robots_txt": {
                "exists": True,
                "url": "https://example.com/robots.txt",
                "status_code": 200,
                "is_allowed": False,
                "matching_rule": "Disallow: /blog/",
                "crawl_delay": 10.0,
                "raw_content": "User-agent: GPTBot\nDisallow: /blog/\nCrawl-delay: 10\n",
            },
            "http": {
                "status_code": 200,
                "headers": {"server": "nginx"},
            },
            "page": {
                "title": "Blog Article",
                "meta_tags": {},
            },
            "detection": {
                "evidence": {"status_code": 200},
                "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"},
                "is_blocked": False,
            },
        }

        remediation = generate_remediation(crawler_result)

        # Output schema assertions
        self.assertIn("problem_detected", remediation)
        self.assertIn("evidence", remediation)
        self.assertIn("why_it_affects_ai_crawling", remediation)
        self.assertIn("recommended_fix", remediation)
        self.assertIn("code_or_configuration_change", remediation)
        self.assertIn("before_after_example", remediation)
        self.assertIn("validation_steps", remediation)
        self.assertIn("uncertainty", remediation)

        # Content assertions
        self.assertIn("Disallow", remediation["problem_detected"])
        self.assertIn("Disallow: /blog/", str(remediation["evidence"]))
        self.assertIn("user-agent: gptbot", remediation["code_or_configuration_change"].lower())
        self.assertIn("Allow: /", remediation["code_or_configuration_change"])
        self.assertIn("before", remediation["before_after_example"])
        self.assertIn("after", remediation["before_after_example"])
        self.assertTrue(len(remediation["validation_steps"]) > 0)

    def test_x_robots_tag_issue(self):
        """2. X-Robots-Tag issue: Must identify header directive and recommend web server fix."""
        crawler_result = {
            "target_url": "https://example.com/products/item-1",
            "persona": "claudebot",
            "robots_txt": {
                "exists": True,
                "is_allowed": True,
                "matching_rule": "Allow: /",
            },
            "http": {
                "status_code": 200,
                "server": "nginx",
                "x_robots_tag": "noindex, nofollow",
                "headers": {
                    "server": "nginx",
                    "x-robots-tag": "noindex, nofollow",
                },
            },
            "page": {
                "title": "Product Page",
                "meta_tags": {},
            },
            "detection": {
                "evidence": {"status_code": 200},
                "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"},
                "is_blocked": False,
            },
        }

        remediation = generate_remediation(crawler_result)

        self.assertIn("X-Robots-Tag", remediation["problem_detected"])
        self.assertIn("noindex", remediation["problem_detected"].lower())
        self.assertTrue(any("x-robots-tag" in e.lower() for e in remediation["evidence"]))
        self.assertIn("header", remediation["why_it_affects_ai_crawling"].lower())
        self.assertIn("add_header", remediation["code_or_configuration_change"])
        self.assertIn("noindex", remediation["before_after_example"]["before"])

    def test_meta_robots_issue(self):
        """3. HTML meta robots issue: Must identify meta tag in DOM and recommend HTML/CMS fix."""
        crawler_result = {
            "target_url": "https://example.com/news/story",
            "persona": "perplexitybot",
            "robots_txt": {
                "exists": True,
                "is_allowed": True,
            },
            "http": {
                "status_code": 200,
                "headers": {"server": "Apache"},
            },
            "page": {
                "title": "Breaking News",
                "meta_tags": {
                    "robots": "noindex, noarchive",
                    "description": "News summary",
                },
            },
            "detection": {
                "evidence": {"status_code": 200},
                "inference": {"verdict": "ACCESSIBLE", "mechanism": "NONE"},
                "is_blocked": False,
            },
        }

        remediation = generate_remediation(crawler_result)

        self.assertIn("meta", remediation["problem_detected"].lower())
        self.assertIn("robots", remediation["problem_detected"].lower())
        self.assertTrue(any("meta" in e.lower() for e in remediation["evidence"]))
        self.assertIn("<meta", remediation["code_or_configuration_change"])
        self.assertIn("index, follow", remediation["code_or_configuration_change"])
        self.assertIn("noindex", remediation["before_after_example"]["before"])
        self.assertIn("index, follow", remediation["before_after_example"]["after"])

    def test_waf_challenge_cloudflare(self):
        """4. Detected WAF/challenge mechanism: Grounded in Cloudflare Turnstile signals."""
        crawler_result = {
            "target_url": "https://example.com/protected",
            "persona": "gptbot",
            "robots_txt": {"exists": True, "is_allowed": True},
            "http": {
                "status_code": 403,
                "server": "cloudflare",
                "headers": {
                    "server": "cloudflare",
                    "cf-ray": "8c4599a1bc23-SJC",
                },
            },
            "page": {
                "title": "Just a moment...",
                "snippet": "Checking your browser before accessing. Enable JavaScript.",
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

        remediation = generate_remediation(crawler_result)

        self.assertIn("CLOUDFLARE_CHALLENGE", remediation["problem_detected"])
        self.assertTrue(any("cf-ray" in e for e in remediation["evidence"]))
        self.assertTrue(any(".cf-turnstile" in e for e in remediation["evidence"]))
        self.assertIn("Cloudflare", remediation["recommended_fix"])
        self.assertIn("cf.client.bot", remediation["code_or_configuration_change"])
        self.assertIn("Skip", remediation["code_or_configuration_change"])

    def test_waf_challenge_aws(self):
        """4b. Detected WAF/challenge mechanism: Grounded in AWS WAF signals."""
        crawler_result = {
            "target_url": "https://example.com/api/data",
            "persona": "claudebot",
            "robots_txt": {"exists": True, "is_allowed": True},
            "http": {
                "status_code": 405,
                "headers": {"x-amzn-waf-action": "block"},
            },
            "page": {"title": "405 Not Allowed"},
            "detection": {
                "evidence": {
                    "status_code": 405,
                    "matched_headers": ["x-amzn-waf header"],
                    "dom_signals": [".aws-waf-captcha"],
                    "matched_keywords": ["request blocked by aws waf"],
                },
                "inference": {
                    "verdict": "CHALLENGED",
                    "mechanism": "AWS_WAF",
                    "confidence": 0.92,
                    "summary": "AWS WAF access challenge or block detected.",
                },
                "is_blocked": True,
            },
        }

        remediation = generate_remediation(crawler_result)

        self.assertIn("AWS_WAF", remediation["problem_detected"])
        self.assertTrue(any("aws" in e.lower() for e in remediation["evidence"]))
        self.assertIn("AWS WAF", remediation["recommended_fix"])
        self.assertIn("Web ACL", remediation["code_or_configuration_change"])

    def test_inconclusive_http_403_critical_rule(self):
        """
        5. CRITICAL INCONCLUSIVE RULE:
        Standalone HTTP 403 with INCONCLUSIVE verdict MUST state uncertainty.
        MUST NOT claim:
        - "This website blocks AI crawlers."
        - "Cloudflare is blocking the crawler."
        MUST NOT invent WAF, Cloudflare, DataDome, PerimeterX, CAPTCHA, or Bot detection.
        """
        crawler_result = {
            "target_url": "https://example.com/private-folder/doc",
            "persona": "gptbot",
            "robots_txt": {
                "exists": False,
                "is_allowed": True,
            },
            "http": {
                "status_code": 403,
                "server": "Apache/2.4.41",
                "headers": {"server": "Apache/2.4.41"},
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
                    "matched_keywords": [],
                    "page_title": "403 Forbidden",
                },
                "inference": {
                    "verdict": "INCONCLUSIVE",
                    "mechanism": "HTTP_FORBIDDEN",
                    "confidence": 0.35,
                    "summary": "Server returned HTTP 403 Forbidden. Access is restricted, but AI-specific blocking attribution is inconclusive.",
                },
                "is_blocked": False,
            },
        }

        remediation = generate_remediation(crawler_result)

        why = remediation["why_it_affects_ai_crawling"].lower()
        problem = remediation["problem_detected"].lower()
        fix = remediation["recommended_fix"].lower()

        # Strict assertion 1: Must explain that cause is uncertain and cannot confirm AI crawler blocking
        self.assertIn("uncertain", why + remediation["uncertainty"].lower())
        self.assertIn("cannot confirm that the website specifically blocks ai crawlers", why)

        # Strict assertion 2: MUST NOT falsely claim AI crawler blocking
        self.assertNotIn("this website blocks ai crawlers", why)
        self.assertNotIn("specifically targets ai crawlers", why)

        # Strict assertion 3: MUST NOT invent Cloudflare, WAF, DataDome, PerimeterX, or CAPTCHA
        self.assertNotIn("cloudflare", why)
        self.assertNotIn("cloudflare", problem)
        self.assertNotIn("datadome", why)
        self.assertNotIn("datadome", problem)
        self.assertNotIn("perimeterx", why)
        self.assertNotIn("perimeterx", problem)
        self.assertNotIn("captcha", why)
        self.assertNotIn("waf", problem)

        # Strict assertion 4: Diagnostic steps provided
        self.assertTrue(any("log" in step.lower() for step in remediation["validation_steps"]))
        self.assertTrue(any("baseline" in step.lower() for step in remediation["validation_steps"]))

    def test_missing_and_empty_fields_resilience(self):
        """6. Robustness test: Handle None, missing keys, empty dictionary gracefully."""
        # Empty dictionary
        res_empty = generate_remediation({})
        self.assertIsInstance(res_empty, dict)
        self.assertIn("problem_detected", res_empty)

        # None input
        res_none = generate_remediation(None)
        self.assertIsInstance(res_none, dict)
        self.assertIn("problem_detected", res_none)

        # Missing nested keys
        partial = {
            "target_url": "https://example.com",
            "robots_txt": None,
            "http": {"status_code": None},
            "detection": {},
        }
        res_partial = generate_remediation(partial)
        self.assertIsInstance(res_partial, dict)
        self.assertIn("problem_detected", res_partial)


if __name__ == "__main__":
    unittest.main()
