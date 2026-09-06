# AI Crawl Optimizer — Integration Contract (Checkpoint 2)

> **Owner**: Anshul (Crawler + Bot Detection)  
> **Target Audience**: Shlok (Orchestration & Scoring), Kavish (AI Remediation), Samarth (Streamlit UI)  
> **Status**: Frozen / Source of Truth

---

## 1. Exact Import Statement

For synchronous environments (e.g. Streamlit, standard synchronous scripts):
```python
from crawler import crawl_sync
```

For asynchronous environments (e.g. asyncio pipelines, async orchestrators):
```python
from crawler import crawl_url
```

For multi-persona and baseline auditing:
```python
from crawler import crawl_with_baseline, crawl_all_personas, list_personas, get_persona
```

---

## 2. Exact Function for Single URL + Persona Audit

### Primary Synchronous Function (Recommended for Streamlit & Orchestration):
```python
crawl_sync(url: str, persona: str = "gptbot", **kwargs) -> dict
```

### Primary Asynchronous Function:
```python
await crawl_url(url: str, persona: str = "gptbot", **kwargs) -> dict
```

---

## 3. Exact Arguments Accepted

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | *(Required)* | Target website URL (e.g. `"https://docs.stripe.com"`). If scheme is missing, `"https://"` is automatically prepended. |
| `persona` | `str` | `"gptbot"` | Identifier of the bot to simulate (case-insensitive). Built-in personas: `"gptbot"`, `"oai_searchbot"`, `"claudebot"`, `"anthropic_ai"`, `"perplexitybot"`, `"google_extended"`, `"bytespider"`, `"cohere"`, `"ccbot"`, `"standard_browser"`, or any custom User-Agent string. |
| `headless` | `bool` | `True` | Whether Playwright runs Chromium in headless mode. |
| `timeout_seconds` | `float` | `15.0` | Maximum page navigation timeout in seconds. |
| `wait_after_load_ms` | `int` | `1500` | Milliseconds to wait after `DOMContentLoaded` to allow dynamic JS challenges / Turnstile to render. |

---

## 4. Exact Return Structure

Both `crawl_sync(...)` and `crawl_url(...)` return a standard Python `dict` containing JSON-primitive values:

```python
{
    "target_url": str,
    "persona": str,
    "user_agent": str,
    "timestamp": str,               # ISO 8601 UTC
    "success": bool,                # True if browser executed without fatal crash
    "error": Optional[str],         # Error message if success == False

    # robots.txt Evaluation
    "robots_txt": {
        "exists": bool,
        "url": str,
        "status_code": Optional[int],
        "is_allowed": bool,         # RFC 9309 rule evaluation for target URL
        "matching_rule": Optional[str], # e.g. "Disallow: /" or "Allow: /docs"
        "crawl_delay": Optional[float], # In seconds, if declared
        "sitemaps": List[str],      # Sitemap URLs extracted
        "ai_specific_rules": Dict[str, Any], # Rules found for other AI agents
        "raw_content": Optional[str] # Truncated text of robots.txt
    },

    # Network / HTTP Observation
    "http": {
        "status_code": Optional[int],    # e.g. 200, 403, 429, 503
        "final_url": str,
        "redirect_count": int,
        "redirects": List[str],
        "headers": Dict[str, str],       # Lowercased response headers
        "content_type": Optional[str],
        "response_time_ms": Optional[float], # Total navigation latency
        "server": Optional[str],         # e.g. "cloudflare", "nginx"
        "x_robots_tag": Optional[str]    # e.g. "noindex, noai"
    },

    # Rendered DOM Observation
    "page": {
        "title": Optional[str],
        "meta_tags": Dict[str, str],     # Dict of all meta name/property -> content
        "text_length": int,              # Visible text character count
        "snippet": str,                  # First 1000 characters of clean text
        "has_javascript_requirement": bool # True if "enable javascript" prompt found
    },

    # Detection & Analysis
    "detection": {
        # DIRECT OBSERVATIONS ONLY
        "evidence": {
            "status_code": Optional[int],
            "matched_headers": List[str],   # e.g. ["cf-ray: ...", "server: cloudflare"]
            "dom_signals": List[str],       # e.g. [".cf-turnstile", "#challenge-form"]
            "matched_keywords": List[str],  # e.g. ["just a moment...", "403 Forbidden"]
            "page_title": Optional[str],
            "snippet_preview": Optional[str]
        },
        # INFERRED CONCLUSIONS
        "inference": {
            "verdict": str,      # "ACCESSIBLE" | "CHALLENGED" | "BLOCKED" | "INCONCLUSIVE"
            "mechanism": str,    # "NONE" | "CLOUDFLARE_CHALLENGE" | "CLOUDFLARE_BLOCK" |
                                 # "DATADOME" | "PERIMETERX" | "AWS_WAF" | "AKAMAI" |
                                 # "RECAPTCHA" | "HCAPTCHA" | "HTTP_FORBIDDEN" |
                                 # "HTTP_429_RATE_LIMITED" | "HTTP_503_SERVICE_UNAVAILABLE" |
                                 # "CUSTOM_BOT_BLOCK"
            "confidence": float, # 0.0 to 1.0
            "summary": str       # Explanatory diagnosis string
        },
        # Backwards compatibility fields:
        "is_blocked": bool,
        "block_type": str,
        "confidence": float,
        "signals": List[str]
    }
}
```

---

## 5. Fields for Shlok (Orchestration & Scoring)

| Field Path | Type | Purpose in Scoring Engine |
|---|---|---|
| `detection["inference"]["verdict"]` | `str` | Primary multiplier (`"ACCESSIBLE"` = 1.0, `"CHALLENGED"` = 0.25, `"BLOCKED"` = 0.0, `"INCONCLUSIVE"` = 0.50). |
| `detection["inference"]["confidence"]` | `float` | Weight confidence factor for risk calculations. |
| `detection["inference"]["mechanism"]` | `str` | Penalize specific mechanisms (e.g. WAF vs Rate Limit vs Permissions). |
| `robots_txt["is_allowed"]` | `bool` | Hard compliance flag: 0 crawl score if `False`. |
| `http["status_code"]` | `int` | Direct HTTP status metric (200 = OK, 403 = Forbidden, 429 = Rate Limited). |
| `http["response_time_ms"]` | `float` | Crawl latency score (fast vs sluggish response). |
| `page["text_length"]` | `int` | Content accessibility: zero characters indicates blank page or blocked content. |
| `page["has_javascript_requirement"]`| `bool` | Penalize client-side-only rendering for simple HTTP AI agents. |

---

## 6. Fields for Kavish (AI Remediation Engine)

| Field Path | Type | Purpose in Remediation / Gemini Prompts |
|---|---|---|
| `detection["evidence"]` | `dict` | Direct proof to inject into prompt (`matched_headers`, `dom_signals`, `matched_keywords`). |
| `detection["inference"]["summary"]` | `str` | High-level diagnostic context to explain *why* the page failed. |
| `detection["inference"]["mechanism"]` | `str` | Used to select remediation template (e.g. Cloudflare WAF allowlist vs. robots.txt fix). |
| `robots_txt["raw_content"]` | `str` | Input to Gemini for generating a corrected `robots.txt` diff. |
| `robots_txt["matching_rule"]` | `str` | Explains which rule triggered disallow. |
| `http["x_robots_tag"]` | `str` | Remediation for HTTP response headers (removing `noai` / `noindex`). |
| `page["meta_tags"]` | `dict` | Remediation for HTML `<meta name="robots">` tags. |

---

## 7. Fields for Samarth (Streamlit UI)

| Field Path | UI Component |
|---|---|
| `detection["inference"]["verdict"]` | Top banner badge: Green (`ACCESSIBLE`), Yellow (`CHALLENGED`), Red (`BLOCKED`), Gray (`INCONCLUSIVE`). |
| `detection["inference"]["summary"]` | Diagnostic callout box. |
| `robots_txt["is_allowed"]` | Status pill: `Allowed` or `Disallowed`. |
| `robots_txt["matching_rule"]` | Subtitle displaying active rule (e.g. `Disallow: /private/`). |
| `http["status_code"]` & `http["response_time_ms"]` | Quick metric gauges: Status (e.g. 200) and Latency (e.g. 340 ms). |
| `page["title"]` & `page["snippet"]` | Collapsible "Crawled Content Preview" expander. |
| `detection["evidence"]` | Collapsible "Technical Evidence & Headers" expander. |
| `selective_ai_block_detected` *(baseline mode)* | Warning banner: *"This site discriminates against AI bots while allowing standard browsers."* |

---

## 8. Performing Browser-Baseline Comparison

To detect whether a site selectively discriminates against AI bots:

```python
import asyncio
from crawler import crawl_with_baseline

async def run_audit():
    result = await crawl_with_baseline("https://example.com", persona="gptbot")
    
    # Returns:
    # {
    #     "url": "https://example.com",
    #     "target_persona": {...},      # Full CrawlResult dict for gptbot
    #     "baseline_browser": {...},    # Full CrawlResult dict for standard_browser
    #     "selective_ai_block_detected": bool
    # }
    if result["selective_ai_block_detected"]:
        print("ALERT: AI agent is blocked while standard desktop browser is permitted!")
```

---

## 9. Running Multiple AI Personas

To test a URL across all supported AI bots (`gptbot`, `claudebot`, `perplexitybot`, etc.):

```python
import asyncio
from crawler import crawl_all_personas

async def run_multi():
    # Audits all registered AI personas
    results = await crawl_all_personas("https://example.com")
    
    for r in results:
        print(f"Persona: {r['persona']} -> Verdict: {r['detection']['inference']['verdict']}")
```

To list all available personas:
```python
from crawler import list_personas
personas = list_personas()  # Returns list of dicts with id, display_name, user_agent
```

---

## 10. Verdict Definitions

The crawler assigns one of four standardized verdicts:

1. **`ACCESSIBLE`**:
   - The webpage responded with HTTP 200 (or normal redirect).
   - Rendered readable content.
   - Zero anti-bot signatures, WAF challenges, or CAPTCHA elements were found.

2. **`CHALLENGED`**:
   - An interactive anti-bot interstitial was triggered (e.g. Cloudflare Turnstile, DataDome, PerimeterX, AWS WAF captcha, reCAPTCHA, hCaptcha).
   - The crawler was prevented from accessing the actual underlying page content without solving an interactive challenge.

3. **`BLOCKED`**:
   - Active, explicit blocking was confirmed.
   - Examples: Cloudflare Error 1020/1015, HTTP 429 Rate Limit, Akamai access denied reference format, or explicit anti-bot wording (*"bot traffic detected"*, *"automated access is prohibited"*).

4. **`INCONCLUSIVE`**:
   - Access failed or was restricted, but there is **no direct evidence** that the failure is targeted specifically at AI crawlers.
   - Example: A standalone HTTP 403 Forbidden without any WAF/bot headers or challenge widgets. (Could be an intranet page, auth-walled route, or geographic block).

---

## 11. Important Interpretation Rule (HTTP 403 Semantics)

> **RULE**: A standalone HTTP 403 must **NOT** be claimed as proof that a site specifically blocks AI crawlers.

- A standalone HTTP 403 sets:
  - `evidence["status_code"] = 403`
  - `inference["verdict"] = "INCONCLUSIVE"`
  - `inference["mechanism"] = "HTTP_FORBIDDEN"`
  - `inference["confidence"] = 0.35`
  - `is_blocked = False`
- Only if the 403 is accompanied by WAF headers (e.g. `cf-ray`), challenge DOM elements, or explicit bot notification text will the verdict become `BLOCKED` or `CHALLENGED` with high confidence.

---

## 12. Minimal Working Example

```python
from crawler import crawl_sync

# Single URL audit using OpenAI GPTBot
result = crawl_sync("https://httpbin.org/status/200", persona="gptbot")

print("URL:       ", result["target_url"])
print("Allowed:   ", result["robots_txt"]["is_allowed"])
print("HTTP Code: ", result["http"]["status_code"])
print("Verdict:   ", result["detection"]["inference"]["verdict"])
print("Summary:   ", result["detection"]["inference"]["summary"])
```

---

## 13. Example for Shlok (Scoring / Orchestration)

```python
from crawler import crawl_sync

def score_crawl(url: str, persona: str = "gptbot") -> dict:
    crawl_data = crawl_sync(url, persona=persona)
    
    verdict = crawl_data["detection"]["inference"]["verdict"]
    is_allowed = crawl_data["robots_txt"]["is_allowed"]
    latency = crawl_data["http"]["response_time_ms"] or 0
    text_len = crawl_data["page"]["text_length"]
    
    # Calculate Accessibility Score (0 - 100)
    score = 100
    if not is_allowed:
        score -= 40
    if verdict == "BLOCKED":
        score -= 50
    elif verdict == "CHALLENGED":
        score -= 40
    elif verdict == "INCONCLUSIVE":
        score -= 20
    if latency > 3000:
        score -= 10
    if text_len == 0:
        score -= 10

    score = max(0, min(100, score))

    return {
        "url": url,
        "persona": persona,
        "score": score,
        "verdict": verdict,
        "crawl_data": crawl_data
    }
```

---

## 14. Example for Kavish (AI Remediation)

```python
def build_remediation_prompt(crawl_data: dict) -> str:
    inference = crawl_data["detection"]["inference"]
    evidence = crawl_data["detection"]["evidence"]
    robots = crawl_data["robots_txt"]

    prompt = f"""
You are an expert web infrastructure engineer.
Audit findings for website: {crawl_data['target_url']}
AI Crawler Persona: {crawl_data['persona']}

Diagnostic Verdict: {inference['verdict']}
Blocking Mechanism: {inference['mechanism']}
Summary: {inference['summary']}

Evidence Gathered:
- HTTP Status: {evidence['status_code']}
- Detected Headers: {evidence['matched_headers']}
- DOM Signals: {evidence['dom_signals']}
- Matched Keywords: {evidence['matched_keywords']}

Robots.txt status:
- Is Allowed: {robots['is_allowed']}
- Triggering Rule: {robots['matching_rule']}
- Content snippet:
{robots['raw_content']}

Task:
1. Explain why this website is inaccessible to {crawl_data['persona']}.
2. Provide exact code or configuration changes (e.g. Cloudflare WAF rules, robots.txt update) to safely allow verified AI agents while preventing malicious scrapers.
"""
    return prompt
```

---

## 15. Example for Samarth (Streamlit UI calling Orchestrator)

Samarth's Streamlit frontend calls Shlok's orchestration layer directly without needing to know crawler internals. The orchestration layer runs the crawler, computes scores/risk, and integrates Kavish's remediation.

```python
import streamlit as st
from orchestration import run_audit

def render_ui():
    st.title("AI Crawl Optimizer")
    url = st.text_input("Enter Website URL", value="https://example.com")
    persona = st.selectbox("Select AI Persona", ["gptbot", "claudebot", "perplexitybot"])
    
    if st.button("Run Audit"):
        with st.spinner("Auditing website accessibility..."):
            # Single call to the orchestration layer
            audit = run_audit(url, persona=persona)

            # Combined integration result returned by orchestration:
            # - audit["score"]        -> Integer (0 - 100)
            # - audit["risk_level"]   -> "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
            # - audit["crawl_data"]   -> Full CrawlResult dict from the crawler
            # - audit["remediation"]  -> Actionable code / config guidance from Gemini

            crawl = audit["crawl_data"]
            verdict = crawl["detection"]["inference"]["verdict"]
            summary = crawl["detection"]["inference"]["summary"]

            # 1. Display Score & Risk Level
            col1, col2 = st.columns(2)
            col1.metric("Accessibility Score", f"{audit['score']} / 100")
            col2.metric("Risk Level", audit["risk_level"])

            # 2. Display Verdict
            if verdict == "ACCESSIBLE":
                st.success(f"**{verdict}**: {summary}")
            elif verdict == "CHALLENGED":
                st.warning(f"**{verdict}**: {summary}")
            elif verdict == "BLOCKED":
                st.error(f"**{verdict}**: {summary}")
            else:
                st.info(f"**{verdict}**: {summary}")

            # 3. Crawled Content Preview
            with st.expander("Page Preview"):
                st.write("**Title:**", crawl["page"]["title"])
                st.write("**Text Snippet:**", crawl["page"]["snippet"][:300])

            # 4. AI Remediation Guidance
            if audit.get("remediation"):
                with st.expander("AI Remediation Recommendations", expanded=True):
                    st.markdown(audit["remediation"])
```
