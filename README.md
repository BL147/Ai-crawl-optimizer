# AI Crawl Optimizer — Crawler & Bot-Block Detection Module

A modular, Playwright-based crawler and heuristic bot-block detection engine built for the **AI Crawl Optimizer** developer tool.

Audits whether websites are accessible to AI agent crawlers (OpenAI GPTBot, Anthropic ClaudeBot, PerplexityBot, Google-Extended, ByteDance Bytespider, etc.) versus standard desktop browsers.

---

## Features

- **Simulate AI Personas**: Predefined, configurable personas (`gptbot`, `claudebot`, `perplexitybot`, `google_extended`, `bytespider`, `ccbot`, `oai_searchbot`, `cohere`) and custom User-Agents.
- **Baseline Comparison**: Compare AI crawler accessibility directly against a standard desktop browser (`standard_browser`) to prove selective bot discrimination.
- **RFC 9309-Compliant `robots.txt` Parser**: Evaluates path matching, wildcard patterns (`*` and `$`), longest-match rule precedence, crawl delays, and sitemaps, with automated extraction of AI-specific directives.
- **HTTP & DOM Observation**: Tracks response codes, redirect chains, server and `X-Robots-Tag` headers, latency, page title, text length, and readable snippets.
- **Bot-Block & Challenge Detector**:
  - **Cloudflare**: Turnstile (`.cf-turnstile`), "Just a moment...", Ray ID, Error 1020/1015.
  - **DataDome**: Protection tags, cookies, challenge headers.
  - **PerimeterX / HUMAN Security**: Challenge scripts, `_px` headers, access denied blocks.
  - **AWS WAF**: Captcha challenges, 405 blocks.
  - **Akamai**: Transform headers, error reference signatures.
  - **CAPTCHAs**: Google reCAPTCHA, hCaptcha iframes.
  - **Generic Status Codes**: 403 Forbidden, 429 Rate Limit, 503 Anti-DDoS.
- **Team-Ready Modular API**: Exports clean Python functions returning JSON-serializable dictionaries for Streamlit UI (`K`), Gemini Remediation (`S`), and Orchestration/Scoring (`Sh`).

---

## Installation

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Install Playwright browser binary
playwright install chromium
```

---

## Python API Usage

### 1. Basic Crawl (Async)

```python
import asyncio
from crawler import crawl_url

async def main():
    result = await crawl_url("https://example.com", persona="gptbot")
    print(result["detection"]["is_blocked"])
    print(result["detection"]["block_type"])

asyncio.run(main())
```

### 2. Synchronous Crawl (For Streamlit or Synchronous Orchestrator)

```python
from crawler import crawl_sync

# Safe to call directly inside Streamlit scripts
result = crawl_sync("https://example.com", persona="claudebot")
print(result["http"]["status_code"])
print(result["robots_txt"]["is_allowed"])
```

### 3. Baseline Comparison (AI Persona vs. Standard Browser)

```python
import asyncio
from crawler import crawl_with_baseline

async def main():
    comparison = await crawl_with_baseline("https://example.com", persona="gptbot")
    if comparison["selective_ai_block_detected"]:
        print("Site selectively discriminates against AI agents!")

asyncio.run(main())
```

### 4. Audit Across All Supported AI Personas

```python
import asyncio
from crawler import crawl_all_personas

async def main():
    results = await crawl_all_personas("https://example.com")
    for res in results:
        print(f"{res['persona']}: Blocked={res['detection']['is_blocked']}")

asyncio.run(main())
```

---

## CLI Usage

```bash
# Audit a URL with default GPTBot
python run_crawler.py https://example.com

# Audit with a specific persona
python run_crawler.py https://example.com --persona claudebot

# Compare against standard desktop browser baseline
python run_crawler.py https://example.com --baseline

# Audit across all AI personas
python run_crawler.py https://example.com --all

# Output raw JSON to stdout or save to file
python run_crawler.py https://example.com --json
python run_crawler.py https://example.com -o result.json

# List supported personas
python run_crawler.py --list-personas
```

---

## Output Dictionary Schema

```json
{
  "target_url": "https://example.com/article",
  "persona": "gptbot",
  "user_agent": "Mozilla/5.0 ... GPTBot/1.2 ...",
  "timestamp": "2026-09-06T10:50:00Z",
  "success": true,
  "error": null,
  "robots_txt": {
    "exists": true,
    "url": "https://example.com/robots.txt",
    "status_code": 200,
    "is_allowed": false,
    "matching_rule": "Disallow: /",
    "crawl_delay": 10.0,
    "sitemaps": ["https://example.com/sitemap.xml"],
    "ai_specific_rules": {
      "gptbot": {"defined": true, "rules_count": 1, "crawl_delay": 10.0}
    },
    "raw_content": "..."
  },
  "http": {
    "status_code": 403,
    "final_url": "https://example.com/article",
    "redirect_count": 0,
    "redirects": [],
    "headers": {"server": "cloudflare", "cf-ray": "..."},
    "content_type": "text/html; charset=UTF-8",
    "response_time_ms": 284.5,
    "server": "cloudflare",
    "x_robots_tag": null
  },
  "page": {
    "title": "Attention Required! | Cloudflare",
    "meta_tags": {},
    "text_length": 520,
    "snippet": "Sorry, you have been blocked...",
    "has_javascript_requirement": true
  },
  "detection": {
    "is_blocked": true,
    "block_type": "CLOUDFLARE_BLOCK",
    "confidence": 0.95,
    "signals": [
      "Cloudflare server/cf-ray header present",
      "Cloudflare signature in page title ('Attention Required! | Cloudflare')",
      "Cloudflare challenge or error keywords found in page content"
    ]
  }
}
```

---

## Running Tests

```bash
.venv/bin/pytest -v
```
