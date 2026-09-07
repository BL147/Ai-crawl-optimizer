import os
import time
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional

import streamlit as st
import pandas as pd

from crawler import list_personas
from orchestration import run_audit
from scoring import calculate_score

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & METADATA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Crawl Optimizer | AI Accessibility & Bot Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# ENVIRONMENT & API DETECTION
# -----------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

has_gemini_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY"))

# -----------------------------------------------------------------------------
# FIGMA-QUALITY CYBERSECURITY SAAS DESIGN SYSTEM (CSS)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url("https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap");

    :root {
        --bg-main: #07090e;
        --bg-card: #0f172a;
        --bg-card-hover: #131f37;
        --border-color: rgba(255, 255, 255, 0.08);
        --border-active: rgba(99, 102, 241, 0.4);
        --accent-indigo: #6366f1;
        --accent-cyan: #06b6d4;
        --accent-blue: #3b82f6;
        --accent-purple: #8b5cf6;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --status-accessible: #10b981;
        --status-blocked: #ef4444;
        --status-inconclusive: #f59e0b;
    }

    /* Streamlit Root Reset & Overrides */
    .stApp {
        background-color: var(--bg-main);
        font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-primary);
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 4rem !important;
        max-width: 1200px !important;
    }

    /* Top Navigation Bar */
    .top-nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.9rem 1.6rem;
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        backdrop-filter: blur(16px);
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }
    .brand-group {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .brand-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 50%, #8b5cf6 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        box-shadow: 0 0 16px rgba(99, 102, 241, 0.4);
    }
    .brand-text {
        font-weight: 800;
        font-size: 1.2rem;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #ffffff 30%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .brand-badge {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.2rem 0.65rem;
        border-radius: 9999px;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.3);
        color: #a5b4fc;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .nav-links {
        display: flex;
        align-items: center;
        gap: 1.6rem;
    }
    .nav-item {
        font-size: 0.88rem;
        font-weight: 600;
        color: var(--text-secondary);
        text-decoration: none;
        transition: color 0.15s ease;
    }
    .nav-item:hover, .nav-item.active {
        color: #ffffff;
    }
    .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.82rem;
        font-weight: 600;
        padding: 0.35rem 0.9rem;
        border-radius: 9999px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.28);
        color: #34d399;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10b981;
        box-shadow: 0 0 8px #10b981;
    }

    /* Hero Section */
    .hero-card {
        background: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.14) 0%, transparent 45%),
                    radial-gradient(circle at 90% 30%, rgba(139, 92, 246, 0.14) 0%, transparent 45%),
                    linear-gradient(180deg, #0e1628 0%, #080c16 100%);
        border: 1px solid var(--border-color);
        border-radius: 20px;
        padding: 2.8rem 2.8rem 2.2rem 2.8rem;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 15px 35px -10px rgba(0, 0, 0, 0.5);
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        line-height: 1.18;
        margin-bottom: 0.85rem;
        background: linear-gradient(135deg, #ffffff 40%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        font-size: 1.08rem;
        color: var(--text-secondary);
        max-width: 820px;
        line-height: 1.6;
        margin-bottom: 1.2rem;
    }
    .hero-caption {
        font-size: 0.86rem;
        color: var(--text-muted);
    }

    /* Streamlit Form & Controls Polish */
    div[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    .config-card {
        background: #0d1424;
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.6rem 1.8rem;
        margin-bottom: 1.5rem;
    }
    .config-header {
        font-size: 0.88rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-secondary);
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Crawler Chips Section */
    .crawler-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.9rem;
        margin-top: 1rem;
        margin-bottom: 2rem;
    }
    .crawler-chip {
        background: #0f172a;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 0.85rem 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .crawler-chip:hover {
        border-color: var(--border-active);
        transform: translateY(-2px);
    }
    .crawler-chip-name {
        font-size: 0.9rem;
        font-weight: 700;
        color: #f1f5f9;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .crawler-chip-desc {
        font-size: 0.74rem;
        color: var(--text-muted);
        line-height: 1.35;
    }
    .crawler-chip-status {
        font-size: 0.68rem;
        font-weight: 700;
        color: #38bdf8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* KPI Summary Metric Cards */
    .kpi-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin-bottom: 1.8rem;
    }
    .kpi-card {
        background: #0e1628;
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 1.3rem 1.4rem;
        position: relative;
        overflow: hidden;
    }
    .kpi-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0; height: 2px;
    }
    .kpi-card-acc::before { background: #10b981; }
    .kpi-card-blk::before { background: #ef4444; }
    .kpi-card-inc::before { background: #f59e0b; }
    .kpi-card-iss::before { background: #6366f1; }

    .kpi-label {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-muted);
        margin-bottom: 0.4rem;
    }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -0.04em;
    }
    .kpi-value-acc { color: #34d399; }
    .kpi-value-blk { color: #f87171; }
    .kpi-value-inc { color: #fbbf24; }
    .kpi-value-iss { color: #a5b4fc; }
    .kpi-subtext {
        font-size: 0.75rem;
        color: var(--text-secondary);
        margin-top: 0.4rem;
    }

    /* Overall Score Visualizer */
    .score-banner {
        background: linear-gradient(135deg, #0e162a 0%, #090e1c 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 18px;
        padding: 2.2rem 2.4rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.8rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 15px 30px -10px rgba(0, 0, 0, 0.45);
    }
    .score-banner::after {
        content: "";
        position: absolute;
        top: 0; left: 0; width: 4px; height: 100%;
        background: linear-gradient(180deg, #3b82f6 0%, #6366f1 50%, #8b5cf6 100%);
    }
    .score-circle-group {
        display: flex;
        align-items: baseline;
        gap: 0.4rem;
    }
    .score-big-num {
        font-size: 5rem;
        font-weight: 900;
        letter-spacing: -0.06em;
        line-height: 0.9;
        background: linear-gradient(180deg, #ffffff 40%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .score-denom {
        font-size: 1.5rem;
        color: var(--text-muted);
        font-weight: 700;
    }
    .score-meta-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    .score-headline {
        font-size: 1.25rem;
        font-weight: 800;
        color: #ffffff;
    }
    .score-diagnosis {
        font-size: 0.92rem;
        color: var(--text-secondary);
        max-width: 620px;
        line-height: 1.5;
    }
    .badge-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.35rem 0.9rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .badge-low-risk {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-med-risk {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .badge-high-risk {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }

    /* Remediation Card */
    .remediation-card {
        background: linear-gradient(145deg, #0e172a 0%, #080d19 100%);
        border: 1px solid rgba(99, 102, 241, 0.35);
        border-radius: 18px;
        padding: 2.2rem 2.4rem;
        margin-top: 1.5rem;
        box-shadow: 0 15px 35px -8px rgba(0, 0, 0, 0.5);
    }
    .rem-section-title {
        font-size: 0.8rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #818cf8;
        margin-top: 1.2rem;
        margin-bottom: 0.4rem;
    }
    .rem-text {
        font-size: 0.95rem;
        color: #e2e8f0;
        line-height: 1.6;
    }

    /* Trust Pipeline */
    .trust-pipeline {
        background: #0c1220;
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.8rem 2rem;
        margin-top: 2.5rem;
        margin-bottom: 2rem;
    }
    .pipeline-steps {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 1.2rem;
        margin-bottom: 1.2rem;
        gap: 0.5rem;
        overflow-x: auto;
    }
    .pipeline-node {
        background: #111a2e;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        text-align: center;
        min-width: 140px;
    }
    .pipeline-node-title {
        font-size: 0.82rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .pipeline-node-sub {
        font-size: 0.7rem;
        color: var(--text-muted);
    }
    .pipeline-arrow {
        color: #4f46e5;
        font-size: 1.2rem;
        font-weight: 800;
    }

    /* How It Works Grid */
    .how-it-works-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.2rem;
        margin-top: 1rem;
        margin-bottom: 2.5rem;
    }
    .hiw-step-card {
        background: #0d1424;
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 1.4rem;
        position: relative;
    }
    .hiw-step-num {
        font-size: 0.75rem;
        font-weight: 800;
        color: #6366f1;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    .hiw-step-title {
        font-size: 1rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.45rem;
    }
    .hiw-step-desc {
        font-size: 0.82rem;
        color: var(--text-secondary);
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# TOP NAVIGATION & BRANDING HEADER
# -----------------------------------------------------------------------------
status_pill = (
    '<span class="status-indicator"><span class="status-dot"></span> Gemini 2.5 Active</span>'
    if has_gemini_key
    else '<span class="status-indicator" style="background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.25); color: #a5b4fc;"><span class="status-dot" style="background:#6366f1; box-shadow:0 0 8px #6366f1;"></span> Grounded Engine Ready</span>'
)

st.markdown(f"""
<div class="top-nav">
    <div class="brand-group">
        <div class="brand-icon">⚡</div>
        <div class="brand-text">AI Crawl Optimizer</div>
        <div class="brand-badge">Audit Suite</div>
    </div>
    <div class="nav-links">
        <a class="nav-item active" href="#hero">Dashboard</a>
        <a class="nav-item" href="#audit-config">Audit</a>
        <a class="nav-item" href="#results-section">Results</a>
        <a class="nav-item" href="#how-it-works">How It Works</a>
    </div>
    <div>
        {status_pill}
    </div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# HERO SECTION
# -----------------------------------------------------------------------------
st.markdown("""
<div id="hero" class="hero-card">
    <div class="hero-title">Is Your Website Ready for AI Crawlers?</div>
    <div style="display: inline-flex; align-items: center; gap: 0.6rem; margin-bottom: 0.75rem;">
        <span style="font-size: 0.78rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #818cf8; background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.3); padding: 0.2rem 0.65rem; border-radius: 9999px;">SCORING ENGINE v2</span>
    </div>
    <div class="hero-subtitle">
        Audit how leading AI crawlers access your website, identify blocking mechanisms,
        and get evidence-based remediation recommendations.
    </div>
    <div class="hero-caption">
        Analyze robots.txt, HTTP responses, bot access rules, WAF challenges, and crawler-specific behavior.
    </div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# AUDIT CONFIGURATION & CONTROLS
# -----------------------------------------------------------------------------
available_personas = list_personas()
ai_personas = [p for p in available_personas if p.get("is_ai_agent")]
ai_persona_keys = [p["id"] for p in ai_personas]

# Quick preset pill buttons
col_p1, col_p2, col_p3, col_space = st.columns([1.5, 1.5, 1.5, 3.5])
default_target = "https://example.com"
with col_p1:
    if st.button("🌐 https://example.com", use_container_width=True):
        st.session_state["target_input"] = "https://example.com"
with col_p2:
    if st.button("📚 https://wikipedia.org", use_container_width=True):
        st.session_state["target_input"] = "https://wikipedia.org"
with col_p3:
    if st.button("🧪 Sandbox (Port 5050)", use_container_width=True):
        st.session_state["target_input"] = "http://127.0.0.1:5050"

current_url_val = st.session_state.get("target_input", default_target)

with st.form("audit_config_form"):
    st.markdown("""
    <div id="audit-config" class="config-header">
        ⚙️ Audit Configuration & Persona Emulation
    </div>
    """, unsafe_allow_html=True)

    col_url, col_mode = st.columns([3, 2])
    with col_url:
        url_input = st.text_input(
            "Target Website URL:",
            value=current_url_val,
            placeholder="https://example.com",
            help="Enter target website or domain to audit for AI crawler accessibility"
        )
    with col_mode:
        audit_mode = st.radio(
            "Audit Mode:",
            options=["Multi-Persona Audit", "Single Persona Audit"],
            horizontal=True,
            index=0,
            help="Multi-Persona audits registered AI engines; Single Persona focuses on a specific agent."
        )

    col_sel, col_base = st.columns([2.5, 2.5])
    with col_sel:
        if audit_mode == "Single Persona Audit":
            chosen_persona = st.selectbox(
                "Select AI Persona to simulate:",
                options=ai_persona_keys,
                format_func=lambda pid: next((p["display_name"] for p in available_personas if p["id"] == pid), pid),
                index=0
            )
            selected_personas = [chosen_persona]
        else:
            default_selection = [p["id"] for p in ai_personas if p["id"] in ("gptbot", "claudebot", "perplexitybot", "google_extended", "bytespider")]
            if not default_selection:
                default_selection = ai_persona_keys[:5]
            selected_personas = st.multiselect(
                "Select AI Personas to audit:",
                options=ai_persona_keys,
                default=default_selection,
                format_func=lambda pid: next((p["display_name"] for p in available_personas if p["id"] == pid), pid),
                help="Select which AI crawlers to emulate from registered personas."
            )
            if not selected_personas:
                selected_personas = default_selection
            st.caption(f"Configured {len(selected_personas)} AI crawler persona(s) for audit.")

    with col_base:
        include_baseline = st.checkbox(
            "Compare Against Browser Baseline",
            value=True,
            help="Compare AI crawler behavior against a standard browser to detect selective blocking."
        )
        st.caption("Compare AI crawler behavior against a standard browser to detect selective blocking.")

    st.markdown("<div style=\"margin-top: 0.5rem;\"></div>", unsafe_allow_html=True)
    submit_button = st.form_submit_button("⚡ Run AI Accessibility Audit", type="primary", use_container_width=True)

# -----------------------------------------------------------------------------
# SUPPORTED AI CRAWLERS (CHIPS GRID - DYNAMIC FROM REGISTRY)
# -----------------------------------------------------------------------------
# NOTE: chips_markup must NOT have leading whitespace on each line.
# Markdown treats 4+ spaces of indentation as a code block, which causes
# raw HTML to appear instead of rendered content.
_chip_parts = []
for _p in ai_personas:
    _name = _p.get("display_name", _p.get("id", ""))
    _token = _p.get("robots_token", "")
    _pid = _p.get("id", "")
    _chip_parts.append(
        f'<div class="crawler-chip">'
        f'<div class="crawler-chip-name">{_name} <span class="crawler-chip-status">Ready</span></div>'
        f'<div class="crawler-chip-desc">Token: {_token} &bull; ID: {_pid}</div>'
        f'</div>'
    )
chips_markup = "".join(_chip_parts)

st.markdown(
    f'<div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase;'
    f' letter-spacing: 0.08em; color: var(--text-secondary); margin-top: 1.5rem;'
    f' margin-bottom: 0.5rem;">🤖 Supported AI Crawlers ({len(ai_personas)})</div>'
    f'<div class="crawler-grid">{chips_markup}</div>',
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _build_aggregate_payload(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a single scoring payload from ALL persona crawl results.
    Uses REAL observed data only - never fabricates status=200 or latency=150.
    Missing evidence stays None/unknown, not defaulted to accessible.
    """
    bots: Dict[str, Any] = {}
    robots_txt: Dict[str, Any] = {}
    baseline_res: Optional[Dict[str, Any]] = None

    for res in results:
        persona_id = res.get("persona", "unknown")
        http = res.get("http", {})
        det = res.get("detection", {})
        inf = det.get("inference", {})
        ev = det.get("evidence", {})

        # REAL observed values only
        status = http.get("status_code")           # None if not crawled
        latency = http.get("response_time_ms") or 0
        verdict = str(inf.get("verdict", "")).upper()
        mechanism = str(inf.get("mechanism", "NONE")).upper()
        confidence = float(inf.get("confidence", 0.0))
        is_blocked = det.get("is_blocked", False) or verdict in ("BLOCKED", "CHALLENGED")

        # WAF name from mechanism string
        waf_name: Optional[str] = None
        if "CLOUDFLARE" in mechanism:
            waf_name = "Cloudflare"
        elif "DATADOME" in mechanism:
            waf_name = "DataDome"
        elif "PERIMETERX" in mechanism:
            waf_name = "PerimeterX"
        elif "AWS_WAF" in mechanism:
            waf_name = "AWS WAF"
        elif "AKAMAI" in mechanism:
            waf_name = "Akamai"
        elif mechanism not in ("NONE", "HTTP_FORBIDDEN", "INCONCLUSIVE", "",
                               "HTTP_429_RATE_LIMITED") and "HTTP" not in mechanism:
            waf_name = mechanism
        # Also check from explicit waf field or matched_headers
        if not waf_name:
            waf_name = res.get("waf") or None
        matched_headers = ev.get("matched_headers", [])
        if not waf_name and any("cloudflare" in h.lower() for h in matched_headers):
            waf_name = "Cloudflare"

        # CAPTCHA from DOM signals and keywords
        dom_signals = ev.get("dom_signals", [])
        matched_keywords = ev.get("matched_keywords", [])
        all_signals = dom_signals + matched_headers + matched_keywords
        has_captcha = any(
            "captcha" in s.lower() or "turnstile" in s.lower() or "challenge" in s.lower()
            for s in all_signals + [mechanism]
        )

        page = res.get("page", {})
        text_length = page.get("text_length", 0) if isinstance(page, dict) else 0

        bots[persona_id] = {
            "status": status,
            "latency_ms": int(latency),
            "blocked": is_blocked,
            "verdict": verdict,
            "mechanism": mechanism,
            "confidence": confidence,
            "waf": waf_name,
            "captcha": has_captcha,
            "signals": all_signals,
            "text_length": text_length,
        }

        # Take first available robots_txt
        if not robots_txt and res.get("robots_txt"):
            robots_txt = res.get("robots_txt", {})

        # Collect baseline if available
        if baseline_res is None and res.get("baseline"):
            baseline_res = res.get("baseline")

    # Browser baseline: ONLY if a real baseline was collected
    browser: Dict[str, Any] = {"status": None, "latency_ms": 0, "is_real": False}
    if baseline_res:
        b_http = baseline_res.get("http", {})
        b_det = baseline_res.get("detection", {})
        browser = {
            "status": b_http.get("status_code"),
            "latency_ms": b_http.get("response_time_ms") or 0,
            "blocked": b_det.get("is_blocked", False),
            "is_real": True,
        }

    waf_detected = next((b.get("waf") for b in bots.values() if b.get("waf")), None)
    captcha_detected = any(b.get("captcha") for b in bots.values())

    # Selective blocking: only if real baseline shows browser 200 while AI denied
    selective_ai_block = False
    if browser.get("is_real") and browser.get("status") == 200 and not browser.get("blocked"):
        selective_ai_block = any(b.get("blocked") for b in bots.values())

    return {
        "browser": browser,
        "bots": bots,
        "robots_txt": robots_txt,
        "waf_detected": waf_detected,
        "captcha_detected": captcha_detected,
        "selective_ai_block_detected": selective_ai_block,
    }

# -----------------------------------------------------------------------------
def build_executive_diagnosis(
    results: List[Dict[str, Any]],
    baseline_result: Optional[Dict[str, Any]]
) -> str:
    """
    Derives an evidence-grounded executive diagnosis from actual aggregate crawler telemetry.
    Strictly follows zero-hallucination rules:
    - Accurately reports counts of accessible, challenged, blocked, and inconclusive crawlers.
    - Accurately names actual detected mechanisms (e.g. RECAPTCHA, CLOUDFLARE_CHALLENGE).
    - NEVER mentions HTTP 403 Forbidden unless an actual crawler in this audit returned status 403.
    - Evaluates selective blocking/challenging against desktop browser baseline.
    """
    total = len(results)
    if total == 0:
        return "No crawler audit results available."

    accessible = []
    challenged = []
    blocked = []
    inconclusive = []

    for r in results:
        inf = r.get("detection", {}).get("inference", {})
        verdict = str(inf.get("verdict", "")).upper()
        st_code = r.get("http", {}).get("status_code")
        is_b = r.get("detection", {}).get("is_blocked", False)

        if verdict == "ACCESSIBLE":
            accessible.append(r)
        elif verdict == "CHALLENGED":
            challenged.append(r)
        elif verdict == "BLOCKED":
            blocked.append(r)
        elif verdict == "INCONCLUSIVE":
            inconclusive.append(r)
        else:
            if st_code == 200 and not is_b:
                accessible.append(r)
            elif is_b or (st_code and st_code in (401, 403)):
                blocked.append(r)
            else:
                inconclusive.append(r)

    # Collect actual detected mechanisms from challenged and blocked bots
    detected_mechanisms = []
    for r in challenged + blocked:
        mech = str(r.get("detection", {}).get("inference", {}).get("mechanism", "NONE")).upper()
        if mech not in ("NONE", "HTTP_FORBIDDEN", "") and mech not in detected_mechanisms:
            detected_mechanisms.append(mech)

    # Check whether HTTP 403 actually occurred in crawler results
    has_actual_403 = any(r.get("http", {}).get("status_code") == 403 for r in results)

    # Evaluate desktop baseline parity
    base_code = baseline_result.get("http", {}).get("status_code") if baseline_result else None
    base_verdict = str(baseline_result.get("detection", {}).get("inference", {}).get("verdict", "")).upper() if baseline_result else ""
    base_accessible = (base_code == 200 and base_verdict != "BLOCKED" and base_verdict != "CHALLENGED") if baseline_result else False

    selective_restriction = base_accessible and (len(challenged) > 0 or len(blocked) > 0)

    # Build grounded diagnosis headline
    if len(accessible) == total:
        headline = f"All {total} AI crawler personas evaluated have unimpeded access. No bot challenges or crawl restrictions detected."
    elif selective_restriction:
        if len(challenged) > 0 and len(blocked) == 0:
            if len(detected_mechanisms) > 0:
                headline = f"Selective AI crawler challenges detected ({', '.join(detected_mechanisms)}). Human desktop visitors receive full access (HTTP 200), but AI crawlers encounter bot verification challenges."
            else:
                headline = "Selective AI crawler challenges detected. Human desktop visitors receive full access (HTTP 200), but AI crawlers encounter bot verification challenges."
        elif len(blocked) > 0 and len(challenged) == 0:
            if has_actual_403:
                headline = "Selective AI crawler blocking detected (HTTP 403 Forbidden). Desktop browsers access normally (HTTP 200), while AI crawlers are explicitly denied."
            else:
                headline = "Selective AI crawler blocking detected. Desktop browsers access normally (HTTP 200), while AI crawlers are blocked."
        else:
            if len(detected_mechanisms) > 0:
                headline = f"Selective AI crawler blocking and challenges detected ({', '.join(detected_mechanisms)}). Human desktop visitors receive full access (HTTP 200), while AI crawlers are restricted."
            else:
                headline = "Selective AI crawler blocking and challenges detected between AI agents and human desktop browsers."
    elif len(challenged) > 0 and len(blocked) == 0 and len(accessible) > 0:
        headline = "Mixed accessibility: Some AI crawler personas are challenged by bot mitigation rules, while others have access."
    elif len(challenged) == total:
        if len(detected_mechanisms) > 0:
            headline = f"AI crawler challenges detected across all personas ({', '.join(detected_mechanisms)}). Indexing agents are intercepted by bot verification."
        else:
            headline = "AI crawler challenges detected across all personas. Indexing agents are intercepted by bot verification."
    elif len(blocked) == total:
        if has_actual_403:
            headline = "Severe AI Crawl Blockage: AI agents are blocked due to HTTP 403 Forbidden. Your site is invisible to generative AI search."
        elif len(detected_mechanisms) > 0:
            headline = f"Severe AI Crawl Blockage: AI agents are blocked by {', '.join(detected_mechanisms)}. Your site is invisible to generative AI search."
        else:
            headline = "Severe AI Crawl Blockage: AI agents are denied access. Your site is invisible to generative AI search."
    elif len(inconclusive) == total:
        headline = "Inconclusive audit: Access restrictions detected without definitive anti-bot challenge signatures."
    else:
        headline = "AI accessibility issues detected across evaluated crawler personas."

    breakdown = f"Audit breakdown: {len(accessible)} accessible, {len(challenged)} challenged, {len(blocked)} blocked, {len(inconclusive)} inconclusive across {total} personas evaluated."
    return f"{headline} {breakdown}"

# -----------------------------------------------------------------------------
# AUDIT EXECUTION FLOW & PROGRESS STEPPER
# -----------------------------------------------------------------------------
if submit_button:
    if not url_input.strip():
        st.error("Please enter a valid website URL.")
    else:
        norm_url = normalize_url(url_input)
        st.session_state["target_input"] = norm_url

        progress_slot = st.empty()
        with progress_slot.container():
            st.markdown("""
            <div style="background: #0d1527; border: 1px solid rgba(99,102,241,0.3); border-radius: 14px; padding: 1.4rem; margin-bottom: 1.5rem;">
                <div style="font-weight: 700; font-size: 1rem; color: #ffffff; margin-bottom: 0.8rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span class="status-dot"></span> Executing Multi-Stage AI Crawler Audit...
                </div>
            """, unsafe_allow_html=True)
            prog_bar = st.progress(0)
            status_text = st.empty()
            st.markdown("</div>", unsafe_allow_html=True)

        try:
            status_text.markdown("**Step**: `1. Initializing audit parameters and verifying target connectivity...`")
            prog_bar.progress(0.05)
            time.sleep(0.08)

            total_personas = len(selected_personas)
            results = []
            for idx, persona in enumerate(selected_personas):
                persona_info = next((p for p in available_personas if p["id"] == persona), None)
                display_name = persona_info["display_name"] if persona_info else persona

                base_pct = 0.10 + (0.75 * (idx / max(1, total_personas)))
                status_text.markdown(f"**Step**: `Auditing {display_name} ({idx + 1}/{total_personas}): inspecting HTTP status, DOM & bot challenges...`")
                prog_bar.progress(base_pct)

                audit_res = run_audit(
                    norm_url,
                    persona=persona,
                    include_baseline=include_baseline,
                    headless=True,
                    timeout_seconds=12.0,
                )
                results.append(audit_res)

            status_text.markdown("**Step**: `Synthesizing audit findings, baseline parity, and remediation plans...`")
            prog_bar.progress(0.92)
            time.sleep(0.1)

            # Final 100% completion state
            status_text.markdown("**Status**: `✅ Audit Complete! All crawler personas evaluated.`")
            prog_bar.progress(1.0)
            time.sleep(0.3)

            # Cleanly clear loading container so it doesn't remain visible after results appear
            progress_slot.empty()

            # ----------------------------------------------------------------
            # BUILD AGGREGATE SCORING from ALL persona results (not just primary_res)
            # ----------------------------------------------------------------
            aggregate_payload = _build_aggregate_payload(results)
            aggregate_scoring = calculate_score(aggregate_payload)

            st.session_state["audit_results"] = results
            st.session_state["audit_url"] = norm_url
            st.session_state["aggregate_scoring"] = aggregate_scoring
        except Exception as e:
            st.error(f"Audit execution error: {str(e)}")
            st.stop()

# -----------------------------------------------------------------------------
# RESULTS DASHBOARD
# -----------------------------------------------------------------------------
if "audit_results" in st.session_state:
    results: List[Dict[str, Any]] = st.session_state["audit_results"]
    audit_url = st.session_state.get("audit_url", "")
    primary_res = results[0]
    baseline_result = primary_res.get("baseline")

    # Aggregate scoring: computed over ALL personas (not just primary_res)
    aggregate_scoring = st.session_state.get("aggregate_scoring", {})
    if not aggregate_scoring:
        # Fallback: build aggregate now (e.g. page reload)
        aggregate_scoring = calculate_score(_build_aggregate_payload(results))

    score = aggregate_scoring.get("score", 0)
    grade = aggregate_scoring.get("grade", "N/A")
    risk_label = aggregate_scoring.get("risk_level", "HIGH RISK")
    diagnosis_text = build_executive_diagnosis(results, baseline_result)

    risk_badge_class = "badge-high-risk"
    if "LOW" in risk_label:
        risk_badge_class = "badge-low-risk"
    elif "MED" in risk_label:
        risk_badge_class = "badge-med-risk"

    # Aggregated Summary Counts - Preserving exact backend semantics
    accessible_count = 0
    challenged_count = 0
    blocked_count = 0
    inconclusive_count = 0

    for r in results:
        det = r.get("detection", {})
        inf = det.get("inference", {})
        verdict = str(inf.get("verdict", "")).upper()
        st_code = r.get("http", {}).get("status_code")
        is_b = det.get("is_blocked", False)

        if verdict == "ACCESSIBLE":
            accessible_count += 1
        elif verdict == "CHALLENGED":
            challenged_count += 1
        elif verdict == "BLOCKED":
            blocked_count += 1
        elif verdict == "INCONCLUSIVE":
            inconclusive_count += 1
        else:
            if st_code == 200 and not is_b:
                accessible_count += 1
            elif is_b or (st_code and st_code in (401, 403)):
                blocked_count += 1
            else:
                inconclusive_count += 1

    penalties = aggregate_scoring.get("penalties", [])
    total_issues = len(penalties)

    st.markdown("<div id=\"results-section\"></div>", unsafe_allow_html=True)

    # 1. Overall Score Banner
    st.markdown(f"""
    <div class="score-banner">
        <div>
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: #818cf8; margin-bottom: 0.4rem;">
                OVERALL AI ACCESSIBILITY SCORE
            </div>
            <div class="score-circle-group">
                <span class="score-big-num">{score}</span>
                <span class="score-denom">/ 100</span>
            </div>
            <div style="margin-top: 0.6rem;">
                <span class="badge-pill {risk_badge_class}">Grade: {grade} &bull; {risk_label}</span>
            </div>
        </div>
        <div class="score-meta-group">
            <div class="score-headline">Executive Diagnosis for <code>{audit_url}</code></div>
            <div class="score-diagnosis">{diagnosis_text}</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.3rem;">
                Evaluated across {len(results)} AI personas &bull; Live Crawler Emulation
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. KPI Summary Row (5 distinct categories)
    st.markdown(f"""
    <div class="kpi-row" style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.9rem;">
        <div class="kpi-card kpi-card-acc">
            <div class="kpi-label">Accessible Crawlers</div>
            <div class="kpi-value kpi-value-acc">{accessible_count}</div>
            <div class="kpi-subtext">Unimpeded AI bot indexing</div>
        </div>
        <div class="kpi-card" style="border-left: 3px solid #f59e0b; background: rgba(245, 158, 11, 0.06);">
            <div class="kpi-label">Challenged Crawlers</div>
            <div class="kpi-value" style="color: #fbbf24;">{challenged_count}</div>
            <div class="kpi-subtext">CAPTCHA or WAF challenge</div>
        </div>
        <div class="kpi-card kpi-card-blk">
            <div class="kpi-label">Blocked Crawlers</div>
            <div class="kpi-value kpi-value-blk">{blocked_count}</div>
            <div class="kpi-subtext">Explicit access denial</div>
        </div>
        <div class="kpi-card kpi-card-inc">
            <div class="kpi-label">Inconclusive</div>
            <div class="kpi-value kpi-value-inc">{inconclusive_count}</div>
            <div class="kpi-subtext">Preserved uncertainty</div>
        </div>
        <div class="kpi-card kpi-card-iss">
            <div class="kpi-label">Issues Detected</div>
            <div class="kpi-value kpi-value-iss">{total_issues}</div>
            <div class="kpi-subtext">Deduction signals flagged</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # POINT DEDUCTION TRACKER — sourced from aggregate_scoring (ALL personas)
    # -------------------------------------------------------------------------
    tracker_penalties = aggregate_scoring.get("penalties", [])
    total_deductions = aggregate_scoring.get("total_deductions", 0)
    base_score = aggregate_scoring.get("base_score", 100)
    final_score_from_engine = aggregate_scoring.get("score", score)

    st.markdown("""
    <div style="font-size: 1.1rem; font-weight: 800; letter-spacing: -0.02em; color: #ffffff; margin-top: 1.8rem; margin-bottom: 0.6rem;">
        📉 Point Deduction Tracker
    </div>
    """, unsafe_allow_html=True)

    if not tracker_penalties:
        st.markdown("""
        <div style="background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.3); border-radius: 12px; padding: 1.2rem 1.4rem; color: #a7f3d0;">
            <strong>✅ No scoring deductions detected.</strong><br>
            Starting score of 100 was fully preserved. This site is AI-crawler optimized.
        </div>
        """, unsafe_allow_html=True)
    else:
        severity_colors = {
            "CRITICAL": ("#ef4444", "rgba(239,68,68,0.1)", "rgba(239,68,68,0.3)"),
            "HIGH":     ("#f59e0b", "rgba(245,158,11,0.1)", "rgba(245,158,11,0.3)"),
            "MEDIUM":   ("#818cf8", "rgba(99,102,241,0.1)", "rgba(99,102,241,0.3)"),
            "LOW":      ("#64748b", "rgba(100,116,139,0.1)", "rgba(100,116,139,0.3)"),
        }
        rows_html = ""
        for p in tracker_penalties:
            sev = p.get("severity", "LOW")
            clr, bg, border = severity_colors.get(sev, severity_colors["LOW"])
            cat = p.get("category", "")
            reason = p.get("reason") or p.get("factor", "")
            pts = p.get("points_deducted") or abs(p.get("penalty", 0))
            evidence_items = p.get("evidence", [])
            evidence_html = ""
            if evidence_items:
                ev_items_str = "".join(
                    f'<span style="font-size:0.73rem;color:#64748b;background:rgba(255,255,255,0.04);'
                    f'border:1px solid rgba(255,255,255,0.07);border-radius:5px;padding:0.1rem 0.4rem;'
                    f'margin-right:0.3rem;display:inline-block;margin-top:0.25rem;">{e}</span>'
                    for e in evidence_items[:3]
                )
                evidence_html = f'<div style="margin-top:0.3rem;">{ev_items_str}</div>'
            rows_html += f"""
            <div style="display: flex; align-items: flex-start; justify-content: space-between;
                        background: {bg}; border: 1px solid {border};
                        border-radius: 10px; padding: 0.8rem 1.1rem; margin-bottom: 0.55rem;">
                <div style="flex:1;">
                    <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                                letter-spacing: 0.08em; color: {clr}; margin-bottom: 0.25rem;">{sev} &bull; {cat}</div>
                    <div style="font-size: 0.9rem; color: #e2e8f0;">{reason}</div>
                    {evidence_html}
                </div>
                <div style="font-size: 1.4rem; font-weight: 800; color: {clr}; white-space: nowrap; margin-left: 1.5rem;">-{pts}</div>
            </div>"""

        st.markdown(f"""
        <div style="background: #0d1527; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 1.2rem 1.3rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;
                        margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <span style="font-size: 0.9rem; color: #94a3b8;">Starting Score</span>
                <span style="font-size: 1.4rem; font-weight: 800; color: #ffffff;">{base_score}</span>
            </div>
            {rows_html}
            <div style="display: flex; justify-content: space-between; align-items: center;
                        margin-top: 0.9rem; padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.1);">
                <span style="font-size: 0.9rem; font-weight: 700; color: #94a3b8;">TOTAL DEDUCTED</span>
                <span style="font-size: 1.4rem; font-weight: 800; color: #ef4444;">-{total_deductions}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;
                        margin-top: 0.5rem; padding-top: 0.6rem; border-top: 2px solid rgba(255,255,255,0.15);">
                <span style="font-size: 1rem; font-weight: 800; color: #ffffff; letter-spacing: -0.01em;">FINAL SCORE</span>
                <span style="font-size: 1.8rem; font-weight: 900; color: {'#10b981' if final_score_from_engine >= 75 else '#f59e0b' if final_score_from_engine >= 50 else '#ef4444'}">{final_score_from_engine} <span style="font-size: 1rem; font-weight: 600; color: #64748b;">/ 100</span></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Baseline Differential Callout (Evidence-Grounded Selective Blocking Banner)
    if baseline_result:
        base_code = baseline_result.get("http", {}).get("status_code", 200)
        base_inf = baseline_result.get("detection", {}).get("inference", {})
        base_verdict = str(base_inf.get("verdict", "ACCESSIBLE")).upper()
        base_is_accessible = (base_code == 200 and base_verdict != "BLOCKED" and base_verdict != "CHALLENGED")

        ai_challenged_or_blocked = [
            r for r in results
            if str(r.get("detection", {}).get("inference", {}).get("verdict", "")).upper() in ("CHALLENGED", "BLOCKED")
            or r.get("detection", {}).get("is_blocked", False)
        ]

        if base_is_accessible and ai_challenged_or_blocked:
            detected_mechs = sorted(list({
                str(r.get("detection", {}).get("inference", {}).get("mechanism", "NONE")).upper()
                for r in ai_challenged_or_blocked
                if str(r.get("detection", {}).get("inference", {}).get("mechanism", "NONE")).upper() not in ("NONE", "")
            }))
            mech_details = f" &bull; Detected mechanism: <strong>{', '.join(detected_mechs)}</strong>" if detected_mechs else ""
            has_403 = any(r.get("http", {}).get("status_code") == 403 for r in ai_challenged_or_blocked)
            status_details = " (HTTP 403 Forbidden)" if has_403 else ""

            st.markdown(f"""
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.4rem;">⚠️</span>
                <div style="font-size: 0.9rem; color: #fca5a5;">
                    <strong>Selective AI Crawler Blocking or Challenges Detected:</strong> Standard desktop browsers receive <code>200 OK</code>, but AI crawler personas encounter access barriers{status_details}{mech_details}.
                </div>
            </div>
            """, unsafe_allow_html=True)
        elif base_is_accessible and not ai_challenged_or_blocked:
            st.markdown("""
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.4rem;">✅</span>
                <div style="font-size: 0.9rem; color: #a7f3d0;">
                    <strong>Consistent Access:</strong> Both AI assistant personas and human desktop browsers have unimpeded access.
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 3. Crawler Results Table / Matrix
    st.markdown("""
    <div style="font-size: 1.1rem; font-weight: 800; letter-spacing: -0.02em; color: #ffffff; margin-bottom: 0.6rem;">
        🤖 AI Crawler Results Matrix
    </div>
    """, unsafe_allow_html=True)

    matrix_rows = []
    matrix_list = list(results)
    if baseline_result:
        matrix_list.append(baseline_result)

    for r in matrix_list:
        p_id = r.get("persona")
        p_name = next((p["display_name"] for p in available_personas if p["id"] == p_id), p_id or "Standard Chrome (Baseline)")
        r_http = r.get("http", {})
        r_robots = r.get("robots_txt", {})
        r_det = r.get("detection", {})
        r_inf = r_det.get("inference", {})

        st_code = r_http.get("status_code", "N/A")
        verdict = str(r_inf.get("verdict", "ACCESSIBLE")).upper()
        mech = str(r_inf.get("mechanism", "NONE")).upper()
        conf = r_inf.get("confidence", 1.0)

        # Preserve exact backend detection verdict
        if verdict == "CHALLENGED":
            verdict_display = "🛡️ Challenged"
        elif verdict == "BLOCKED":
            verdict_display = "⛔ Blocked"
        elif verdict == "INCONCLUSIVE":
            verdict_display = "⚠️ Inconclusive"
        elif verdict == "ACCESSIBLE":
            verdict_display = "✅ Accessible"
        else:
            verdict_display = f"Status {st_code}"

        robots_policy = "Allowed" if r_robots.get("is_allowed", True) else "Disallowed"
        latency = f"{r_http.get('response_time_ms', 0)} ms"

        matrix_rows.append({
            "Crawler Persona": p_name,
            "Verdict": verdict_display,
            "HTTP Status": str(st_code),
            "Detected Mechanism": mech if mech != "NONE" else "None",
            "robots.txt Policy": robots_policy,
            "Confidence": f"{int(conf * 100)}%" if isinstance(conf, (int, float)) else "N/A",
            "Latency": latency
        })

    df_matrix = pd.DataFrame(matrix_rows)
    st.dataframe(df_matrix, use_container_width=True, hide_index=True)

    # 4. Crawler Deep Dive / Detail View
    st.markdown("""
    <div style="font-size: 1.1rem; font-weight: 800; letter-spacing: -0.02em; color: #ffffff; margin-top: 1.8rem; margin-bottom: 0.6rem;">
        🔍 Detailed Crawler Telemetry & Evidence Inspector
    </div>
    """, unsafe_allow_html=True)

    inspect_options = [r.get("persona") for r in results]
    inspect_persona_id = st.selectbox(
        "Select crawler result to inspect detailed technical evidence:",
        options=inspect_options,
        format_func=lambda pid: next((p["display_name"] for p in available_personas if p["id"] == pid), pid),
        index=0
    )

    inspected_res = next((r for r in results if r.get("persona") == inspect_persona_id), results[0])
    ins_det = inspected_res.get("detection", {})
    ins_inf = ins_det.get("inference", {})
    ins_http = inspected_res.get("http", {})
    ins_robots = inspected_res.get("robots_txt", {})
    ins_page = inspected_res.get("page", {})
    ins_verdict = str(ins_inf.get("verdict", "ACCESSIBLE")).upper()
    ins_mech = str(ins_inf.get("mechanism", "NONE")).upper()

    tab_sum, tab_ev, tab_rem = st.tabs(["📋 Detection Summary", "📡 Telemetry Summary", "🛠️ Grounded Remediation Plan"])

    with tab_sum:
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("Verdict", ins_verdict)
        with col_s2:
            st.metric("Mechanism", ins_mech)
        with col_s3:
            conf_val = ins_inf.get("confidence", 1.0)
            st.metric("Confidence Score", f"{int(conf_val * 100)}%" if isinstance(conf_val, (int, float)) else "N/A")

        if ins_verdict == "INCONCLUSIVE":
            st.markdown(f"""
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 12px; padding: 1.2rem; color: #fbbf24; margin-top: 1rem;">
                <strong>⚠️ Uncertainty Preserved (Zero-Hallucination Policy):</strong><br>
                The crawler received HTTP {ins_http.get("status_code", "N/A")}, but detected no definitive WAF fingerprint, Cloudflare challenge, or bot-blocking signatures.
                In compliance with strict evidence rules, this finding is classified as <strong>INCONCLUSIVE</strong>. The system will NOT fabricate an AI-specific blocking claim without concrete evidence.
            </div>
            """, unsafe_allow_html=True)

        st.markdown("#### Observed Detection Signals")
        signals = ins_det.get("signals", [])
        if signals:
            for s in signals:
                st.markdown(f"- `{s}`")
        else:
            st.caption("No suspicious bot mitigation signals or challenge markers detected.")

    with tab_ev:
        st.markdown("#### Telemetry Summary")
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("**HTTP Response**")
            http_status = ins_http.get("status_code", "N/A")
            http_latency = ins_http.get("response_time_ms", "N/A")
            http_url = ins_http.get("final_url") or inspected_res.get("url", "N/A")
            st.markdown(f"""
            <div style="background:#0d1424; border:1px solid rgba(255,255,255,0.07); border-radius:10px; padding:1rem;">
                <div style="margin-bottom:0.5rem;"><span style="color:#64748b; font-size:0.8rem;">Status Code</span><br>
                    <strong style="font-size:1.1rem; color:#f8fafc;">{http_status}</strong></div>
                <div style="margin-bottom:0.5rem;"><span style="color:#64748b; font-size:0.8rem;">Response Time</span><br>
                    <strong style="color:#f8fafc;">{http_latency} ms</strong></div>
                <div style="word-break:break-all;"><span style="color:#64748b; font-size:0.8rem;">Final URL</span><br>
                    <span style="color:#94a3b8; font-size:0.82rem;">{http_url}</span></div>
            </div>
            """, unsafe_allow_html=True)
        with col_e2:
            st.markdown("**Robots.txt & Page Detection**")
            robots_exists = ins_robots.get("exists", False)
            robots_allowed = ins_robots.get("is_allowed", True)
            page_title = ins_page.get("title") or "(not captured)"
            has_captcha_el = ins_page.get("has_captcha", False)
            has_waf_el = ins_page.get("has_waf_challenge", False)
            robots_icon = "✅" if robots_allowed else "🚫"
            st.markdown(f"""
            <div style="background:#0d1424; border:1px solid rgba(255,255,255,0.07); border-radius:10px; padding:1rem;">
                <div style="margin-bottom:0.5rem;"><span style="color:#64748b; font-size:0.8rem;">robots.txt exists</span><br>
                    <strong style="color:#f8fafc;">{'Yes' if robots_exists else 'No'}</strong></div>
                <div style="margin-bottom:0.5rem;"><span style="color:#64748b; font-size:0.8rem;">AI Crawler Allowed</span><br>
                    <strong style="color:#f8fafc;">{robots_icon} {'Yes' if robots_allowed else 'No (Disallowed)'}</strong></div>
                <div style="margin-bottom:0.5rem;"><span style="color:#64748b; font-size:0.8rem;">Page Title</span><br>
                    <span style="color:#94a3b8; font-size:0.82rem;">{page_title}</span></div>
                <div style="display:flex; gap:1.2rem;">
                    <div><span style="color:#64748b; font-size:0.8rem;">CAPTCHA Elements</span><br>
                        <strong style="color:{'#ef4444' if has_captcha_el else '#10b981'};">{'Detected' if has_captcha_el else 'None'}</strong></div>
                    <div><span style="color:#64748b; font-size:0.8rem;">WAF Challenge</span><br>
                        <strong style="color:{'#ef4444' if has_waf_el else '#10b981'};">{'Detected' if has_waf_el else 'None'}</strong></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with tab_rem:
        rem_data = inspected_res.get("remediation", {})
        model_used = rem_data.get("model_used")

        engine_tag = (
            '<span class="brand-badge" style="background: rgba(16,185,129,0.15); color: #34d399; border-color: rgba(16,185,129,0.35);">✨ Gemini 2.5 Generative Fix</span>'
            if model_used
            else '<span class="brand-badge" style="background: rgba(99,102,241,0.15); color: #a5b4fc; border-color: rgba(99,102,241,0.35);">🛡️ Deterministic Grounded Engine (RFC 9309)</span>'
        )

        problem_text = rem_data.get("problem_detected") or rem_data.get("problem", "No remediation required.")
        impact_text = rem_data.get("impact_on_ai_crawling") or rem_data.get("impact", "No adverse impact detected.")
        fix_text = rem_data.get("recommended_fix") or rem_data.get("fix", "No fix needed.")
        code_text = rem_data.get("code_or_configuration_change") or rem_data.get("code_or_config", "")
        evidence_list = rem_data.get("evidence_observed") or []
        validation_steps = rem_data.get("validation_steps") or []

        st.markdown(f"""
        <div class="remediation-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <span style="font-size: 1.15rem; font-weight: 800; color: #ffffff;">Remediation & Action Plan</span>
                {engine_tag}
            </div>
            <div class="rem-section-title">Problem Detected</div>
            <div class="rem-text">{problem_text}</div>
            <div class="rem-section-title">Why It Affects AI Crawling</div>
            <div class="rem-text">{impact_text}</div>
            <div class="rem-section-title">Recommended Fix</div>
            <div class="rem-text">{fix_text}</div>
        </div>
        """, unsafe_allow_html=True)

        if evidence_list:
            st.markdown("##### Grounded Evidence Observed:")
            for ev in evidence_list:
                st.markdown(f"- `{ev}`")

        if code_text:
            # Extract plain-English action title from the fix text
            action_title = rem_data.get("action_title") or "Recommended Configuration Change"
            # Expected impact from code comment / recommendation
            impact_text_short = rem_data.get("expected_impact") or impact_text
            st.markdown(f"""
            <div style="background: rgba(99,102,241,0.07); border: 1px solid rgba(99,102,241,0.25);
                        border-radius: 12px; padding: 1.1rem 1.3rem; margin-top: 0.8rem;">
                <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                            letter-spacing: 0.1em; color: #818cf8; margin-bottom: 0.5rem;">Recommended Action</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin-bottom: 0.4rem;">{action_title}</div>
                <div style="font-size: 0.88rem; color: #94a3b8; line-height: 1.55;">{fix_text}</div>
                <div style="font-size: 0.82rem; color: #64748b; margin-top: 0.6rem;">
                    Expected impact: {impact_text_short}
                </div>
            </div>
            """, unsafe_allow_html=True)

        if validation_steps:
            st.markdown("##### Verification & Validation Steps:")
            for step in validation_steps:
                st.markdown(f"- [ ] {step}")

# -----------------------------------------------------------------------------
# EXPLAINABILITY & TRUST SECTION ("Evidence-Based, Not Guesswork")
# -----------------------------------------------------------------------------
_pipeline_nodes = [
    ("1. Target Website",        "Public URL / App"),
    ("2. AI Crawler Simulation", "Authentic User-Agents"),
    ("3. Evidence Collection",   "HTTP, DOM &amp; WAF signals"),
    ("4. Grounded Detection",    "Factual classification"),
    ("5. Remediation Engine",    "Synthesized code fixes"),
]
_pipeline_html = ""
for _i, (_title, _sub) in enumerate(_pipeline_nodes):
    _pipeline_html += (
        f'<div class="pipeline-node">'
        f'<div class="pipeline-node-title">{_title}</div>'
        f'<div class="pipeline-node-sub">{_sub}</div>'
        f'</div>'
    )
    if _i < len(_pipeline_nodes) - 1:
        _pipeline_html += '<div class="pipeline-arrow">&rarr;</div>'

st.markdown(
    '<div class="trust-pipeline">'
    '<div style="font-size:1.25rem;font-weight:800;color:#ffffff;letter-spacing:-0.02em;">'
    '🛡️ Evidence-Based, Not Guesswork'
    '</div>'
    '<div style="font-size:0.9rem;color:var(--text-secondary);margin-top:0.4rem;max-width:820px;line-height:1.55;">'
    'The system separates detected facts from inference and preserves uncertainty when the cause cannot be confidently determined. '
    'Deductions and remediation recommendations are grounded in observed crawler telemetry and response evidence.'
    '</div>'
    f'<div class="pipeline-steps">{_pipeline_html}</div>'
    '</div>',
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# HOW IT WORKS SECTION
# -----------------------------------------------------------------------------
_hiw_steps = [
    ("Step 01", "Enter Website",
     "Input any public URL or staging sandbox to initiate the automated accessibility audit."),
    ("Step 02", "Simulate AI Crawlers",
     "Emulate supported AI crawler personas using authentic User-Agents and browser emulation."),
    ("Step 03", "Detect Access Issues",
     "Inspect robots.txt directives, X-Robots-Tag headers, meta robots tags, and edge WAF challenges."),
    ("Step 04", "Get Actionable Fixes",
     "Receive copy-paste ready robots.txt rules, web server configurations, and WAF rule adjustments."),
]
_hiw_cards = "".join(
    f'<div class="hiw-step-card">'
    f'<div class="hiw-step-num">{_num}</div>'
    f'<div class="hiw-step-title">{_title}</div>'
    f'<div class="hiw-step-desc">{_desc}</div>'
    f'</div>'
    for _num, _title, _desc in _hiw_steps
)

st.markdown(
    '<div id="how-it-works">'
    '<div style="font-size:1.25rem;font-weight:800;color:#ffffff;letter-spacing:-0.02em;margin-bottom:0.4rem;">'
    '⚡ How It Works'
    '</div>'
    '<div style="font-size:0.9rem;color:var(--text-secondary);margin-bottom:1.2rem;">'
    'Four high-precision phases ensuring comprehensive visibility into your website\'s AI search compatibility.'
    '</div>'
    f'<div class="how-it-works-grid">{_hiw_cards}</div>'
    '</div>',
    unsafe_allow_html=True,
)
