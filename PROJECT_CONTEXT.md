# PROJECT_CONTEXT.md
> **Purpose:** Complete onboarding context for a new AI agent or team member joining this project.  
> **Last Updated:** 2026-09-06 | **Branch:** `shloksabherwal1` (integration branch)

---

## 1. Project Overview & Objective

**Project Name:** AI Crawl Optimizer  
**Type:** Hackathon submission (C2C)

This tool audits any website and tells you how accessible it is to modern **AI search engines** (ChatGPT/GPTBot, Perplexity, Claude/ClaudeBot, Google Gemini). It produces a **0-100 AI Crawlability Score**, explains what is blocking AI bots from indexing the site, and generates **ready-to-use remediation fixes** (Cloudflare WAF rules, optimized robots.txt directives).

The output is a structured audit report that can be consumed by a frontend dashboard.

---

## 2. Problem We Are Solving

As AI-powered search (ChatGPT Browse, Perplexity, Claude) replaces traditional SEO, websites that block AI crawlers become **invisible in AI-generated answers**. Many sites unknowingly block AI bots through:

- Cloudflare WAF rules that treat AI user-agents as scrapers
- robots.txt Disallow directives targeting GPTBot, ClaudeBot, CCBot
- CAPTCHAs / Turnstile challenges that AI headless browsers cannot solve
- HTTP 403 / 429 responses served selectively to AI user-agents

**We detect all of these, score them, and provide exact configuration fixes.**

---

## 3. Complete Architecture

```
INPUT: URL (from user via Streamlit UI)
           |
           v
+----------------------------------+
|         ORCHESTRATOR             |  orchestrator.py
|   run_audit(url) -> AuditResult  |
+----------+-----------------------+
           |
     +-----+------+
     |             |
     v             v
+---------+  +--------------+
| CRAWLER |  | ROBOTS.TXT   |
| (Samarth|  | Inspector    |
| Anshul) |  | (built-in)   |
+----+----+  +------+-------+
     |              |
     +---------+----+
               v
+----------------------------------+
|        SCORING ENGINE            |  scoring.py
|   calculate_score(audit_data)    |
|   -> score (0-100), grade, flags |
+----------+-----------------------+
           v
+----------------------------------+
|    AI ADVISOR / REMEDIATION      |  ai_advisor.py -> remediation/
|   generate_recommendations()     |
|   -> WAF rules, robots.txt fix   |
+----------+-----------------------+
           v
+----------------------------------+
|     UNIFIED AUDIT RESULT         |
|   {score, grade, bot_matrix,     |
|    penalties, ai_recommendations}|
+----------+-----------------------+
           v
+----------------------------------+
|     STREAMLIT DASHBOARD          |  dashboard.py / app.py
|   (Samarth UI implementation)    |
+----------------------------------+
```

Sandbox Server (sandbox/server.py) is a local Flask app that simulates a website in two modes:
- BEFORE mode: Returns HTTP 200 for browsers, HTTP 403 for AI bots
- AFTER mode: Returns HTTP 200 for everyone (AI-optimized site)

---

## 4. Folder Structure & Purpose of Every File

```
Ai-crawl-optimizer/
|
+-- orchestrator.py         [SHLOK] Master pipeline. run_audit(url) is the single entry point.
|                             Integrates crawler, robots.txt check, scoring, and AI remediation.
|
+-- scoring.py              [SHLOK] ScoringEngine class. Computes 0-100 crawlability score.
|                             Applies deductions for 403s, WAF, CAPTCHA, robots.txt, latency.
|
+-- ai_advisor.py           [SHLOK + KAVISH] Adapter bridging scoring -> Kavish remediation engine.
|                             Formats structured crawler payload and calls generate_remediation().
|
+-- test_integration.py     [SHLOK] End-to-end integration test suite.
|                             Tests BEFORE (blocked) and AFTER (optimized) modes on sandbox server.
|
+-- shlok.py                [SHLOK] Self-contained all-in-one backup/prototype file.
|                             Contains entire scoring + orchestrator + sandbox in a single file.
|                             Used early in development; main logic now split into proper modules.
|
+-- dashboard.py            [SAMARTH] Full Streamlit UI. Authoritative frontend implementation.
|                             Calls crawler/ and remediation/ directly.
|
+-- app.py                  [SAMARTH] Streamlit app entry point / alternate view.
|                             Used for deployment via: streamlit run app.py
|
+-- run_crawler.py          [SAMARTH/ANSHUL] CLI runner for the crawler module.
|
+-- requirements.txt        All Python dependencies.
+-- pyproject.toml          Project metadata and tool configuration.
+-- README.md               Public-facing project readme.
+-- PROJECT_CONTEXT.md      THIS FILE - AI agent onboarding context.
+-- .env.example            Template for environment variables (GEMINI_API_KEY).
+-- .streamlit/             Streamlit configuration (theme, server settings).
|
+-- crawler/                [SAMARTH + ANSHUL] Playwright-based AI bot emulation engine.
|   +-- __init__.py         Public API: crawl_sync(), crawl_all_sync(), crawl_target(), etc.
|   +-- engine.py           CrawlerEngine - launches Playwright browser with persona UA.
|   +-- detector.py         BotBlockDetector - identifies WAF, CAPTCHA, 403/429 from response.
|   +-- models.py           CrawlResult, BlockType Pydantic models.
|   +-- personas.py         PERSONAS dict: gptbot, claudebot, perplexitybot, standard_browser.
|   +-- robots.py           inspect_robots() - fetches and parses robots.txt for AI directives.
|
+-- remediation/            [KAVISH] Gemini-powered remediation engine. AUTHORITATIVE version.
|   +-- __init__.py         Public API: generate_remediation(crawler_result) -> dict.
|   +-- engine.py           RemediationEngine - Gemini API calls, issue analysis, fix generation.
|   +-- models.py           RemediationResult, BeforeAfterExample Pydantic models.
|   +-- normalizer.py       normalize_crawler_result() - converts raw crawl data to NormalizedAudit.
|   +-- prompt_builder.py   Builds structured prompts for Gemini from audit context.
|
+-- sandbox/                [SHLOK] Local Flask demo server for live presentation.
|   +-- server.py           start_sandbox(), set_mode("before"/"after"), get_mode().
|                             Routes: / (homepage), /robots.txt, /_mode (control endpoint).
|
+-- tests/                  Additional unit tests directory (pytest).
```

---

## 5. Technologies & Frameworks Used

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend/UI | Streamlit >= 1.35 | Main dashboard interface |
| Crawler | Playwright >= 1.49 | Headless browser for realistic AI bot emulation |
| HTTP Requests | httpx >= 0.28, requests >= 2.31 | HTTP-level fetching (lightweight/fallback) |
| AI Remediation | Google Gemini API (google-genai) | LLM-powered root cause + fix generation |
| Data Models | Pydantic >= 2.10 | Strongly-typed crawl and remediation result models |
| Demo Server | Flask >= 3.0 | Sandbox server for hackathon live demo |
| Data Processing | Pandas >= 2.2, Plotly >= 5.20 | Dashboard tables and charts |
| HTML Parsing | BeautifulSoup4 | DOM analysis for CAPTCHA signal detection |
| Testing | pytest, pytest-asyncio | Integration and unit test suites |
| Environment | python-dotenv | GEMINI_API_KEY loading from .env |

---

## 6. How the Different Modules Interact

### Primary Flow (Streamlit Dashboard)

```
dashboard.py / app.py
    |
    +-- calls: crawl_sync(url, persona) / crawl_all_sync(url)
    |             +-- crawler/engine.py -> Playwright -> returns CrawlResult
    |
    +-- calls: generate_remediation(crawl_result)
                  +-- remediation/normalizer.py -> remediation/engine.py -> Gemini API
```

### Orchestrator Flow (clean API for any frontend)

```
orchestrator.run_audit(url)
    |
    +-- tries crawler.crawl_target(url)  [Playwright, full detection]
    |   +-- falls back to built-in requests fetcher if crawler unavailable
    |
    +-- calls _check_robots_txt(url)  [requests]
    |
    +-- calls scoring.calculate_score(audit_payload)
    |   +-- returns {score, grade, penalties[]}
    |
    +-- calls ai_advisor.generate_recommendations(scoring_result, audit_context)
            +-- calls remediation.generate_remediation() -> Gemini
                +-- falls back to rule-based WAF/robots suggestions if Gemini fails
```

### Key Integration Contract: run_audit(url) return shape

```python
{
    "url": str,
    "timestamp": str,
    "summary": {"score": int, "grade": str, "status": str, "color": str, "text": str},
    "scoring": {"score": int, "grade": str, "penalties": [...], "total_deductions": int},
    "bot_matrix": {
        "browser_chrome": {"status": int, "latency_ms": int, "blocked": bool, "waf": str},
        "gpt_bot": {...},
        "claude_bot": {...},
        "perplexity_bot": {...}
    },
    "robots_txt": {"status": int, "ai_disallowed": bool, "disallowed_bots": [...]},
    "ai_recommendations": {
        "root_cause": str,
        "cloudflare_waf_rule": str,
        "robots_txt_fix": str,
        "action_items": [str]
    },
    "status": "success"
}
```

---

## 7. Current Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| scoring.py | COMPLETE | 0-100 score, grades A/B/C/F, full penalty breakdown |
| orchestrator.py | COMPLETE | Full pipeline, fallback fetcher, crawler integration |
| sandbox/server.py | COMPLETE | BEFORE/AFTER modes, robots.txt simulation |
| test_integration.py | COMPLETE | Full BEFORE/AFTER assertions, contract validation |
| ai_advisor.py | COMPLETE | Bridges orchestrator to Kavish remediation engine |
| crawler/ | COMPLETE | Playwright engine, persona system, bot detection |
| remediation/ | COMPLETE | Gemini-powered remediation with fallback |
| dashboard.py | COMPLETE | Full Streamlit UI (Samarth implementation) |
| app.py | COMPLETE | Alternate Streamlit entry point |
| requirements.txt | COMPLETE | All dependencies pinned with minimum versions |

---

## 8. Features Already Completed

1. Multi-persona AI bot emulation - GPTBot, ClaudeBot, PerplexityBot, Googlebot, standard Chrome browser tested against any URL
2. Playwright-based deep crawl - realistic browser fingerprinting, full JS execution, cookie/header analysis
3. WAF & CAPTCHA detection - Cloudflare, Akamai, DataDome, AWS CloudFront; Turnstile, reCAPTCHA, hCAPTCHA
4. robots.txt AI policy parsing - detects Disallow rules targeting GPTBot/ClaudeBot/CCBot/PerplexityBot
5. 0-100 Crawlability Score - with letter grades (A/B/C/F), color coding, and itemized penalty breakdown
6. Selective block detection - detects when browser gets 200 but AI agents get 403 (critical signal)
7. Gemini-powered remediation - uses Google Gemini API to generate root cause analysis and configuration fixes
8. Cloudflare WAF rule generation - produces copy-paste WAF expression for Cloudflare dashboard
9. robots.txt fix generation - generates optimized directives for all major AI crawlers
10. Local demo sandbox server - toggle BEFORE/AFTER mode for 100% reliable hackathon live demo
11. Streamlit dashboard - full UI with score card, bot matrix table, penalty breakdown, fix display
12. Fallback resilience - orchestrator gracefully falls back: Playwright -> requests -> rule-based
13. End-to-end integration tests - pytest suite verifying full pipeline against sandbox server
14. Unified data contract - run_audit() returns consistent schema regardless of which backend components are available

---

## 9. Features Currently Being Worked On / Open Items

- Deployment to Streamlit Cloud - requirements.txt and .streamlit/ are ready; Playwright needs playwright install chromium in cloud environment
- Gemini API key management - requires GEMINI_API_KEY in .env (see .env.example); remediation falls back gracefully if key is missing
- Historical audit storage - currently stateless (no database); each run is independent

---

## 10. Important Design Decisions & Why

| Decision | Rationale |
|----------|-----------|
| run_audit(url) as the single public API | The frontend developer (K) should not need to know any internal details. One function, one result. |
| Playwright for crawling, requests as fallback | Playwright gives realistic bot emulation (full JS, real browser fingerprint). Requests is the lightweight fallback for when Playwright is not available (e.g., serverless). |
| Scoring deduction system (start at 100, subtract) | More intuitive than additive scoring - shows clearly what is wrong rather than what is right. |
| Selective block penalty (-20 pts) | The most important signal - a site that blocks AI but not humans is deliberately choosing AI invisibility. Given a dedicated penalty. |
| Sandbox server for demo | Hackathon demos must not depend on external sites. The sandbox gives a 100% controllable, reliable before/after demonstration. |
| Kavish remediation over Samarth | Kavish uses the Gemini API for LLM-powered, context-aware fix generation which is more sophisticated and demo-ready. |
| Samarth Streamlit UI selected | Samarth built a more complete and polished UI that integrates crawler and remediation directly. |

---

## 11. Git Branch Structure & Integration History

### Branches

| Branch | Purpose | Status |
|--------|---------|--------|
| main | Original project base | Upstream, not directly modified |
| shloksabherwal1 | Integration branch - FINAL | Active, fully integrated |
| shlok | Shlok secondary branch (early push) | Merged into shloksabherwal1 |
| Samarth | Samarth crawler + Streamlit UI | Merged into shloksabherwal1 |
| gemini-kavish | Kavish Gemini remediation engine | Merged into shloksabherwal1 |
| crawler-anshul | Anshul crawler contributions | Referenced from main |

### Integration History (chronological)

```
8a23811  first commit                       <- project start
2939eab  branch commit                      <- Shlok branch init
1d3c485  feat(integrator): implement orchestrator, scoring engine, demo sandbox, tests, Streamlit dashboard
187af8c  fix(integrator): add ai_advisor and crawler modules
87ad251  feat(advisor): add main test runner to ai_advisor.py
fd626c3  Dashboard example                  <- Samarth dashboard
73e2377  build crawler and bot detection    <- Samarth/Anshul crawler
28a84bd  feat(shlok): complete self-contained integrator in shlok.py
83ac85a  Merge branch crawler-anshul into main
7f2a1ca  Commit for integration of crawler and basic remediation engine
cafd954  Add AI remediation engine and tests <- Kavish remediation
9de728f  feat(integration): merge Samarth crawler and Kavish remediation into shloksabherwal1  <- CURRENT HEAD
```

---

## 12. Which Components Came from Which Team Member

### Shlok (System Integrator) - this repo branch owner
- orchestrator.py - master pipeline, run_audit() function
- scoring.py - ScoringEngine class, 0-100 score calculation, all penalty weights
- sandbox/server.py - local Flask demo server (BEFORE/AFTER toggle)
- test_integration.py - end-to-end integration test suite
- ai_advisor.py - adapter bridging orchestrator to Kavish remediation engine
- shlok.py - self-contained backup/prototype (scoring + orchestrator + sandbox in one file)

### Samarth (Crawler + Frontend)
- dashboard.py - full Streamlit UI (AUTHORITATIVE frontend version)
- app.py - Streamlit entry point
- run_crawler.py - CLI crawler runner
- crawler/ - entire Playwright-based crawler package:
  - engine.py - CrawlerEngine (Playwright)
  - detector.py - BotBlockDetector
  - models.py - CrawlResult, BlockType
  - personas.py - AI persona definitions
  - robots.py - robots.txt inspector

### Kavish (AI Remediation Engine)
- remediation/ - entire Gemini-powered remediation package (AUTHORITATIVE):
  - engine.py - RemediationEngine + generate_remediation() using Gemini API
  - models.py - RemediationResult, BeforeAfterExample
  - normalizer.py - normalize_crawler_result(), IssueType, NormalizedAudit
  - prompt_builder.py - Gemini prompt construction

---

## 13. Important Integration Decisions

### Remediation: Kavish implementation was selected (NOT Samarth)
- Kavish remediation/ package uses Google Gemini API to generate intelligent, context-aware root cause analysis and fix recommendations. It is LLM-powered, structured with Pydantic models, and produces detailed BeforeAfterExample configuration comparisons.
- Samarth remediation was a simpler rule-based implementation and was dropped to avoid duplication.
- Kavish generate_remediation(crawler_result) is called via ai_advisor.py which acts as the adapter.

### UI: Samarth Streamlit implementation was selected
- Samarth built a complete, polished Streamlit UI in dashboard.py that integrates directly with the crawler and remediation modules. It includes score cards, bot matrix tables, penalty breakdowns, and remediation display.
- The original basic Streamlit view in shlok.py was replaced with Samarth implementation.

### Crawler: Both Samarth Playwright engine and Shlok lightweight requests fallback coexist
- The orchestrator first tries crawler.crawl_target(url) (Playwright-based, full detection)
- If crawler package is unavailable or raises an exception, falls back to built-in _fetch_with_agent() (requests-based)
- This ensures the system never fails completely even in restricted environments

---

## 14. Environment Setup & Running the Project

### Prerequisites
```
pip install -r requirements.txt
playwright install chromium
```

### Environment Variables
Copy .env.example to .env and set:
```
GEMINI_API_KEY=your_google_gemini_api_key_here
```

### Running the Streamlit Dashboard
```
streamlit run dashboard.py
```
or
```
streamlit run app.py
```

### Running the Integration Tests
```
python test_integration.py
```
or
```
pytest tests/
```

### Testing the Orchestrator Directly
```python
from orchestrator import run_audit
result = run_audit("https://example.com")
print(result["summary"])
```

### Running the Demo Sandbox Server
```python
from sandbox.server import start_sandbox, set_mode
start_sandbox(port=5050)    # starts on http://127.0.0.1:5050
set_mode("before")          # simulates AI-blocked site
set_mode("after")           # simulates AI-optimized site
```

---

## 15. Scoring System - Factor Reference

The ScoringEngine starts at 100 points and applies the following deductions:

| Factor | Penalty | Severity | Triggered When |
|--------|---------|----------|---------------|
| HTTP 403 Forbidden | -20 | CRITICAL | Any AI bot receives a 403 or blocked=True |
| HTTP 429 Too Many Requests | -10 | HIGH | Any AI bot is rate-limited |
| HTTP 5xx Server Error | -15 | HIGH | Server error during AI bot crawl |
| Anti-Bot WAF Challenge | -20 | CRITICAL | WAF detected AND actively blocking/challenging bots |
| Interactive CAPTCHA/Turnstile | -25 | CRITICAL | Turnstile, reCAPTCHA, hCAPTCHA detected in response |
| AI Bot Discrepancy | -20 | CRITICAL | Browser gets 200 OK, but AI bot gets blocked (selective block) |
| Robots.txt AI Disallow | -10 | MEDIUM | GPTBot/ClaudeBot/CCBot/PerplexityBot disallowed in robots.txt |
| High Response Latency (>3s) | -10 | LOW | Any endpoint responds slower than 3000ms |

Grade Thresholds:
- A (90-100): AI OPTIMIZED - all major AI search engines can crawl freely
- B (75-89): PARTIALLY ACCESSIBLE - minor friction, some coverage loss
- C (50-74): DEGRADED ACCESS - significant barriers harm AI visibility
- F (0-49): AI CRAWL BLOCKED - site is effectively invisible to AI search

---

Generated by Antigravity AI | System Integrator Branch: shloksabherwal1
