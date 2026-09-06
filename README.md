# AI Crawl Optimizer ⚡

> Audit, diagnose, and optimize websites for AI search engine crawlers (ChatGPT Search, Claude, Perplexity, CCBot).

---

## 👥 Team & Architecture Overview

| Member | Focus Area | Interface / File | Responsibility |
|---|---|---|---|
| **K** | **Frontend (Streamlit)** | `app.py` | UI dashboard, metrics cards, bot matrix table, remediation display |
| **A** | **Crawler** | `crawler.py` | Multi-agent fetcher, header extraction, proxy/stealth mechanics |
| **S** | **AI Diagnosis** | `ai_advisor.py` | Root-cause analysis, Cloudflare WAF rule generation, fix synthesis |
| **Sh (You)** | **System Integrator** | `orchestrator.py`, `scoring.py`, `sandbox/` | Connects all components, mathematical scoring engine, demo sandbox, integration testing, and deployment |

---

## 🚀 Quick Start

### 1. Installation
```bash
git checkout shlok
pip install -r requirements.txt
```

### 2. Run the Full Streamlit Dashboard
```bash
streamlit run app.py
```
This launches the web UI and automatically starts the local Enterprise Demo Sandbox on `http://127.0.0.1:5050`.

### 3. Run Integration Tests
```bash
python test_integration.py
```
Verifies both **BEFORE** (Grade F, 403 Forbidden on AI bots) and **AFTER** (Grade A, 200 OK on AI bots) modes end-to-end.

---

## 🔌 Developer Contracts & Integration

### For K (Frontend Developers)
Import the master audit function:
```python
from orchestrator import run_audit

result = run_audit("https://your-target-url.com")
```
`result` returns a clean, typed dictionary:
```json
{
  "url": "https://...",
  "timestamp": "2026-09-06T16:30:00Z",
  "summary": {
    "score": 100,
    "grade": "A",
    "status": "AI OPTIMIZED",
    "color": "#10B981",
    "text": "Excellent AI crawlability! Search agents can index seamlessly."
  },
  "scoring": {
    "base_score": 100,
    "total_deductions": 0,
    "penalties": []
  },
  "bot_matrix": {
    "browser_chrome": {"status": 200, "blocked": false, "latency_ms": 18},
    "gpt_bot": {"status": 200, "blocked": false, "latency_ms": 7},
    "claude_bot": {"status": 200, "blocked": false, "latency_ms": 6}
  },
  "ai_recommendations": {
    "root_cause": "...",
    "cloudflare_waf_rule": "...",
    "robots_txt_fix": "...",
    "action_items": ["..."]
  }
}
```

### For A (Crawler Developers)
Create `crawler.py` with:
```python
def crawl_target(url: str) -> dict:
    return {
        "bots": {
            "browser_chrome": {"status": 200, "latency_ms": 120, "blocked": False},
            "gpt_bot": {"status": 403, "latency_ms": 90, "blocked": True, "waf": "Cloudflare", "captcha": True},
            ...
        }
    }
```
`orchestrator.py` will automatically import and invoke it if present.

### For S (AI Developers)
Create `ai_advisor.py` with:
```python
def generate_recommendations(scoring_result: dict, audit_context: dict) -> dict:
    return {
        "root_cause": "...",
        "cloudflare_waf_rule": "...",
        "robots_txt_fix": "...",
        "action_items": ["..."]
    }
```
`orchestrator.py` will automatically use your custom AI model.

---

## 🎪 The Pitch & Demo Strategy (Live Sandbox)

The sandbox provides a **100% fail-safe demo** during presentations:

1. **Start the Demo**:
   - Open `app.py` in your browser.
   - Show that the target is set to the Demo Sandbox (`http://127.0.0.1:5050`).
2. **Audit BEFORE (The Problem)**:
   - Make sure Sandbox is in `BEFORE` mode.
   - Click **Run Audit**.
   - **Show the Audience**:
     - Browser gets `200 OK` (human visitors are happy).
     - ChatGPT (`GPTBot`), Claude (`ClaudeBot`), and Perplexity (`PerplexityBot`) receive `403 Forbidden` with Cloudflare Challenge!
     - Score drops to **`0/100 (Grade F - AI CRAWL BLOCKED)`**.
     - Explain: *"This company is completely invisible to generative AI search!"*
3. **The Solution (AI Optimization)**:
   - Scroll down to the **AI Remediation Panel**.
   - Show the generated Cloudflare WAF bypass rule and updated `robots.txt`.
4. **Audit AFTER (The Transformation)**:
   - Click **Set AFTER** in the sidebar.
   - Click **Run Audit**.
   - Score jumps to **`100/100 (Grade A - AI OPTIMIZED)`**!
   - Every AI crawler gets `200 OK` with zero latency penalties.
