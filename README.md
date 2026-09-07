# AI Crawl Optimizer

AI Crawl Optimizer is a platform for auditing and analyzing website accessibility for AI crawlers.

As AI-powered search and discovery systems become increasingly important, websites need to understand whether automated AI agents can access their content. A website may be fully accessible to normal users while AI crawlers are blocked by robots.txt policies, WAFs, CAPTCHAs, Cloudflare challenges, rate limits, or other security mechanisms.

AI Crawl Optimizer helps identify these issues, measure their impact, and provide actionable recommendations.

---

## Problem Statement

When AI systems attempt to access web content through automated crawlers, their requests may be treated as bot traffic and blocked by website security infrastructure.

Common causes include:

- `robots.txt` restrictions
- HTTP 401, 403, 429, or 503 responses
- Web Application Firewalls
- Cloudflare challenges and bot protection
- CAPTCHAs
- Rate limiting
- Custom bot detection mechanisms
- JavaScript-dependent access restrictions

Website owners need to understand:

1. Which AI crawlers are affected?
2. What mechanism is causing the restriction?
3. Is the problem specific to AI crawlers or does it affect normal browsers as well?
4. How does the issue affect overall AI accessibility?
5. What can be done to resolve it?

AI Crawl Optimizer addresses these questions through automated crawling, evidence-based detection, scoring, and remediation.

---

## Features

### Multi-Persona AI Crawling

The platform simulates different AI crawler personas and evaluates how a website responds to each one.

Supported personas include:

- GPTBot
- ClaudeBot
- PerplexityBot
- Google-Extended
- CCBot

A standard browser persona is also used as a baseline for comparison.

### Robots.txt Analysis

The crawler fetches and analyzes the website's `robots.txt` file.

It evaluates:

- Whether `robots.txt` exists
- Whether a specific crawler is allowed
- Matching Allow and Disallow rules
- AI-specific directives
- Crawl delays
- Sitemap declarations

### Browser-Based Crawling

The crawling engine uses Playwright to perform browser-based website access.

For each crawl, the system collects:

- HTTP status code
- Response headers
- Redirects
- Final URL
- Response time
- Page title
- Page content
- Meta tags
- JavaScript requirements

### Bot and Block Detection

The detection engine analyzes HTTP and page-level evidence to identify possible access restrictions.

Supported detection categories include:

- Cloudflare challenges
- Cloudflare blocks
- DataDome
- PerimeterX
- Akamai
- AWS WAF
- reCAPTCHA
- hCaptcha
- HTTP Forbidden responses
- Rate limiting
- Service unavailability
- Custom bot blocking

The system separates raw evidence from inferred conclusions to make results transparent.

Example:

    Evidence:
    - HTTP Status: 403
    - Cloudflare-related response signals detected

    Inference:
    - Verdict: BLOCKED
    - Mechanism: CLOUDFLARE_CHALLENGE
    - Confidence: High

### Browser Baseline Comparison

AI Crawl Optimizer compares AI crawlers against a standard browser baseline.

For example:

| Agent | Result |
|---|---|
| Standard Browser | Accessible |
| GPTBot | Blocked |

If a normal browser can access the website but an AI crawler cannot, the system can flag this as potential selective AI blocking.

### AI Accessibility Scoring

The scoring engine generates an AI Accessibility Score out of 100.

Potential factors include:

- AI crawler blocking
- Robots.txt restrictions
- CAPTCHA challenges
- WAF interference
- HTTP access failures
- Rate limiting
- Selective AI blocking

The scoring system provides:

- Final score
- Grade
- Risk level
- Detected issues
- Point deductions
- Scoring summary

### Point Deduction Tracker

The platform provides a transparent view of how the final score was calculated.

Instead of presenting a black-box score, the deduction tracker shows which issues contributed to score reductions.

Example:

    Base Score: 100

    AI Crawler Blocked          -30
    robots.txt Restriction      -20
    CAPTCHA Detected            -15

    Final Score: 35

### Remediation Recommendations

After identifying an issue, the remediation engine provides recommendations based on crawler results.

Recommendations can include:

- Identified problem
- Impact on AI crawling
- Recommended fix
- Observed evidence
- Configuration suggestions
- Validation steps

---

## Architecture

    Website URL
         |
         v
    AI Crawl Optimizer
         |
         v
    Crawler Persona Selection
         |
    +----+----+
    |    |    |
    v    v    v
    GPT  Claude Perplexity
    Bot  Bot    Bot
         |
         v
    Crawling Engine
      (Playwright)
         |
         v
    Evidence Collection
         |
    +----+----+----+
    |    |    |
    v    v    v
    HTTP Page robots.txt
         |
         v
    Detection Engine
         |
         v
    Scoring Engine
         |
         v
    Remediation Engine
         |
         v
    Streamlit Dashboard

---

## Project Structure

    Ai-crawl-optimizer/
    │
    ├── crawler/
    │   ├── __init__.py
    │   ├── engine.py
    │   ├── detector.py
    │   ├── models.py
    │   ├── personas.py
    │   └── robots.py
    │
    ├── remediation/
    ├── tests/
    │   └── test_scoring.py
    │
    ├── demo_streaming_site/
    │
    ├── dashboard.py
    ├── orchestration.py
    ├── orchestrator.py
    ├── scoring.py
    ├── remediation_engine.py
    ├── ai_advisor.py
    ├── run_crawler.py
    ├── requirements.txt
    ├── pyproject.toml
    └── README.md

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application |
| Streamlit | Dashboard and user interface |
| Playwright | Browser-based crawling |
| HTTPX | HTTP requests and robots.txt fetching |
| Pydantic | Structured data models |
| Pytest | Testing |
| Gemini | Optional AI-assisted remediation |

---

## Installation

### Clone the repository

    git clone https://github.com/BL147/Ai-crawl-optimizer.git
    cd Ai-crawl-optimizer

### Create a virtual environment

macOS / Linux:

    python3 -m venv .venv
    source .venv/bin/activate

Windows:

    python -m venv .venv
    .venv\Scripts\activate

### Install dependencies

    pip install -r requirements.txt

### Install Playwright

    playwright install chromium

---

## Running the Application

Start the Streamlit dashboard:

    streamlit run dashboard.py

---

## Running Tests

Run the scoring tests:

    pytest -q tests/test_scoring.py

---

## Usage

1. Start the Streamlit application.
2. Enter a website URL.
3. Select one or more AI crawler personas.
4. Run the audit.
5. Review the crawler results.
6. Check the AI Accessibility Score.
7. Review the point deduction tracker.
8. Compare results with the browser baseline.
9. Review remediation recommendations.

---

## Programmatic Usage

The audit pipeline can also be accessed directly through Python.

    from orchestration import run_audit

    result = run_audit(
        "https://example.com",
        persona="gptbot",
        include_baseline=True
    )

    print(result)

The pipeline performs:

    URL
     |
     v
    Crawler
     |
     v
    Detection
     |
     v
    Scoring
     |
     v
    Remediation
     |
     v
    Structured Result

---

## Example Output

An audit result includes information about:

- Target URL
- Crawler Persona
- Crawl Success
- HTTP Status
- Response Time
- robots.txt Rules
- Detection Verdict
- Detection Mechanism
- Confidence
- Accessibility Score
- Grade
- Risk Level
- Point Deductions
- Remediation Recommendations

---

## Use Cases

### Website Owners

Understand whether AI crawlers can access website content.

### Developers

Identify technical configurations that affect automated AI access.

### Security Teams

Determine whether security systems unintentionally block AI crawlers.

### AI Visibility and SEO Teams

Evaluate website accessibility for AI-driven search and discovery systems.

### Researchers

Analyze how websites respond to different automated crawler identities.

---

## Future Improvements

- Historical audit tracking
- Scheduled monitoring
- More AI crawler personas
- Multi-page website audits
- Sitemap crawling
- Detailed WAF fingerprinting
- API access
- Accessibility trend analysis
- Automated remediation validation

---

## Core Objective

AI Crawl Optimizer is designed to answer three questions:

1. Can AI crawlers access a website?
2. If not, what is preventing access?
3. What can be done to improve accessibility?

By combining crawler simulation, robots.txt analysis, browser comparison, block detection, scoring, and remediation, the platform provides a structured way to analyze website accessibility for AI crawlers.

---

## License

This project was developed as part of a hackathon project.
