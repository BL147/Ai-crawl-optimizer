"""
Remediation Engine for AI Crawler Compatibility & Bot Management.

Accepts structured crawler result output and produces grounded, developer-friendly
remediation guidance strictly based on observed evidence without hallucinating
unverified blocking vendors or mechanisms.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class RemediationAdvice:
    problem_detected: str
    evidence: List[str]
    why_it_affects_ai_crawling: str
    recommended_fix: str
    exact_code_change: str
    code_language: str
    before_after_example: str
    validation_steps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_detected": self.problem_detected,
            "evidence": self.evidence,
            "why_it_affects_ai_crawling": self.why_it_affects_ai_crawling,
            "recommended_fix": self.recommended_fix,
            "exact_code_change": self.exact_code_change,
            "code_language": self.code_language,
            "before_after_example": self.before_after_example,
            "validation_steps": self.validation_steps,
        }

    def format_markdown(self) -> str:
        evidence_md = "\n".join(f"- {e}" for e in self.evidence)
        steps_md = "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.validation_steps))
        return f"""### 1. Problem Detected
{self.problem_detected}

### 2. Evidence
{evidence_md}

### 3. Why It Affects AI Crawling
{self.why_it_affects_ai_crawling}

### 4. Recommended Fix
{self.recommended_fix}

### 5. Exact Code / Configuration Change
```{self.code_language}
{self.exact_code_change}
```

### 6. Before / After Example
{self.before_after_example}

### 7. Validation Steps
{steps_md}
"""


class RemediationEngine:
    """
    Evaluates structured crawler results and generates strict, evidence-grounded
    remediations for:
    - Robots.txt blocking/disallowing
    - HTTP headers / Meta tags (X-Robots-Tag, meta name="robots")
    - Verified WAF / Bot management challenges (Cloudflare, DataDome, PerimeterX, AWS WAF, etc.)
    - Inconclusive / generic HTTP 403 or 429 blocks
    """

    def generate_remediation(self, result: Dict[str, Any]) -> RemediationAdvice:
        """
        Main entrypoint: parses the structured result and routes to the appropriate
        specialized generator.
        """
        detection = result.get("detection", {})
        evidence_list = detection.get("evidence", [])
        inference = detection.get("inference", {})
        mechanism = inference.get("mechanism", "").upper() if inference else ""

        robots_txt = result.get("robots_txt", {})
        http_data = result.get("http", {})
        page_data = result.get("page", {})
        status_code = http_data.get("status_code")

        # 1. Check for specific WAF / Bot challenge mechanisms
        if mechanism in ["CLOUDFLARE_CHALLENGE", "CLOUDFLARE"]:
            return self._remediate_cloudflare(evidence_list, http_data, inference)
        elif mechanism in ["DATADOME"]:
            return self._remediate_datadome(evidence_list, http_data, inference)
        elif mechanism in ["PERIMETERX", "HUMAN_SECURITY"]:
            return self._remediate_perimeterx(evidence_list, http_data, inference)
        elif mechanism in ["AWS_WAF"]:
            return self._remediate_aws_waf(evidence_list, http_data, inference)
        elif mechanism in ["RECAPTCHA", "CAPTCHA"]:
            return self._remediate_recaptcha(evidence_list, http_data, inference)
        elif mechanism == "RATE_LIMITED" or status_code == 429:
            return self._remediate_rate_limiting(evidence_list, http_data)

        # 2. Check for Inconclusive blocks (HTTP 403 Forbidden without recognized signature)
        verdict = inference.get("verdict", "").upper() if inference else ""
        if (
            mechanism in ["INCONCLUSIVE", "UNKNOWN", "HTTP_FORBIDDEN", "NONE", ""]
            and status_code in [403, "403", "HTTP_FORBIDDEN"]
        ) or inference.get("status") == "INCONCLUSIVE" or verdict == "INCONCLUSIVE":
            return self._remediate_inconclusive_forbidden(evidence_list, http_data)

        # 3. Check for robots.txt blocking rules
        is_robots_disallowed = (
            robots_txt.get("is_blocked") is True
            or (robots_txt.get("is_allowed") is False and robots_txt.get("exists") is True)
            or ("disallow" in str(robots_txt.get("matching_rule", "")).lower())
        )
        if is_robots_disallowed:
            return self._remediate_robots_txt(robots_txt, evidence_list)

        # 4. Check for HTTP X-Robots-Tag or HTML Meta Tag blocking
        x_robots = http_data.get("x_robots_tag")
        meta_tags = page_data.get("meta_tags", {})
        robots_meta = meta_tags.get("robots") or meta_tags.get("googlebot")
        if x_robots or robots_meta:
            combined = f"{x_robots or ''} {robots_meta or ''}".lower()
            if "noindex" in combined or "none" in combined or "nofollow" in combined:
                return self._remediate_meta_and_headers(x_robots, robots_meta, evidence_list)

        # 5. Fallback for generic or passed audits
        return self._remediate_generic_pass_or_unknown(result, evidence_list)

    def _remediate_cloudflare(
        self, evidence: List[str], http_data: Dict[str, Any], inference: Dict[str, Any]
    ) -> RemediationAdvice:
        headers = http_data.get("headers", {})
        cf_ray = headers.get("cf-ray") or headers.get("CF-RAY", "Present in headers")
        ev = evidence if evidence else [f"Cloudflare Turnstile/Challenge detected", f"cf-ray: {cf_ray}"]

        return RemediationAdvice(
            problem_detected="Cloudflare Managed Challenge / Bot Fight Mode Active",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "Cloudflare's automated challenge (Managed Challenge / Super Bot Fight Mode) requires "
                "interactive JavaScript execution and browser canvas/fingerprint verification. AI crawlers "
                "operate non-interactively via HTTP clients and cannot execute or solve these challenge interstitials."
            ),
            recommended_fix=(
                "Create an authenticated Cloudflare Custom WAF Rule or configure Bot Management to skip "
                "Bot Fight Mode challenges for verified AI user agents (or verified IP ranges using CF verified bot tags)."
            ),
            exact_code_change=(
                '# Cloudflare WAF Custom Rule (Expression Builder):\n'
                '(cf.client.bot and (http.user_agent contains "GPTBot" or http.user_agent contains "ClaudeBot" or http.user_agent contains "PerplexityBot"))\n'
                '# Action: Skip -> Select "All remaining custom rules" and "Bot Fight Mode"'
            ),
            code_language="text",
            before_after_example=(
                "BEFORE:\n"
                "  All non-standard browser user agents trigger an interactive managed challenge (HTTP 403 / JavaScript interstitial).\n"
                "AFTER:\n"
                "  Verified AI crawlers match the WAF skip exception and receive immediate 200 OK HTML responses."
            ),
            validation_steps=[
                "Deploy the custom rule in the Cloudflare Dashboard under Security > WAF > Custom Rules.",
                "Send a curl request with the target User-Agent: curl -I -A 'Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)' https://example.com",
                "Verify HTTP status 200 OK is returned and cf-mitigated header is absent or marked bypassed."
            ]
        )

    def _remediate_datadome(
        self, evidence: List[str], http_data: Dict[str, Any], inference: Dict[str, Any]
    ) -> RemediationAdvice:
        ev = evidence if evidence else ["DataDome cookie/interstitial response detected in HTTP response"]
        return RemediationAdvice(
            problem_detected="DataDome Bot Management Protection Triggered",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "DataDome intercepts requests missing valid device telemetry or client behavioral cookies, "
                "issuing a 403 with a DataDome CAPTCHA/Device-Check payload that automated AI engines cannot complete."
            ),
            recommended_fix=(
                "Add an allowlist rule in the DataDome Dashboard under 'Management' -> 'Custom Rules' specifically "
                "for authorized AI bots, or use DataDome's AI Crawler Allowlist feature."
            ),
            exact_code_change=(
                '// DataDome Custom Rule Specification\n'
                '{\n'
                '  "rule_name": "Allow_Verified_AI_Crawlers",\n'
                '  "criteria": [\n'
                '    { "type": "user_agent", "operator": "contains", "values": ["GPTBot", "ClaudeBot", "PerplexityBot"] },\n'
                '    { "type": "verified_bot", "operator": "equals", "value": true }\n'
                '  ],\n'
                '  "action": "ALLOW"\n'
                '}'
            ),
            code_language="json",
            before_after_example=(
                "BEFORE:\n"
                "  DataDome returns HTTP 403 with `x-datadome: protected` and captcha redirect.\n"
                "AFTER:\n"
                "  DataDome matches verified AI partner identity and forwards traffic directly to the origin web server."
            ),
            validation_steps=[
                "Log in to the DataDome dashboard and add the verified bot rule.",
                "Execute an audit request with the target crawler User-Agent.",
                "Inspect response headers to verify the `x-datadome` response header indicates `pass` or allow."
            ]
        )

    def _remediate_perimeterx(
        self, evidence: List[str], http_data: Dict[str, Any], inference: Dict[str, Any]
    ) -> RemediationAdvice:
        ev = evidence if evidence else ["PerimeterX / HUMAN Security block payload detected"]
        return RemediationAdvice(
            problem_detected="HUMAN Security (PerimeterX) Bot Detection Enforced",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "PerimeterX enforcer modules inspect client sensor data. Requests lacking client JS telemetry "
                "are tagged as automated threats and served an interactive block page or HTTP 403."
            ),
            recommended_fix=(
                "Update the PerimeterX Enforcer configuration file (in NGINX, Node, or CDN middleware) to include "
                "verified AI crawler user-agents in `px_custom_allowlist_headers` or `px_whitelist_uri_full`."
            ),
            exact_code_change=(
                '// PerimeterX Enforcer Configuration (e.g. px_config.json / Node middleware)\n'
                '{\n'
                '  "px_custom_verification_enabled": true,\n'
                '  "px_bypass_monitor_header": "X-PX-BYPASS",\n'
                '  "px_user_agent_allowlist": [\n'
                '    "GPTBot",\n'
                '    "ClaudeBot",\n'
                '    "PerplexityBot"\n'
                '  ],\n'
                '  "px_ip_reverse_lookup": true\n'
                '}'
            ),
            code_language="json",
            before_after_example=(
                "BEFORE:\n"
                "  AI crawler request returns HTTP 403 with PerimeterX `_px` payload script.\n"
                "AFTER:\n"
                "  PerimeterX enforcer bypasses sensor check for verified AI user agents and serves origin content."
            ),
            validation_steps=[
                "Deploy the updated `px_config` to your reverse proxy / enforcer middleware.",
                "Simulate an AI crawler request with curl: curl -H 'User-Agent: GPTBot' -i https://example.com",
                "Verify HTTP 200 OK without PerimeterX block markers."
            ]
        )

    def _remediate_aws_waf(
        self, evidence: List[str], http_data: Dict[str, Any], inference: Dict[str, Any]
    ) -> RemediationAdvice:
        ev = evidence if evidence else ["AWS WAF token/interstitial challenge detected in headers or body"]
        return RemediationAdvice(
            problem_detected="AWS WAF AWSManagedRulesBotControlRuleSet Block",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "The AWS WAF Bot Control managed rule set blocks or challenges requests that match scraper signatures "
                "or lack AWS WAF JavaScript challenge tokens."
            ),
            recommended_fix=(
                "Add a custom rule with higher priority than the Bot Control rule group in your WebACL that matches "
                "AI search bot User-Agent strings and overrides the action to Count or Allow."
            ),
            exact_code_change=(
                '# AWS WAFv2 WebACL Rule Statement (JSON / CloudFormation)\n'
                '{\n'
                '  "Name": "Allow-AICrawlers",\n'
                '  "Priority": 0,\n'
                '  "Action": { "Allow": {} },\n'
                '  "VisibilityConfig": {\n'
                '    "SampledRequestsEnabled": true,\n'
                '    "CloudWatchMetricsEnabled": true,\n'
                '    "MetricName": "AllowAICrawlers"\n'
                '  },\n'
                '  "Statement": {\n'
                '    "ByteMatchStatement": {\n'
                '      "FieldToMatch": { "SingleHeader": { "Name": "user-agent" } },\n'
                '      "PositionalConstraint": "CONTAINS",\n'
                '      "SearchString": "GPTBot",\n'
                '      "TextTransformations": [{ "Priority": 0, "Type": "LOWERCASE" }]\n'
                '    }\n'
                '  }\n'
                '}'
            ),
            code_language="json",
            before_after_example=(
                "BEFORE:\n"
                "  AWS WAF Bot Control evaluates request first and returns HTTP 403 Forbidden with `x-amzn-waf-action: block`.\n"
                "AFTER:\n"
                "  Priority 0 rule allows verified AI crawlers before Bot Control evaluation."
            ),
            validation_steps=[
                "Apply the rule to the target WebACL in AWS WAF Console or CloudFormation.",
                "Review CloudWatch metrics for the `AllowAICrawlers` rule.",
                "Verify curl requests containing the User-Agent receive HTTP 200 without `x-amzn-waf-action` blocks."
            ]
        )

    def _remediate_recaptcha(
        self, evidence: List[str], http_data: Dict[str, Any], inference: Dict[str, Any]
    ) -> RemediationAdvice:
        ev = evidence if evidence else ["CAPTCHA challenge detected in HTML body or redirect"]
        return RemediationAdvice(
            problem_detected="Interactive CAPTCHA Challenge Interstitial",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "Automated crawlers cannot render or solve visual/interactive CAPTCHA challenges, causing "
                "the crawl job to abort and content to be excluded from LLM search indexes."
            ),
            recommended_fix=(
                "Configure edge middleware to bypass interactive CAPTCHAs for legitimate bots identified by "
                "User-Agent combined with reverse DNS (rDNS) verification."
            ),
            exact_code_change=(
                '# NGINX reverse-proxy CAPTCHA bypass logic:\n'
                'map $http_user_agent $bypass_captcha {\n'
                '    default 0;\n'
                '    "~*(GPTBot|ClaudeBot|PerplexityBot)" 1;\n'
                '}\n\n'
                'server {\n'
                '    location / {\n'
                '        if ($bypass_captcha = 1) {\n'
                '            proxy_pass http://origin_content;\n'
                '            break;\n'
                '        }\n'
                '        # Normal human challenge flow continues here\n'
                '    }\n'
                '}'
            ),
            code_language="nginx",
            before_after_example=(
                "BEFORE:\n"
                "  Request is redirected to a /captcha or /challenge gatekeeper page.\n"
                "AFTER:\n"
                "  Identified AI crawler bypasses challenge gate and accesses canonical HTML directly."
            ),
            validation_steps=[
                "Reload NGINX configuration (`nginx -t && systemctl reload nginx`).",
                "Perform request with AI bot User-Agent.",
                "Confirm that response body contains actual page markup rather than the CAPTCHA iframe/form."
            ]
        )

    def _remediate_inconclusive_forbidden(
        self, evidence: List[str], http_data: Dict[str, Any]
    ) -> RemediationAdvice:
        """
        STRICT GROUNDING: The crawler reports INCONCLUSIVE + HTTP_FORBIDDEN.
        Must NOT claim that the site specifically blocks AI crawlers or assume a vendor.
        """
        headers = http_data.get("headers", {})
        server = headers.get("server") or headers.get("Server", "Unknown / Not Provided")
        ev = evidence if evidence else [
            "HTTP status code: 403 Forbidden",
            f"Server header: {server}",
            "No recognized WAF or bot management signature identified in body or response headers."
        ]

        return RemediationAdvice(
            problem_detected="Uncertain Root Cause: HTTP 403 Forbidden (Inconclusive Mechanism)",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "The server or upstream proxy returned an HTTP 403 Forbidden status code to the crawler. "
                "However, no definitive WAF fingerprint, challenge page, or vendor-specific signature was detected. "
                "Because the evidence is inconclusive, it CANNOT be confirmed whether this site specifically targets AI crawlers, "
                "or if this block is caused by generic User-Agent filtering, IP geolocation/datacenter ASN filtering, "
                "origin server file permissions, or an unbranded reverse proxy rule."
            ),
            recommended_fix=(
                "Diagnose upstream ingress logs to isolate the exact component returning the 403: "
                "1. Test request from a non-datacenter residential/office IP with standard curl headers. "
                "2. Check web server (NGINX/Apache) access and error logs for permission or User-Agent denial directives. "
                "3. Verify whether reverse proxies or cloud security groups restrict requests missing specific browser headers (e.g. Accept-Language, Sec-Fetch-*)."
            ),
            exact_code_change=(
                '# Step 1: Diagnose via curl using verbose output to isolate where the 403 originates\n'
                'curl -iv -A "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)" \\\n'
                '     -H "Accept: text/html,application/xhtml+xml" \\\n'
                '     https://example.com/\n\n'
                '# Step 2: In NGINX, ensure User-Agent or default server block is not issuing an unconditional 403:\n'
                'server {\n'
                '    listen 443 ssl;\n'
                '    server_name example.com;\n'
                '    # Check for blanket deny rules like:\n'
                '    # if ($http_user_agent ~* (bot|crawler)) { return 403; }\n'
                '}'
            ),
            code_language="bash",
            before_after_example=(
                "BEFORE:\n"
                "  Crawler receives HTTP 403 Forbidden from an unidentified upstream layer.\n"
                "AFTER:\n"
                "  Server logs identify whether the block was triggered by missing headers, datacenter IP filtering, "
                "or an explicit web server configuration."
            ),
            validation_steps=[
                "Check server error logs: `tail -f /var/log/nginx/error.log` while making the test request.",
                "Compare the response against an identical request with a standard desktop browser User-Agent.",
                "Check whether your hosting provider or cloud edge has default geo-blocking or datacenter IP restrictions enabled."
            ]
        )

    def _remediate_rate_limiting(
        self, evidence: List[str], http_data: Dict[str, Any]
    ) -> RemediationAdvice:
        headers = http_data.get("headers", {})
        retry_after = headers.get("retry-after") or headers.get("Retry-After", "Not specified")
        ev = evidence if evidence else [
            "HTTP status code: 429 Too Many Requests",
            f"Retry-After header: {retry_after}"
        ]

        return RemediationAdvice(
            problem_detected="Aggressive Rate Limiting (HTTP 429 Too Many Requests)",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "AI search engines crawl multiple pages concurrently. High request frequency triggers "
                "rate-limiting thresholds, causing crawler threads to be dropped and content indexing to stall."
            ),
            recommended_fix=(
                "Define a dedicated rate-limiting zone for recognized crawler user agents or specify "
                "a `crawl-delay` directive in `robots.txt`."
            ),
            exact_code_change=(
                '# NGINX Rate Limiting Configuration\n'
                'limit_req_zone $binary_remote_addr zone=general_zone:10m rate=10r/s;\n'
                'limit_req_zone $binary_remote_addr zone=ai_crawler_zone:10m rate=30r/s;\n\n'
                'map $http_user_agent $is_ai_bot {\n'
                '    default 0;\n'
                '    "~*(GPTBot|ClaudeBot|PerplexityBot)" 1;\n'
                '}\n\n'
                'server {\n'
                '    location / {\n'
                '        set $rate_zone general_zone;\n'
                '        if ($is_ai_bot = 1) {\n'
                '            limit_req zone=ai_crawler_zone burst=20 nodelay;\n'
                '        }\n'
                '        proxy_pass http://upstream;\n'
                '    }\n'
                '}'
            ),
            code_language="nginx",
            before_after_example=(
                "BEFORE:\n"
                "  AI crawler bursts exceed low consumer rate limit and trigger HTTP 429.\n"
                "AFTER:\n"
                "  AI crawler is allocated an expanded burst capacity and does not receive 429 errors."
            ),
            validation_steps=[
                "Test burst capacity with an automated testing tool or Apache Bench (`ab -n 50 -c 5`).",
                "Verify HTTP 200 responses are maintained within the designated burst thresholds."
            ]
        )

    def _remediate_robots_txt(
        self, robots_txt: Dict[str, Any], evidence: List[str]
    ) -> RemediationAdvice:
        raw_content = robots_txt.get("raw_content", "")
        matching_rule = robots_txt.get("matching_rule", "Disallow: /")
        ev = evidence if evidence else [
            f"Matching rule: {matching_rule}",
            "robots.txt raw content contains explicit Disallow directive for AI crawlers"
        ]

        return RemediationAdvice(
            problem_detected="Robots.txt Disallow Directive Blocking AI Agents",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "Compliant AI crawlers (like GPTBot, ClaudeBot, PerplexityBot) strictly respect robots.txt. "
                "A `Disallow: /` rule prohibits these agents from accessing and indexing the site."
            ),
            recommended_fix=(
                "Update `robots.txt` to explicitly grant access to specific AI agents for public pages, "
                "while restricting sensitive or private administration endpoints."
            ),
            exact_code_change=(
                '# /robots.txt\n'
                'User-agent: GPTBot\n'
                'Allow: /\n'
                'Disallow: /admin/\n'
                'Disallow: /private/\n\n'
                'User-agent: ClaudeBot\n'
                'Allow: /\n'
                'Disallow: /admin/\n'
                'Disallow: /private/\n\n'
                'User-agent: PerplexityBot\n'
                'Allow: /\n\n'
                'User-agent: *\n'
                'Allow: /\n'
                'Sitemap: https://example.com/sitemap.xml'
            ),
            code_language="robots.txt",
            before_after_example=(
                f"BEFORE:\n"
                f"  {matching_rule}\n\n"
                f"AFTER:\n"
                f"  User-agent: GPTBot\n  Allow: /"
            ),
            validation_steps=[
                "Deploy the updated file to the web root at `https://example.com/robots.txt`.",
                "Verify accessibility: curl -i https://example.com/robots.txt",
                "Validate using standard robots.txt validators or Google Search Console Robots Testing tool."
            ]
        )

    def _remediate_meta_and_headers(
        self, x_robots: Optional[str], robots_meta: Optional[str], evidence: List[str]
    ) -> RemediationAdvice:
        ev = evidence if evidence else []
        if x_robots:
            ev.append(f"X-Robots-Tag header: {x_robots}")
        if robots_meta:
            ev.append(f"<meta name='robots'> content: {robots_meta}")

        return RemediationAdvice(
            problem_detected="Content Disallowed via X-Robots-Tag Header or Robots Meta Tag",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "Directives such as `noindex`, `none`, or `noai` instructed in HTTP headers or HTML meta tags "
                "tell crawlers that although the HTTP request succeeded, the content cannot be saved, processed, "
                "or indexed into LLM search answers."
            ),
            recommended_fix=(
                "Remove restrictive `noindex` or `noai` directives from the HTTP response headers and HTML head "
                "on publicly viewable pages intended for AI search discovery."
            ),
            exact_code_change=(
                '<!-- In HTML <head>: -->\n'
                '<!-- BEFORE: -->\n'
                '<!-- <meta name="robots" content="noindex, nofollow"> -->\n\n'
                '<!-- AFTER: -->\n'
                '<meta name="robots" content="index, follow">\n\n'
                '# In Web Server Header Config (e.g. NGINX):\n'
                '# Remove: add_header X-Robots-Tag "noindex, nofollow";\n'
                'add_header X-Robots-Tag "index, follow";'
            ),
            code_language="html",
            before_after_example=(
                f"BEFORE:\n"
                f"  X-Robots-Tag: {x_robots or 'None'} | Meta: {robots_meta or 'None'}\n"
                f"AFTER:\n"
                f"  X-Robots-Tag: index, follow | Meta: <meta name='robots' content='index, follow'>"
            ),
            validation_steps=[
                "Deploy header or HTML template modifications.",
                "Send a curl request to verify headers: curl -I https://example.com",
                "Inspect HTML source to ensure no conflicting meta robots tags remain."
            ]
        )

    def _remediate_generic_pass_or_unknown(
        self, result: Dict[str, Any], evidence: List[str]
    ) -> RemediationAdvice:
        ev = evidence if evidence else ["HTTP 200 OK received; no blocking signatures observed."]
        return RemediationAdvice(
            problem_detected="No Blocking Mechanism Detected (Site Accessible)",
            evidence=ev,
            why_it_affects_ai_crawling=(
                "The site is currently accessible to AI crawler requests without being blocked by WAFs, "
                "status code errors, or restrictive headers."
            ),
            recommended_fix=(
                "Maintain accessibility by verifying that `robots.txt` explicitly documents crawling policies "
                "and ensure edge security rules do not inadvertently block crawler IP blocks in future updates."
            ),
            exact_code_change=(
                '# Maintain explicit crawler guidance in /robots.txt\n'
                'User-agent: GPTBot\n'
                'Allow: /\n\n'
                'User-agent: ClaudeBot\n'
                'Allow: /\n\n'
                'User-agent: PerplexityBot\n'
                'Allow: /'
            ),
            code_language="robots.txt",
            before_after_example=(
                "BEFORE:\n"
                "  Implicit access permissions.\n"
                "AFTER:\n"
                "  Explicit permissions defined in robots.txt for AI search crawlers."
            ),
            validation_steps=[
                "Monitor periodic crawl logs to verify continued 200 OK delivery to AI crawlers."
            ]
        )
