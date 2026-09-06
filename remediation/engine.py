"""AI Remediation Engine orchestrating Gemini AI synthesis and grounded fallback."""

import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from remediation.models import RemediationResult
from remediation.normalizer import NormalizedAudit, normalize_crawler_result, IssueType
from remediation.prompt_builder import SYSTEM_INSTRUCTION, build_gemini_prompt


class RemediationEngine:
    """
    Orchestrates AI-driven crawl remediation suggestions strictly grounded in
    actual crawler evidence.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        timeout_seconds: float = 12.0,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def remediate(self, crawler_result: Any) -> Dict[str, Any]:
        """
        Generate developer-friendly, strictly grounded remediation from crawler result.
        Returns a dictionary adhering to the project schema.
        """
        audit = normalize_crawler_result(crawler_result)

        # Attempt Gemini AI generation if API key is present
        if self.api_key:
            ai_result = self._call_gemini_api(audit)
            if ai_result:
                return ai_result

        # Fallback to deterministic rule-based remediation engine
        return self._generate_rule_based_remediation(audit).to_dict()

    def _call_gemini_api(self, audit: NormalizedAudit) -> Optional[Dict[str, Any]]:
        """Attempt to call Gemini API via REST or official SDK, parsing structured JSON."""
        prompt = build_gemini_prompt(audit)

        # Try Google GenAI SDK if installed
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "system_instruction": SYSTEM_INSTRUCTION,
                    "response_mime_type": "application/json",
                },
            )
            if response and response.text:
                parsed = self._clean_and_parse_json(response.text)
                if parsed:
                    return self._validate_and_finalize_dict(parsed, audit, raw_response=response.text)
        except ImportError:
            pass
        except Exception:
            # Fall back to HTTP REST call
            pass

        # Try legacy google.generativeai if installed
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.api_key)
            g_model = legacy_genai.GenerativeModel(
                model_name=self.model,
                system_instruction=SYSTEM_INSTRUCTION,
                generation_config={"response_mime_type": "application/json"},
            )
            response = g_model.generate_content(prompt)
            if response and response.text:
                parsed = self._clean_and_parse_json(response.text)
                if parsed:
                    return self._validate_and_finalize_dict(parsed, audit, raw_response=response.text)
        except ImportError:
            pass
        except Exception:
            pass

        # Native HTTPS REST call using urllib (zero external dependencies required)
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status == 200:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "")
                            parsed = self._clean_and_parse_json(raw_text)
                            if parsed:
                                return self._validate_and_finalize_dict(parsed, audit, raw_response=raw_text)
        except urllib.error.HTTPError as he:
            try:
                he.read()
                he.close()
            except Exception:
                pass
        except Exception:
            # Fall back to deterministic grounded engine
            pass

        return None

    def _clean_and_parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Clean markdown wrapping and parse json safely."""
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return None

    def _validate_and_finalize_dict(
        self, parsed: Dict[str, Any], audit: NormalizedAudit, raw_response: str
    ) -> Dict[str, Any]:
        """Ensure all required keys exist and enforce the Critical Inconclusive Rule."""
        result = RemediationResult(
            problem_detected=str(parsed.get("problem_detected") or ""),
            evidence=parsed.get("evidence") if isinstance(parsed.get("evidence"), list) else audit.observed_facts,
            why_it_affects_ai_crawling=str(parsed.get("why_it_affects_ai_crawling") or ""),
            recommended_fix=str(parsed.get("recommended_fix") or ""),
            code_or_configuration_change=str(parsed.get("code_or_configuration_change") or ""),
            before_after_example=parsed.get("before_after_example") if isinstance(parsed.get("before_after_example"), dict) else {},
            validation_steps=parsed.get("validation_steps") if isinstance(parsed.get("validation_steps"), list) else [],
            uncertainty=str(parsed.get("uncertainty") or ""),
            observed_facts={"facts": audit.observed_facts, "inferences": audit.crawler_inferences},
            raw_model_response=raw_response,
        )

        # Enforce Critical Inconclusive Rule on Gemini output if triggered
        if audit.is_inconclusive_403:
            forbidden_phrases = [
                "blocks ai crawlers",
                "blocking ai crawlers",
                "cloudflare is blocking",
                "cloudflare waf",
                "datadome is blocking",
                "perimeterx is blocking",
            ]
            why_lower = result.why_it_affects_ai_crawling.lower()
            if any(p in why_lower for p in forbidden_phrases):
                # Sanitize response to guarantee strict compliance
                result.why_it_affects_ai_crawling = (
                    "The crawler received a 403 Forbidden response, but the available evidence does not "
                    "conclusively identify the blocking mechanism. Therefore, we cannot confirm that the "
                    "website specifically blocks AI crawlers."
                )
                result.uncertainty = (
                    "High uncertainty. Standalone HTTP 403 response without observed anti-bot challenge headers, "
                    "DOM signals, or keywords."
                )

        return result.to_dict()

    def _generate_rule_based_remediation(self, audit: NormalizedAudit) -> RemediationResult:
        """
        Deterministic, strictly grounded remediation generator ensuring 100% testability,
        exact adherence to grounding rules, and zero hallucinations.
        """
        persona_name = audit.persona or "AI Crawler"
        parsed_url = urlparse(audit.target_url) if audit.target_url else None
        domain = parsed_url.netloc if parsed_url and parsed_url.netloc else "yourdomain.com"

        # -------------------------------------------------------------
        # 1. Robots.txt Disallow Issue
        # -------------------------------------------------------------
        if audit.issue_type == IssueType.ROBOTS_TXT_DISALLOW:
            matching_rule = audit.robots_matching_rule or "Disallow: /"
            problem = f"Robots.txt Disallow rule blocks {persona_name} crawler access."
            evidence = [
                f"robots.txt location: {audit.robots_url or f'https://{domain}/robots.txt'}",
                f"Evaluation: is_allowed = False",
                f"Matching rule: '{matching_rule}'",
            ]
            if audit.robots_crawl_delay:
                evidence.append(f"Crawl delay directive: {audit.robots_crawl_delay}s")

            why = (
                f"Compliant AI crawlers (including {persona_name}) strictly adhere to RFC 9309 robots.txt standards. "
                f"When a Disallow directive matches the target URL path, the crawler terminates the request before fetching "
                f"page content, preventing the resource from appearing in generative search summaries."
            )
            fix = f"Update the robots.txt file to explicitly permit the {persona_name} user-agent, or allow the required path."
            code = (
                f"# robots.txt configuration\n"
                f"User-agent: {persona_name}\n"
                f"Allow: /\n\n"
                f"# Fallback standard crawlers\n"
                f"User-agent: *\n"
                f"Allow: /\n"
            )
            before_after = {
                "before": f"User-agent: {persona_name}\n{matching_rule}",
                "after": f"User-agent: {persona_name}\nAllow: /",
            }
            validation = [
                f"Deploy the updated robots.txt to https://{domain}/robots.txt.",
                f"Verify HTTP 200 response: curl -sI https://{domain}/robots.txt",
                f"Confirm rule: curl -s https://{domain}/robots.txt | grep -A 2 -i '{persona_name}'",
                f"Re-run AI Crawl Optimizer with persona '{audit.persona}' to verify is_allowed evaluates to True.",
            ]
            uncertainty = "None. Direct robots.txt directive observed."

        # -------------------------------------------------------------
        # 2. HTTP X-Robots-Tag Issue
        # -------------------------------------------------------------
        elif audit.issue_type == IssueType.X_ROBOTS_TAG_RESTRICTION:
            x_robots = audit.http_x_robots_tag or "noindex, nofollow"
            problem = f"HTTP response header X-Robots-Tag restricts indexing: '{x_robots}'."
            evidence = [f"HTTP header X-Robots-Tag: '{x_robots}'"]
            if audit.http_server:
                evidence.append(f"HTTP Server: '{audit.http_server}'")

            why = (
                f"The HTTP X-Robots-Tag header is sent by the web server in the response headers. "
                f"Directives such as '{x_robots}' instruct search and AI engines not to index or extract knowledge "
                f"from this URL, even if robots.txt permits crawling."
            )
            fix = "Update your web server configuration (Nginx, Apache, or CDN) to remove or relax the X-Robots-Tag header for AI crawlers."
            code = (
                f"# Nginx web server configuration (/etc/nginx/conf.d/default.conf)\n"
                f"# Remove static restrictive header:\n"
                f"# add_header X-Robots-Tag \"{x_robots}\";\n\n"
                f"# Or conditionally allow AI search engines:\n"
                f"map $http_user_agent $ai_robots_tag {{\n"
                f"    default \"all\";\n"
                f"    ~*(GPTBot|ClaudeBot|PerplexityBot) \"all\";\n"
                f"}}\n"
                f"add_header X-Robots-Tag $ai_robots_tag always;\n"
            )
            before_after = {
                "before": f'add_header X-Robots-Tag "{x_robots}";',
                "after": 'add_header X-Robots-Tag "all";',
            }
            validation = [
                f"Verify headers with curl: curl -sI -A '{audit.user_agent or 'GPTBot'}' https://{domain}/",
                f"Confirm the X-Robots-Tag header is no longer returning '{x_robots}'.",
                f"Re-test using the AI Crawl Optimizer to ensure clean accessibility.",
            ]
            uncertainty = "None. Direct HTTP response header observation."

        # -------------------------------------------------------------
        # 3. HTML Meta Robots Tag Issue
        # -------------------------------------------------------------
        elif audit.issue_type == IssueType.META_ROBOTS_RESTRICTION:
            meta_key = next((k for k in audit.meta_tags if any(b in k for b in ["robots", "googlebot", "gptbot", "claudebot"])), "robots")
            meta_val = audit.meta_tags.get(meta_key, "noindex, nofollow")

            problem = f"HTML <meta name='{meta_key}'> tag contains restrictive directive: '{meta_val}'."
            evidence = [f"HTML meta tag '{meta_key}': '{meta_val}'"]
            if audit.page_title:
                evidence.append(f"Page title: '{audit.page_title}'")

            why = (
                f"The HTML document contains a <meta name='{meta_key}' content='{meta_val}'> tag in the <head> section. "
                f"AI indexing pipelines parse HTML meta tags and respect 'noindex' or 'none' directives by excluding the "
                f"page from generative retrieval and citations."
            )
            fix = "Update your HTML template, layout file, or CMS SEO plugin to set the meta robots tag to 'index, follow'."
            code = (
                f"<!-- HTML <head> update -->\n"
                f"<meta name=\"robots\" content=\"index, follow\">\n"
                f"<meta name=\"googlebot\" content=\"index, follow\">\n"
                f"<meta name=\"gptbot\" content=\"index, follow\">\n"
            )
            before_after = {
                "before": f'<meta name="{meta_key}" content="{meta_val}">',
                "after": '<meta name="robots" content="index, follow">',
            }
            validation = [
                f"Inspect the rendered HTML <head> section in your browser or with curl: curl -sL https://{domain}/ | grep -i '<meta.*robots'",
                f"Confirm that '{meta_val}' is replaced with 'index, follow'.",
                f"Re-audit the page with AI Crawl Optimizer to confirm meta_tags reflects 'index, follow'.",
            ]
            uncertainty = "None. Direct DOM meta tag observation."

        # -------------------------------------------------------------
        # 4. Inconclusive HTTP 403 Forbidden Issue (CRITICAL RULE)
        # -------------------------------------------------------------
        elif audit.issue_type == IssueType.INCONCLUSIVE_HTTP_403:
            problem = "HTTP 403 Forbidden received without conclusive blocking attribution."
            evidence = ["HTTP Status Code: 403"]
            if audit.http_server:
                evidence.append(f"HTTP Server: '{audit.http_server}'")
            evidence.append("No specific WAF signatures, challenge widgets, or anti-bot headers were detected in the response.")

            # MUST adhere strictly to the Critical Inconclusive Rule
            why = (
                "The crawler received a 403 Forbidden response, but the available evidence does not conclusively "
                "identify the blocking mechanism. Therefore, we cannot confirm that the website specifically blocks "
                "AI crawlers. The 403 status may stem from generic server configuration, directory index restrictions, "
                "file system permissions, IP filtering, or basic authorization requirements."
            )
            fix = (
                "Investigate server access controls, reverse proxy configuration, and file permissions before assuming "
                "an anti-bot intervention. Run baseline diagnostics to determine if standard browsers are also restricted."
            )
            code = (
                "# Server Diagnostic & Remediation Checklist:\n"
                "# 1. Inspect web server error logs for denial reasons:\n"
                "#    Nginx:  tail -n 50 /var/log/nginx/error.log\n"
                "#    Apache: tail -n 50 /var/log/apache2/error.log\n"
                "# 2. Verify file and directory read permissions:\n"
                "#    chmod 755 /var/www/html && chmod 644 /var/www/html/index.html\n"
                "# 3. Check for IP or CIDR restrictions in web server configs\n"
                "# 4. Compare with standard browser baseline using crawl_with_baseline()\n"
            )
            before_after = {
                "before": "Uncertain access restriction returning HTTP 403 Forbidden",
                "after": "Verified web server configuration granting appropriate read access",
            }
            validation = [
                "Review web server error logs at the exact timestamp of the crawl request.",
                "Execute `crawl_with_baseline()` to see if a standard desktop browser receives HTTP 403 or HTTP 200.",
                "Verify file permissions for the web server user (e.g. www-data or nginx).",
                f"Test from command line using curl: curl -sI -A '{audit.user_agent or 'GPTBot'}' https://{domain}/",
            ]
            uncertainty = (
                "High uncertainty. The available evidence does not conclusively identify the blocking mechanism. "
                "No known WAF or bot-detection markers were observed."
            )

        # -------------------------------------------------------------
        # 5. Detected WAF / Challenge Mechanism
        # -------------------------------------------------------------
        elif audit.issue_type == IssueType.WAF_OR_CHALLENGE:
            mechanism = audit.mechanism
            evidence = []
            if audit.http_status_code:
                evidence.append(f"HTTP Status Code: {audit.http_status_code}")
            evidence.extend([f"Header: {h}" for h in audit.evidence_matched_headers])
            evidence.extend([f"DOM Signal: {s}" for s in audit.evidence_dom_signals])
            evidence.extend([f"Matched Keyword: '{k}'" for k in audit.evidence_matched_keywords])
            if not evidence and audit.observed_facts:
                evidence = audit.observed_facts[:5]

            problem = f"{mechanism} intercepted the AI crawler request."
            why = (
                f"The automated request from {persona_name} was intercepted by {mechanism}. "
                f"AI crawlers do not execute interactive JavaScript challenges (such as Turnstile or CAPTCHAs) "
                f"and will not retrieve page contents when challenged, causing the page to be excluded from AI search indexes."
            )

            # Mechanism-specific code / configuration recommendations
            if "CLOUDFLARE" in mechanism:
                fix = "Create a Cloudflare Custom WAF Rule to allow or skip challenges for verified AI bots."
                code = (
                    "# Cloudflare Custom WAF Rule (Security -> WAF -> Custom Rules)\n"
                    "# Rule Name: Allow Verified AI Crawlers\n"
                    "# Expression:\n"
                    '(cf.client.bot or http.user_agent contains "GPTBot" or '
                    'http.user_agent contains "ClaudeBot" or '
                    'http.user_agent contains "PerplexityBot")\n\n'
                    "# Action: Skip\n"
                    "# Skip components: WAF Managed Rules, Bot Management, Rate Limiting\n"
                )
                before_after = {
                    "before": "Interactive challenge (Turnstile / JS Challenge) enforced for all automated requests",
                    "after": "WAF skip / allow rule configured for verified AI bot user-agents",
                }
            elif "AWS_WAF" in mechanism:
                fix = "Configure an AWS WAF Web ACL rule to allow verified AI crawler User-Agents."
                code = (
                    "# AWS WAF Web ACL Rule JSON snippet\n"
                    "{\n"
                    '  "Name": "AllowAICrawlers",\n'
                    '  "Priority": 1,\n'
                    '  "Action": { "Allow": {} },\n'
                    '  "Statement": {\n'
                    '    "ByteMatchStatement": {\n'
                    '      "FieldToMatch": { "SingleHeader": { "Name": "user-agent" } },\n'
                    f'      "SearchString": "{persona_name}",\n'
                    '      "TextTransformations": [{ "Priority": 0, "Type": "NONE" }],\n'
                    '      "PositionalConstraint": "CONTAINS"\n'
                    '    }\n'
                    '  },\n'
                    '  "VisibilityConfig": { "SampledRequestsEnabled": true, "CloudWatchMetricsEnabled": true, "MetricName": "AllowAICrawlers" }\n'
                    "}\n"
                )
                before_after = {
                    "before": "AWS WAF ACL blocking or challenging AI agent requests",
                    "after": "AWS WAF Web ACL rule explicitly allowing verified AI bot User-Agents",
                }
            elif "DATADOME" in mechanism:
                fix = "Add verified AI bots to your DataDome allowlist in the DataDome dashboard."
                code = (
                    "# DataDome Dashboard Configuration:\n"
                    "# 1. Navigate to Management -> Whitelist / Allowlist\n"
                    "# 2. Select Category: Partner / AI Bot\n"
                    f"# 3. Add '{persona_name}' to allowed crawler bots\n"
                )
                before_after = {
                    "before": "DataDome anti-bot challenge intercepting crawler",
                    "after": "DataDome allowlist rule configured for AI agent",
                }
            elif "PERIMETERX" in mechanism:
                fix = "Update HUMAN Security / PerimeterX bot policies to allowlist verified AI search crawlers."
                code = (
                    "# HUMAN Security (PerimeterX) Console Configuration:\n"
                    "# 1. Navigate to Bot Defender -> Policies\n"
                    "# 2. Add custom allow rule for User-Agent containing 'GPTBot' or 'ClaudeBot'\n"
                )
                before_after = {
                    "before": "PerimeterX challenge (#px-captcha) intercepting requests",
                    "after": "Bot Defender policy allowing verified AI search crawlers",
                }
            elif "RECAPTCHA" in mechanism or "HCAPTCHA" in mechanism:
                fix = "Ensure public landing pages and content routes do not trigger CAPTCHA verification for automated search crawlers."
                code = (
                    "# Application Routing Configuration:\n"
                    "# Restrict CAPTCHA challenges to user interactive flows (login, checkout, sign-up)\n"
                    "# Exclude GET requests for public content paths from CAPTCHA middleware\n"
                )
                before_after = {
                    "before": "CAPTCHA widget rendered on public content path",
                    "after": "Public content served directly; CAPTCHA restricted to transactional POST flows",
                }
            else:
                fix = f"Review security rules for {mechanism} and establish an allow rule for verified AI crawler user-agents."
                code = f"# Configure {mechanism} access control to allow User-Agent: {persona_name}\n"
                before_after = {
                    "before": f"{mechanism} access denial",
                    "after": f"{mechanism} allowlist configured",
                }

            validation = [
                f"Apply the configuration change in your {mechanism} control console.",
                f"Re-run AI Crawl Optimizer audit for URL with persona '{audit.persona}'.",
                "Verify HTTP 200 status code and absence of challenge DOM elements.",
            ]
            uncertainty = "The exact rule syntax may depend on your provider plan and enterprise configuration."

        # -------------------------------------------------------------
        # 6. HTTP 429 Rate Limited Issue
        # -------------------------------------------------------------
        elif audit.issue_type == IssueType.HTTP_429_RATE_LIMITED:
            problem = "HTTP 429 Too Many Requests (Rate limit enforced by server or CDN)."
            evidence = ["HTTP Status Code: 429"]
            why = "The web server or CDN rate limiting threshold was exceeded, temporarily rejecting further crawl requests."
            fix = "Increase rate limiting thresholds for verified AI crawlers or specify a crawl-delay in robots.txt."
            code = (
                f"# Add crawl-delay to robots.txt to pace crawler requests:\n"
                f"User-agent: {persona_name}\n"
                f"Crawl-delay: 5\n"
            )
            before_after = {
                "before": "HTTP 429 rate limit exceeded",
                "after": "Paced crawling with Crawl-delay and relaxed rate limit bucket",
            }
            validation = [
                "Deploy Crawl-delay in robots.txt.",
                "Wait for rate limit cool-off period and re-test URL.",
            ]
            uncertainty = "Exact rate limit window depends on server config."

        # -------------------------------------------------------------
        # 7. Clean / Accessible (No Issue)
        # -------------------------------------------------------------
        else:
            problem = "No access restrictions detected. The page is accessible to AI crawlers."
            evidence = [
                f"HTTP Status Code: {audit.http_status_code or 200}",
                f"robots.txt is_allowed: {audit.robots_is_allowed}",
                f"Detection Verdict: {audit.verdict}",
            ]
            why = "The page returned a successful HTTP 200 response and neither robots.txt nor WAF mechanisms restrict crawling."
            fix = "Maintain current accessibility and ensure content has structured semantic metadata for AI extraction."
            code = (
                "<!-- Best Practice: Structured Data for AI Summarization -->\n"
                "<script type=\"application/ld+json\">\n"
                "{\n"
                '  "@context": "https://schema.org",\n'
                '  "@type": "WebPage",\n'
                f'  "name": "{audit.page_title or "Documentation"}",\n'
                f'  "url": "{audit.target_url}"\n'
                "}\n"
                "</script>\n"
            )
            before_after = {
                "before": "Page accessible without structured metadata",
                "after": "Page accessible with JSON-LD semantic markup for AI ingestion",
            }
            validation = [
                "Verify Google Rich Results or Schema Validator on the target URL.",
                "Monitor server response times during crawler indexation.",
            ]
            uncertainty = "None. Page is currently accessible."

        return RemediationResult(
            problem_detected=problem,
            evidence=evidence,
            why_it_affects_ai_crawling=why,
            recommended_fix=fix,
            code_or_configuration_change=code,
            before_after_example=before_after,
            validation_steps=validation,
            uncertainty=uncertainty,
            observed_facts={"facts": audit.observed_facts, "inferences": audit.crawler_inferences},
        )


def generate_remediation(
    crawler_result: Any,
    api_key: Optional[str] = None,
    model: str = "gemini-1.5-flash",
) -> Dict[str, Any]:
    """
    Public API function: Accepts a crawler result dict/model and returns
    a clean, developer-friendly remediation suggestion dictionary.
    """
    engine = RemediationEngine(api_key=api_key, model=model)
    return engine.remediate(crawler_result)
