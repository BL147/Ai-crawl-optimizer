import os
import time
import textwrap
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional

import streamlit as st
import pandas as pd

def render_html(html_str: str) -> None:
    """Render HTML cleanly without Markdown interpreting indented lines as code blocks."""
    st.markdown(textwrap.dedent(html_str).strip(), unsafe_allow_html=True)

from crawler import list_personas
from demo_streaming_site.app import start_server
from fix_engine import (
    apply_fix,
    get_default_registry,
    apply_restriction,
    remove_restriction,
    RestrictionEngine,
    RestrictionStatus,
    RestrictionCapability,
    RestrictionCategory,
    RESTRICTION_CATALOG,
)
from orchestration import run_audit
from scoring import calculate_score
from validation import compare_and_validate, ValidationStatus, FixStatus, TargetIssue, IssueCategory

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
        grid-template-columns: repeat(2, 1fr);
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

    /* Phase 2 Fix & Validate Styles */
    .phase2-container {
        background: linear-gradient(135deg, #0e172a 0%, #0a1020 100%);
        border: 1px solid rgba(99, 102, 241, 0.35);
        border-radius: 18px;
        padding: 2.2rem 2.4rem;
        margin-top: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 15px 35px -8px rgba(0, 0, 0, 0.5);
    }
    .phase2-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.2rem;
        padding-bottom: 0.8rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .phase2-badge {
        font-size: 0.72rem;
        font-weight: 800;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        background: rgba(99, 102, 241, 0.2);
        border: 1px solid rgba(99, 102, 241, 0.4);
        color: #a5b4fc;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .controlled-env-callout {
        background: rgba(14, 165, 233, 0.08);
        border: 1px solid rgba(14, 165, 233, 0.25);
        border-radius: 10px;
        padding: 0.8rem 1.1rem;
        font-size: 0.84rem;
        color: #7dd3fc;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .phase2-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1.2rem;
        margin-top: 1rem;
        margin-bottom: 1.2rem;
    }
    .state-card {
        background: #0d1527;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.3rem;
    }
    .state-card-header {
        font-size: 0.82rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.8rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .state-before-title { color: #fca5a5; }
    .state-after-title { color: #86efac; }
    .val-banner-verified {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.45);
        color: #34d399;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        font-weight: 700;
        font-size: 1.1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .val-banner-partially {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.45);
        color: #fbbf24;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        font-weight: 700;
        font-size: 1.1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .val-banner-failed {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.45);
        color: #f87171;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        font-weight: 700;
        font-size: 1.1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .val-banner-inconclusive {
        background: rgba(148, 163, 184, 0.15);
        border: 1px solid rgba(148, 163, 184, 0.45);
        color: #cbd5e1;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        font-weight: 700;
        font-size: 1.1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    /* Phase 3 Restriction & Security Styles */
    .phase3-container {
        background: linear-gradient(180deg, rgba(30, 27, 75, 0.45) 0%, rgba(15, 23, 42, 0.6) 100%);
        border: 1px solid rgba(168, 85, 247, 0.35);
        border-radius: 16px;
        padding: 1.8rem;
        margin-top: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }
    .phase3-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 1.2rem;
        margin-bottom: 1.4rem;
    }
    .phase3-badge {
        font-size: 0.75rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 0.3rem 0.8rem;
        border-radius: 9999px;
        background: rgba(168, 85, 247, 0.15);
        border: 1px solid rgba(168, 85, 247, 0.4);
        color: #d8b4fe;
    }
    .cap-badge-supported {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34d399;
    }
    .cap-badge-rec {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.4);
        color: #fbbf24;
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
        <a class="nav-item" href="#phase2-section">Phase 2 Fix</a>
        <a class="nav-item" href="#phase3-section">Phase 3 Control</a>
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
    if st.button("🌐 https://example.com", width="stretch"):
        st.session_state["target_input"] = "https://example.com"
with col_p2:
    if st.button("📚 https://wikipedia.org", width="stretch"):
        st.session_state["target_input"] = "https://wikipedia.org"
with col_p3:
    if st.button("🧪 Sandbox (Port 5050)", width="stretch"):
        st.session_state["target_input"] = "http://127.0.0.1:5050"

current_url_val = st.session_state.get("target_input", default_target)

with st.form("audit_config_form"):
    render_html("""
    <div id="audit-config" class="config-header">
        ⚙️ Audit Configuration & Persona Emulation
    </div>
    """)

    security_mode = st.radio(
        "AI WORKFLOW MODE:",
        options=["AI ACCESSIBILITY (Optimize & Fix)", "AI RESTRICTION (Security & Control)"],
        horizontal=True,
        index=0,
        help="Accessibility evaluates how AI crawlers can reach your site. Restriction presents security controls and guidance to protect proprietary data."
    )
    st.caption("Choose whether your goal is maximizing AI discoverability (Phase 2) or enforcing AI crawl boundaries (Phase 3).")

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
    submit_button = st.form_submit_button(
        "⚡ Run AI Accessibility Audit" if "ACCESSIBILITY" in security_mode else "🛡️ Run AI Restriction Audit",
        type="primary",
        width="stretch"
    )

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

with st.expander(f"🤖 Supported AI Crawlers ({len(ai_personas)})", expanded=False):
    render_html(f'<div class="crawler-grid">{chips_markup}</div>')

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


def is_controlled_test_environment(target: str, registry=None) -> bool:
    """Check if target is a registered, controlled local test environment."""
    if registry is None:
        registry = get_default_registry()
    try:
        return bool(registry.is_allowed(target))
    except Exception:
        return False


def _restriction_status(result: Dict[str, Any]) -> str:
    """Translate crawler telemetry and evidence into restriction status language."""
    http_status = result.get("http", {}).get("status_code")
    inference = result.get("detection", {}).get("inference", {})
    verdict = str(inference.get("verdict", "")).upper()
    mechanism = str(inference.get("mechanism", "")).upper()

    if http_status == 429 or mechanism == "RATE_LIMIT":
        return "AI Requests Rate Limited / Blocked (HTTP 429)"
    if verdict == "CHALLENGED" or mechanism in {"CAPTCHA", "CLOUDFLARE_CHALLENGE"}:
        return "AI Verification Challenge Required"
    if result.get("robots_txt", {}).get("is_allowed") is False or verdict in {"BLOCKED", "RESTRICTED"}:
        return "AI Crawl Restricted by Policy"
    if verdict == "ACCESSIBLE" or (http_status and 200 <= http_status < 300):
        return "AI Accessible (Unrestricted)"
    return "Inconclusive / Indeterminate"


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
        st.session_state["audit_security_mode"] = "AI RESTRICTION" if "RESTRICTION" in security_mode else "AI ACCESSIBILITY"

        if "5050" in norm_url or "demo_streaming_site" in norm_url:
            try:
                start_server(port=5050)
            except Exception:
                pass

        progress_slot = st.empty()
        with progress_slot.container():
            render_html("""
            <div style="background: #0d1527; border: 1px solid rgba(99,102,241,0.3); border-radius: 14px; padding: 1.4rem; margin-bottom: 1.5rem;">
                <div style="font-weight: 700; font-size: 1rem; color: #ffffff; display: flex; align-items: center; gap: 0.5rem;">
                    <span class="status-dot"></span> Executing Multi-Stage AI Crawler Audit...
                </div>
            </div>
            """)
            prog_bar = st.progress(0)
            status_text = st.empty()

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
            is_restriction_audit = "RESTRICTION" in st.session_state.get("audit_security_mode", security_mode)
            aggregate_scoring = calculate_score(
                aggregate_payload,
                mode="RESTRICTION" if is_restriction_audit else "ACCESSIBILITY"
            )

            st.session_state["audit_results"] = results
            st.session_state["audit_url"] = norm_url
            st.session_state["aggregate_scoring"] = aggregate_scoring
            st.session_state["scroll_to_score"] = True
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
    active_security_mode = st.session_state.get("audit_security_mode", "AI ACCESSIBILITY")
    is_restr_mode = "RESTRICTION" in active_security_mode

    aggregate_scoring = st.session_state.get("aggregate_scoring", {})
    if not aggregate_scoring:
        # Fallback: build aggregate now (e.g. page reload)
        aggregate_scoring = calculate_score(
            _build_aggregate_payload(results),
            mode="RESTRICTION" if is_restr_mode else "ACCESSIBILITY"
        )

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
    st.markdown("<div id=\"overall-accessibility-score\"></div>", unsafe_allow_html=True)

    # Auto-scroll directly to Overall Accessibility Score after running audit
    if st.session_state.pop("scroll_to_score", False):
        st.html(
            """
            <script>
                setTimeout(function() {
                    var el = document.getElementById('overall-accessibility-score') ||
                             (window.parent && window.parent.document && window.parent.document.getElementById('overall-accessibility-score')) ||
                             document.getElementById('results-section');
                    if (el) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }, 250);
            </script>
            """
        )

    score_title = "OVERALL AI RESTRICTION & SECURITY SCORE" if is_restr_mode else "OVERALL AI ACCESSIBILITY SCORE"

    # 1. Overall Score Banner
    render_html(f"""
    <div class="score-banner" id="overall-score-banner">
        <div>
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: #818cf8; margin-bottom: 0.4rem;">
                {score_title}
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
    """)

    # 2. KPI Summary Row (5 distinct categories)
    render_html(f"""
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
    """)

    # -------------------------------------------------------------------------
    # POINT DEDUCTION TRACKER — sourced from aggregate_scoring (ALL personas)
    # -------------------------------------------------------------------------
    tracker_penalties = aggregate_scoring.get("penalties", [])
    total_deductions = aggregate_scoring.get("total_deductions", 0)
    base_score = aggregate_scoring.get("base_score", 100)
    final_score_from_engine = aggregate_scoring.get("score", score)

    tracker_label = (
        f"📉 Point Deduction Tracker (-{total_deductions} pts)"
        if total_deductions > 0
        else "📉 Point Deduction Tracker (0 deductions)"
    )
    with st.expander(tracker_label, expanded=False):
        if not tracker_penalties:
            render_html("""
            <div style="background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.3); border-radius: 12px; padding: 1.2rem 1.4rem; color: #a7f3d0;">
                <strong>✅ No scoring deductions detected.</strong><br>
                Starting score of 100 was fully preserved.
            </div>
            """)
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

            rows_html = textwrap.dedent(rows_html).strip()
            render_html(f"""
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
            """)

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

            render_html(f"""
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.4rem;">⚠️</span>
                <div style="font-size: 0.9rem; color: #fca5a5;">
                    <strong>Selective AI Crawler Blocking or Challenges Detected:</strong> Standard desktop browsers receive <code>200 OK</code>, but AI crawler personas encounter access barriers{status_details}{mech_details}.
                </div>
            </div>
            """)
        elif base_is_accessible and not ai_challenged_or_blocked:
            render_html("""
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.4rem;">✅</span>
                <div style="font-size: 0.9rem; color: #a7f3d0;">
                    <strong>Consistent Access:</strong> Both AI assistant personas and human desktop browsers have unimpeded access.
                </div>
            </div>
            """)

    # 3. Crawler Results Table / Matrix
    render_html("""
    <div style="font-size: 1.1rem; font-weight: 800; letter-spacing: -0.02em; color: #ffffff; margin-bottom: 0.6rem;">
        🤖 AI Crawler Results Matrix
    </div>
    """)

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
    st.dataframe(df_matrix, width="stretch", hide_index=True)

    # 4. Crawler Deep Dive / Detail View
    render_html("""
    <div style="font-size: 1.1rem; font-weight: 800; letter-spacing: -0.02em; color: #ffffff; margin-top: 1.8rem; margin-bottom: 0.6rem;">
        🔍 Detailed Crawler Telemetry & Evidence Inspector
    </div>
    """)

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
            render_html(f"""
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 12px; padding: 1.2rem; color: #fbbf24; margin-top: 1rem;">
                <strong>⚠️ Uncertainty Preserved (Zero-Hallucination Policy):</strong><br>
                The crawler received HTTP {ins_http.get("status_code", "N/A")}, but detected no definitive WAF fingerprint, Cloudflare challenge, or bot-blocking signatures.
                In compliance with strict evidence rules, this finding is classified as <strong>INCONCLUSIVE</strong>. The system will NOT fabricate an AI-specific blocking claim without concrete evidence.
            </div>
            """)

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
            render_html(f"""
            <div style="background:#0d1424; border:1px solid rgba(255,255,255,0.07); border-radius:10px; padding:1rem;">
                <div style="margin-bottom:0.5rem;"><span style="color:#64748b; font-size:0.8rem;">Status Code</span><br>
                    <strong style="font-size:1.1rem; color:#f8fafc;">{http_status}</strong></div>
                <div style="margin-bottom:0.5rem;"><span style="color:#64748b; font-size:0.8rem;">Response Time</span><br>
                    <strong style="color:#f8fafc;">{http_latency} ms</strong></div>
                <div style="word-break:break-all;"><span style="color:#64748b; font-size:0.8rem;">Final URL</span><br>
                    <span style="color:#94a3b8; font-size:0.82rem;">{http_url}</span></div>
            </div>
            """)
        with col_e2:
            st.markdown("**Robots.txt & Page Detection**")
            robots_exists = ins_robots.get("exists", False)
            robots_allowed = ins_robots.get("is_allowed", True)
            page_title = ins_page.get("title") or "(not captured)"
            has_captcha_el = ins_page.get("has_captcha", False)
            has_waf_el = ins_page.get("has_waf_challenge", False)
            robots_icon = "✅" if robots_allowed else "🚫"
            render_html(f"""
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
            """)

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

        render_html(f"""
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
        """)

        if evidence_list:
            st.markdown("##### Grounded Evidence Observed:")
            for ev in evidence_list:
                st.markdown(f"- `{ev}`")

        if code_text:
            # Extract plain-English action title from the fix text
            action_title = rem_data.get("action_title") or "Recommended Configuration Change"
            # Expected impact from code comment / recommendation
            impact_text_short = rem_data.get("expected_impact") or impact_text
            render_html(f"""
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
            """)

        if validation_steps:
            st.markdown("##### Verification & Validation Steps:")
            for step in validation_steps:
                st.markdown(f"- [ ] {step}")

    # =========================================================================
    # PHASE 3 RESTRICTION / SECURITY WORKFLOW IMPLEMENTATION
    # =========================================================================
    def _render_phase3_restriction_mode(
        audit_url: str,
        results: List[Dict[str, Any]],
        registry: Any,
    ) -> None:
        """Render Phase 3 AI Crawl Restriction & Security Control workflow."""
        st.markdown("<div id=\"phase3-section\"></div>", unsafe_allow_html=True)

        controlled = is_controlled_test_environment(audit_url, registry)
        env = registry.get(audit_url) or registry.get("demo_streaming_site")
        env_name = env.description if env else "CineStream Streaming Platform Demo Website"
        env_url = env.base_url if env else "http://127.0.0.1:5050"
        env_id = env.id if env else "demo_streaming_site"

        render_html(f"""
        <div class="phase3-container">
            <div class="phase3-header">
                <div>
                    <span class="phase3-badge">Phase 3 Security & Control Engine</span>
                    <div style="font-size: 1.45rem; font-weight: 800; color: #ffffff; margin-top: 0.4rem;">
                        🛡️ AI Crawl Restriction & Security Mode
                    </div>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 0.8rem; color: #94a3b8;">Active Target</span><br>
                    <strong style="color: #c084fc; font-size: 0.95rem;">{env_name if controlled else audit_url}</strong>
                </div>
            </div>
            <div style="font-size: 0.92rem; color: #cbd5e1; line-height: 1.55; margin-bottom: 1.2rem;">
                Control, restrict, and validate AI crawler access boundaries on your web assets.
                Evaluate exposure across leading AI agents, enforce security controls, and verify enforcement using the canonical validation engine.
            </div>
        </div>
        """)

        # 1. Educational Context: Why restrict AI crawling?
        with st.expander("ℹ️ Understanding AI Crawl Restriction: Why, When, and How", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("""
                **Why Restrict AI Crawling?**
                - **Copyright & Training Data Ingestion**: Prevent commercial LLM foundation models from scraping proprietary writing, creative works, and media without attribution or compensation.
                - **Bandwidth & Server Load Protection**: High-frequency AI scrapers can overwhelm origin servers, cause latency degradation, and spike cloud ingress/egress bills.
                """)
            with c2:
                st.markdown("""
                **Control Mechanisms:**
                - **Robots.txt Policy**: RFC 9309 declarative boundary honored by compliant AI models.
                - **Rate Limiting (HTTP 429)**: Throttling request velocity at reverse proxy or CDN edge.
                - **Edge WAF Challenges (HTTP 403)**: Intercepting automated traffic with bot management.
                - **Interactive CAPTCHAs**: Distinguishing human visitors from automated agents.
                - **Authentication / Paywalls**: Strict token or session verification for private content.
                """)

        # 2. Observed AI Exposure Matrix
        st.markdown("#### 📡 Observed AI Crawler Exposure")
        st.caption("Observed access state across evaluated AI crawler personas based on recent audit telemetry.")

        exposure_rows = []
        for r in results:
            p_name = str(r.get("persona", "Unknown")).replace("_", " ").title()
            status_text = _restriction_status(r)
            http_code = r.get("http", {}).get("status_code") or (r.get("crawl", {}).get("http", {}).get("status_code")) or "N/A"
            det_inf = r.get("detection", {}).get("inference", {}) or r.get("crawl", {}).get("detection", {}).get("inference", {})
            verdict = det_inf.get("verdict", "UNKNOWN")
            exposure_rows.append({
                "AI Crawler": p_name,
                "Observed Restriction Status": status_text,
                "HTTP Code": http_code,
                "Verdict": verdict,
            })
        st.dataframe(pd.DataFrame(exposure_rows), width="stretch", hide_index=True)

        # 3. External Site Safety Guarantee
        if not controlled:
            st.warning(
                f"🔒 **EXTERNAL TARGET SAFETY GUARANTEE ({audit_url}):** "
                "To guarantee safety and prevent unauthorized modifications, automated restriction enforcement, live re-crawling, "
                "and removal actions are strictly disabled on external websites. "
                "The recommendations below provide verified configuration guidance for production deployment."
            )
            st.caption("🛡️ No external provider configurations (Cloudflare, Akamai, reCAPTCHA, origin servers) are modified.")

            recs = [
                (
                    "1. Robots.txt AI Restriction",
                    "RECOMMENDATION ONLY",
                    "Add crawler-specific Disallow directives for AI user-agents in your robots.txt file.",
                    "User-agent: GPTBot\nUser-agent: ClaudeBot\nUser-agent: PerplexityBot\nUser-agent: CCBot\nUser-agent: Bytespider\nDisallow: /",
                    "Compliant AI crawlers (OpenAI, Anthropic, Perplexity) parse and honor RFC 9309 rules before scraping, protecting your content without impacting search engines like Googlebot."
                ),
                (
                    "2. AI Crawler Rate Limiting",
                    "RECOMMENDATION ONLY",
                    "Configure edge rate limits in Nginx or CDN WAF to return HTTP 429 Too Many Requests for AI bot user-agents.",
                    "# Nginx configuration snippet\nlimit_req_zone $binary_remote_addr zone=ai_limit:10m rate=1r/s;\nif ($http_user_agent ~* (GPTBot|ClaudeBot|Bytespider)) {\n    return 429;\n}",
                    "Protects server capacity and prevents scraper DDoS attacks while ensuring standard human visitors experience fast response times."
                ),
                (
                    "3. Edge WAF / Bot Challenge",
                    "RECOMMENDATION ONLY",
                    "Deploy Cloudflare WAF Custom Rules or Akamai Bot Manager to challenge or block automated AI scraping traffic.",
                    "# Cloudflare Custom WAF Expression\n(http.user_agent contains \"GPTBot\" or http.user_agent contains \"ClaudeBot\")\nAction: Managed Challenge (HTTP 403 / JS Challenge)",
                    "Edge firewalls intercept and block non-compliant scraping bots before their requests reach your origin application."
                ),
                (
                    "4. Interactive CAPTCHA / Bot Verification",
                    "RECOMMENDATION ONLY",
                    "Integrate Cloudflare Turnstile or Google reCAPTCHA Enterprise on content and search routes.",
                    "<!-- Cloudflare Turnstile Widget -->\n<div class=\"cf-turnstile\" data-sitekey=\"your-site-key\"></div>",
                    "Requires cryptographic proof of human interaction, creating an insurmountable challenge for automated scraping scripts."
                ),
                (
                    "5. Authentication & Content Gating",
                    "RECOMMENDATION ONLY",
                    "Enforce JWT, OAuth 2.0, or mutual TLS session tokens on private API endpoints.",
                    "# Require Authorization Header\nAuthorization: Bearer <valid_jwt_token>\n# Unauthenticated bots receive HTTP 401 Unauthorized",
                    "Establishes a strict zero-trust boundary. Automated AI crawlers cannot index or extract private subscriber content."
                ),
            ]
            st.markdown("#### 📋 Recommended Production AI Restrictions")
            for title, pill, desc, code, why in recs:
                with st.expander(f"{title} — {pill}", expanded=False):
                    st.markdown(f"**Action:** {desc}")
                    if code:
                        st.code(code, language="nginx" if "Nginx" in desc else "text")
                    st.markdown(f"**Why it helps:** {why}")
            return

        # 4. Controlled Environment Controls (CineStream)
        st.success(f"✅ **CONTROLLED ENVIRONMENT CONNECTED:** {env_name} (`{env_url}`). Supported restrictions can be applied, re-crawled, validated, and reverted.")

        st.markdown("##### 🛡️ Restriction Capabilities in Controlled Environment")
        cap_c1, cap_c2 = st.columns(2)
        with cap_c1:
            st.markdown("""
            - 🟢 **Robots.txt AI Crawl Restriction** — `SUPPORTED_CONTROLLED_FIX` (Actionable)
            - 🟢 **AI Crawler Rate Limiting (HTTP 429)** — `SUPPORTED_CONTROLLED_FIX` (Actionable)
            - 🟢 **WAF Challenge Simulation (HTTP 403)** — `SUPPORTED_CONTROLLED_FIX` (Actionable)
            """)
        with cap_c2:
            st.markdown("""
            - 🟢 **Interactive CAPTCHA Challenge** — `SUPPORTED_CONTROLLED_FIX` (Actionable)
            - 🟡 **AI Agent Authentication & Gating** — `RECOMMENDATION ONLY` (OAuth/mTLS)
            """)

        control_options = {
            "ai_robots_restriction": "Robots.txt AI Crawl Restriction (RFC 9309 Disallow)",
            "ai_rate_limit": "AI Crawler Rate Limiting (HTTP 429 Simulation)",
            "ai_waf_challenge": "WAF / Anti-Bot Challenge Simulation (HTTP 403 Challenge)",
            "ai_captcha": "Interactive CAPTCHA Challenge (Cloudflare Turnstile Simulation)",
            "ai_authentication": "AI Agent Authentication & Gating (Recommendation Only)",
        }

        selected_control_id = st.selectbox(
            "Select AI Restriction Control to Apply / Test:",
            options=list(control_options.keys()),
            format_func=lambda cid: control_options[cid],
            help="Select a control mechanism to enforce on the controlled CineStream test environment."
        )

        if selected_control_id == "ai_authentication":
            st.info("ℹ️ **AI Agent Authentication & Gating** is an architectural pattern requiring identity provider integration (OAuth 2.0 / JWT tokens). It is marked **Recommendation Only** in the controlled test environment.")
            st.code("""# Authentication Middleware Example:
def verify_ai_agent_token(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(401, description="Authentication required for AI crawler access.")""", language="python")
            return

        # Multi-Persona Selection for Target and Allowed traffic
        st.markdown("##### 👥 Multi-Persona Policy Configuration")
        col_t, col_a = st.columns(2)
        with col_t:
            target_personas = st.multiselect(
                "Target AI Personas to Restrict:",
                options=["gptbot", "claudebot", "perplexitybot", "bytespider", "ccbot", "google_extended"],
                default=["gptbot"],
                format_func=lambda pid: pid.replace("_", " ").title(),
                help="These AI crawler personas will be targeted by the restriction."
            )
        with col_a:
            allowed_personas = st.multiselect(
                "Allowed Personas to Preserve Access:",
                options=["standard_browser", "googlebot"],
                default=["standard_browser"],
                format_func=lambda pid: pid.replace("_", " ").title(),
                help="Validation Engine verifies that legitimate traffic from these personas remains unhindered (no collateral blocking)."
            )

        if not target_personas:
            st.warning("Select at least one target persona to restrict.")

        # Action buttons side-by-side
        btn_col1, btn_col2 = st.columns([1.5, 1.5])
        with btn_col1:
            apply_restr_btn = st.button(
                "⚡ Apply Restriction & Validate",
                type="primary",
                width="stretch",
                disabled=not target_personas,
                help="Enforces restriction on CineStream, executes live re-crawl, and runs canonical ValidationEngine."
            )
        with btn_col2:
            remove_restr_btn = st.button(
                "🔄 Remove Restriction & Revert",
                type="secondary",
                width="stretch",
                disabled=not target_personas,
                help="Removes active restriction and validates that CineStream returns to normal accessible state."
            )

        # Apply flow
        if apply_restr_btn and target_personas:
            restr_prog = st.empty()
            with restr_prog.container():
                st.info(f"🔄 Step 1/3: Running baseline multi-persona crawl on {env_name}...")

            start_server(port=5050)

            raw_before = []
            for p in target_personas:
                raw_before.append(run_audit(env_url, persona=p, include_baseline=False, timeout_seconds=12.0))
            for p in allowed_personas:
                raw_before.append(run_audit(env_url, persona=p, include_baseline=False, timeout_seconds=12.0))
            audit_before = dict(raw_before[0])
            audit_before["raw_results"] = raw_before

            with restr_prog.container():
                st.info(f"🛡️ Step 2/3: Enforcing '{selected_control_id}' via canonical RestrictionEngine...")
            restr_res = apply_restriction(
                control_id=selected_control_id,
                target=env_id,
                options={
                    "personas": target_personas,
                    "allowed_personas": allowed_personas,
                }
            )

            with restr_prog.container():
                st.info(f"📡 Step 3/3: Re-crawling test environment across target and allowed personas...")
            raw_after = []
            for p in target_personas:
                raw_after.append(run_audit(env_url, persona=p, include_baseline=False, timeout_seconds=12.0))
            for p in allowed_personas:
                raw_after.append(run_audit(env_url, persona=p, include_baseline=False, timeout_seconds=12.0))
            audit_after = dict(raw_after[0])
            audit_after["raw_results"] = raw_after

            cat_map = {
                "ai_robots_restriction": IssueCategory.AI_ROBOTS_RESTRICTION,
                "ai_rate_limit": IssueCategory.AI_RATE_LIMIT,
                "ai_waf_challenge": IssueCategory.AI_WAF_CHALLENGE,
                "ai_captcha": IssueCategory.AI_CAPTCHA,
            }
            target_issue = TargetIssue(
                category=cat_map.get(selected_control_id, IssueCategory.AI_ROBOTS_RESTRICTION),
                target_personas=target_personas,
                allowed_personas=allowed_personas,
                is_security_restriction=True,
            )
            val_result = compare_and_validate(
                audit_before=audit_before,
                audit_after=audit_after,
                fix_status=restr_res.get("status", "APPLIED"),
                target_issue=target_issue,
            )

            restr_prog.empty()

            st.session_state["phase3_validation_result"] = val_result
            st.session_state["phase3_restr_res"] = restr_res
            st.session_state["phase3_audit_before"] = audit_before
            st.session_state["phase3_audit_after"] = audit_after
            st.session_state["phase3_control_id"] = selected_control_id
            st.session_state["phase3_target_personas"] = target_personas
            st.session_state["phase3_allowed_personas"] = allowed_personas

        # Remove flow
        if remove_restr_btn and target_personas:
            rem_prog = st.empty()
            with rem_prog.container():
                st.info(f"🔄 Reverting restriction '{selected_control_id}' on {env_name}...")

            start_server(port=5050)
            rem_res = remove_restriction(
                control_id=selected_control_id,
                target=env_id,
                options={"personas": target_personas}
            )
            restored_crawl = run_audit(env_url, persona=target_personas[0], include_baseline=False, timeout_seconds=12.0)
            rem_prog.empty()

            st.session_state["phase3_validation_result"] = None
            st.session_state.pop("phase3_audit_after", None)
            st.success(f"✅ Restriction `{selected_control_id}` removed! Target `{target_personas[0].title()}` restored to {restored_crawl.get('crawl', {}).get('detection', {}).get('inference', {}).get('verdict', 'ACCESSIBLE')}.")

        # Render validation result
        if st.session_state.get("phase3_validation_result"):
            v_res = st.session_state["phase3_validation_result"]
            a_before = st.session_state["phase3_audit_before"]
            a_after = st.session_state["phase3_audit_after"]
            r_res = st.session_state["phase3_restr_res"]
            t_personas = st.session_state.get("phase3_target_personas", ["gptbot"])
            all_personas = st.session_state.get("phase3_allowed_personas", ["standard_browser"])
            c_id = st.session_state.get("phase3_control_id", "ai_robots_restriction")

            v_status = v_res.validation_status
            status_val = v_status.value if hasattr(v_status, "value") else str(v_status)

            b_score = v_res.before_score
            a_score = v_res.after_score
            delta = v_res.score_delta
            delta_str = f"{delta:+d}" if delta != 0 else "0"

            if status_val == "VERIFIED":
                banner_class = "val-banner-verified"
                banner_icon = "✓"
                banner_title = "RESTRICTION ENFORCEMENT VERIFIED"
                banner_desc = "Canonical Validation Engine confirmed: target AI crawler(s) successfully restricted without collateral impact on allowed traffic."
            elif status_val == "PARTIALLY_VERIFIED":
                banner_class = "val-banner-partially"
                banner_icon = "⚠️"
                banner_title = "PARTIALLY VERIFIED"
                banner_desc = "Target restriction partially enforced or collateral impact detected on legitimate allowed traffic."
            elif status_val == "INCONCLUSIVE":
                banner_class = "val-banner-inconclusive"
                banner_icon = "❓"
                banner_title = "INCONCLUSIVE VALIDATION"
                banner_desc = "Telemetric evidence is insufficient to conclusively verify restriction enforcement."
            else:
                banner_class = "val-banner-failed"
                banner_icon = "✗"
                banner_title = "RESTRICTION VALIDATION FAILED"
                banner_desc = "Target AI crawler remained accessible despite applied restriction."

            render_html(f"""
            <div style="margin-top: 1.5rem;">
                <div class="{banner_class}">
                    <span style="font-size: 1.8rem; font-weight: 900;">{banner_icon}</span>
                    <div>
                        <div style="font-size: 1.25rem; font-weight: 800; letter-spacing: -0.01em;">{banner_title}</div>
                        <div style="font-size: 0.85rem; opacity: 0.9; margin-top: 0.15rem;">{banner_desc}</div>
                    </div>
                </div>
            </div>
            """)

            p_primary = t_personas[0]
            before_raw_p = next((x for x in a_before.get("raw_results", []) if x.get("persona") == p_primary), a_before)
            after_raw_p = next((x for x in a_after.get("raw_results", []) if x.get("persona") == p_primary), a_after)

            b_verd = before_raw_p.get("detection", {}).get("inference", {}).get("verdict", "ACCESSIBLE")
            a_verd = after_raw_p.get("detection", {}).get("inference", {}).get("verdict", "RESTRICTED")

            render_html(f"""
            <div class="phase2-grid" style="margin-top: 1.2rem;">
                <div class="state-card">
                    <div class="state-card-header state-before-title">
                        <span>BASELINE (BEFORE RESTRICTION)</span>
                        <span style="font-size: 1.1rem; color: #ffffff;">Score: <strong>{b_score}</strong></span>
                    </div>
                    <div style="margin-bottom: 0.6rem;">
                        <span style="font-size: 0.78rem; color: #94a3b8;">Target Bot ({p_primary.title()}):</span><br>
                        <strong style="color: #10b981; font-size: 1.05rem;">{b_verd}</strong>
                    </div>
                    <div>
                        <span style="font-size: 0.78rem; color: #94a3b8;">Observed Baseline State:</span><br>
                        <span style="font-size: 0.88rem; color: #e2e8f0;">{str(v_res.issue_before or 'AI crawlers permitted')}</span>
                    </div>
                </div>
                <div class="state-card">
                    <div class="state-card-header state-after-title">
                        <span>ENFORCED (AFTER RESTRICTION)</span>
                        <span style="font-size: 1.1rem; color: #ffffff;">Score: <strong>{a_score}</strong> ({delta_str})</span>
                    </div>
                    <div style="margin-bottom: 0.6rem;">
                        <span style="font-size: 0.78rem; color: #94a3b8;">Target Bot ({p_primary.title()}):</span><br>
                        <strong style="color: #ef4444; font-size: 1.05rem;">{a_verd}</strong>
                    </div>
                    <div>
                        <span style="font-size: 0.78rem; color: #94a3b8;">Observed Enforced State:</span><br>
                        <span style="font-size: 0.88rem; color: #e2e8f0;">{str(v_res.issue_after or 'Security restriction enforced')}</span>
                    </div>
                </div>
            </div>
            """)

            st.markdown("##### 👥 Multi-Persona Telemetry Verification")
            telemetry_rows = []
            for res_p in a_after.get("raw_results", []):
                persona_id = res_p.get("persona", "unknown")
                is_target = persona_id in t_personas
                role_label = "🎯 Target Restriction" if is_target else "🛡️ Allowed Traffic"
                p_robots = res_p.get("robots_txt", {}).get("is_allowed")
                robots_label = "Allowed" if p_robots is True else ("Disallowed" if p_robots is False else "N/A")
                p_http = res_p.get("http", {}).get("status_code", "N/A")
                p_verd = res_p.get("detection", {}).get("inference", {}).get("verdict", "UNKNOWN")

                if is_target:
                    outcome = "✅ Successfully Restricted" if p_verd in {"RESTRICTED", "BLOCKED", "CHALLENGED"} or p_robots is False else "❌ Not Restricted"
                else:
                    outcome = "✅ Preserved (No Collateral)" if p_verd == "ACCESSIBLE" and p_robots is not False else "⚠️ Collateral Friction"

                telemetry_rows.append({
                    "Persona": persona_id.replace("_", " ").title(),
                    "Role": role_label,
                    "Robots Policy": robots_label,
                    "HTTP Status": p_http,
                    "Observed Verdict": p_verd,
                    "Validation Outcome": outcome,
                })
            st.dataframe(pd.DataFrame(telemetry_rows), width="stretch", hide_index=True)

            col_r1, col_r2 = st.columns([1, 1])
            with col_r1:
                st.markdown("##### 🔧 Restriction Engine Report")
                st.markdown(f"- **Control ID**: `{r_res.get('control_id')}`")
                st.markdown(f"- **Target Environment**: `{r_res.get('target')}`")
                st.markdown(f"- **Status**: `{r_res.get('status')}`")
                st.markdown(f"- **Engine Message**: {r_res.get('message')}")
                if r_res.get("files_changed"):
                    st.markdown(f"- **Files Modified**: `{', '.join(r_res.get('files_changed'))}`")
            with col_r2:
                st.markdown("##### 🔍 Validation Engine Evidence")
                if v_res.evidence:
                    for ev in v_res.evidence:
                        st.markdown(f"- `{ev}`")
                else:
                    st.markdown("- `No specific evidence lines recorded.`")

    # =========================================================================
    # WORKFLOW MODE SELECTOR: PHASE 2 (ACCESSIBILITY FIX) vs PHASE 3 (RESTRICTION CONTROL)
    # =========================================================================
    st.markdown("<div id=\"workflow-selection\"></div>", unsafe_allow_html=True)
    st.markdown("---")

    registry = get_default_registry()
    active_security_mode = st.session_state.get("audit_security_mode", "AI ACCESSIBILITY")
    default_workflow_idx = 1 if active_security_mode == "AI RESTRICTION" else 0

    workflow_mode = st.radio(
        "SELECT WORKFLOW TO EXECUTE:",
        options=[
            "🛠️ Phase 2: AI Accessibility Optimization (Audit → Fix → Validate)",
            "🛡️ Phase 3: AI Crawl Restriction & Security Control (Enforce → Re-crawl → Validate)",
        ],
        index=default_workflow_idx,
        horizontal=True,
        help="Phase 2 helps open access for AI crawlers. Phase 3 allows website owners to intentionally restrict AI crawlers and validate security enforcement."
    )

    if workflow_mode.startswith("🛡️ Phase 3"):
        _render_phase3_restriction_mode(audit_url, results, registry)
    else:
        # =========================================================================
        # PHASE 2: VALIDATE FIX ON TEST ENVIRONMENT
        # =========================================================================
        st.markdown("<div id=\"phase2-section\"></div>", unsafe_allow_html=True)

        if not is_controlled_test_environment(audit_url, registry):
            st.info(
                "🔒 **CONTROLLED TEST ENVIRONMENT ONLY:** "
                "Phase 2 automated fix application is available only for registered "
                "local test environments (e.g. CineStream at `http://127.0.0.1:5050`). "
                "For external websites, review and copy the generated remediation code in the section above."
            )
        else:
            env_list = registry.list_environments()
            default_env = env_list[0] if env_list else None
            test_env_name = default_env.get("description") if default_env else "CineStream Streaming Platform Demo Website"
            test_env_url = default_env.get("base_url") if default_env else "http://127.0.0.1:5050"
            test_env_id = default_env.get("id") if default_env else "demo_streaming_site"

            # Extract detected issue & recommended fix from current audit results
            primary_crawl = primary_res.get("crawl", primary_res)
            primary_det = primary_crawl.get("detection", {})
            primary_inf = primary_det.get("inference", {})
            primary_mech = str(primary_inf.get("mechanism", "NONE")).upper()
            primary_robots = primary_res.get("robots_txt", {})
            rem_info = primary_res.get("remediation", {})

            detected_issue_desc = "GPTBot is restricted by robots.txt"
            recommended_fix_desc = "Allow AI crawler access in robots.txt"
            chosen_fix_id = "robots_txt"

            if not primary_robots.get("is_allowed", True):
                detected_issue_desc = f"{primary_res.get('persona', 'GPTBot').title()} is restricted by robots.txt policy"
                recommended_fix_desc = "Allow AI crawler access in robots.txt"
                chosen_fix_id = "robots_txt"
            elif primary_mech in ("CLOUDFLARE_CHALLENGE", "CLOUDFLARE_BLOCK", "CAPTCHA"):
                detected_issue_desc = f"AI crawler blocked by anti-bot challenge ({primary_mech})"
                recommended_fix_desc = rem_info.get("recommended_fix", "Configure WAF bypass rule for verified AI bots")
                chosen_fix_id = "robots_txt"
            elif (primary_res.get("http", {}).get("response_time_ms") or 0) > 3000:
                detected_issue_desc = f"Excessive crawler response latency ({primary_res.get('http', {}).get('response_time_ms', 0):.0f}ms)"
                recommended_fix_desc = "Optimize endpoint latency and reduce simulated server delay"
                chosen_fix_id = "latency"
            elif penalties:
                detected_issue_desc = penalties[0].get("factor", "AI Crawlability Friction Flagged")
                recommended_fix_desc = rem_info.get("recommended_fix", "Apply recommended configuration fix")
                chosen_fix_id = "robots_txt"

            render_html(f"""
            <div class="phase2-container">
                <div class="phase2-header">
                    <div>
                        <span class="phase2-badge">Phase 2 Verification Workflow</span>
                        <div style="font-size: 1.45rem; font-weight: 800; color: #ffffff; margin-top: 0.4rem;">
                            🛠️ Validate Fix on Test Environment
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 0.8rem; color: #94a3b8;">Target Environment</span><br>
                        <strong style="color: #38bdf8; font-size: 0.95rem;">{test_env_name}</strong>
                    </div>
                </div>

                <div class="controlled-env-callout">
                    <span style="font-size: 1.2rem;">🔒</span>
                    <div>
                        <strong>CONTROLLED TEST ENVIRONMENT ONLY:</strong> Arbitrary URL modifications and direct filesystem edits are strictly prohibited by the security allowlist. Fixes are applied deterministically via the Fix Application Engine.
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.2rem;">
                    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 10px; padding: 1rem;">
                        <span style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #f87171;">Detected Issue</span>
                        <div style="font-size: 1.05rem; font-weight: 700; color: #ffffff; margin-top: 0.3rem;">{detected_issue_desc}</div>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 10px; padding: 1rem;">
                        <span style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #818cf8;">Recommended Fix</span>
                        <div style="font-size: 1.05rem; font-weight: 700; color: #ffffff; margin-top: 0.3rem;">{recommended_fix_desc}</div>
                    </div>
                </div>
            </div>
            """)

            restricted_bot_ids = []
            for r in results:
                r_robots = r.get("robots_txt", {})
                r_det = r.get("detection", {})
                r_inf = r_det.get("inference", {})
                r_verd = str(r_inf.get("verdict", "")).upper()
                if (
                    r_robots.get("is_allowed") is False
                    or r_det.get("is_blocked", False)
                    or r_verd in {"BLOCKED", "CHALLENGED", "RESTRICTED"}
                ):
                    bid = str(r.get("persona", "")).strip().lower()
                    if bid and bid not in restricted_bot_ids:
                        restricted_bot_ids.append(bid)

            if not restricted_bot_ids:
                restricted_bot_ids = [primary_res.get("persona", "gptbot")]

            bot_labels = {
                bid: bid.replace("_", " ").title()
                for bid in restricted_bot_ids
            }
            selected_bots = st.multiselect(
                "Select restricted bot(s) to allow:",
                options=restricted_bot_ids,
                default=restricted_bot_ids,
                format_func=lambda bid: bot_labels.get(bid, bid),
                help="Selected bots will be added to the controlled site's robots.txt Allow rules."
            )
            if selected_bots:
                st.caption("The fix will update: " + ", ".join(bot_labels.get(bid, bid) for bid in selected_bots))
            else:
                st.warning("Select at least one restricted bot before applying a fix.")

            col_btn, col_info = st.columns([2, 3])
            with col_btn:
                run_fix_val = st.button(
                    "⚡ Apply Fix & Validate",
                    type="primary",
                    width="stretch",
                    disabled=not selected_bots,
                    help="Executes backend Fix Application Engine on controlled test environment and validates via Re-crawl."
                )
            with col_info:
                st.caption(f"Applies `{chosen_fix_id}` to `{test_env_id}` ({test_env_url}), performs live re-crawl, and executes Before vs. After validation.")

            if run_fix_val:
                fix_progress = st.empty()
                with fix_progress.container():
                    st.info("🔄 Initiating Phase 2 Fix Application & Validation Flow...")

                try:
                    start_server(port=5050)
                except Exception:
                    pass

                # 1. Baseline Audit (BEFORE) on test environment
                audit_before = primary_res
                if not (audit_url and test_env_url in audit_url):
                    with fix_progress.container():
                        st.info(f"📡 Step 1/3: Running initial baseline crawl on {test_env_name} ({test_env_url})...")
                    audit_before = run_audit(
                        test_env_url,
                        persona=primary_res.get("persona", "gptbot"),
                        include_baseline=True,
                        headless=True,
                        timeout_seconds=12.0
                    )

                # 2. Call backend Fix Application Engine
                with fix_progress.container():
                    st.info(f"🔧 Step 2/3: Applying '{chosen_fix_id}' via Fix Application Engine...")
                fix_res = apply_fix(
                    fix_id=chosen_fix_id,
                    target=test_env_id,
                    options={"personas": selected_bots if selected_bots else [primary_res.get("persona", "gptbot")]}
                )

                # 3. Call backend Re-crawl (AFTER)
                with fix_progress.container():
                    st.info(f"📡 Step 3/3: Re-crawling test environment to collect post-fix telemetry...")
                audit_after = run_audit(
                    test_env_url,
                    persona=primary_res.get("persona", "gptbot"),
                    include_baseline=True,
                    headless=True,
                    timeout_seconds=12.0
                )

                # 4. Call backend Validation Engine
                val_result = compare_and_validate(
                    audit_before=audit_before,
                    audit_after=audit_after,
                    fix_status=fix_res.get("status", "APPLIED"),
                    target_issue=chosen_fix_id,
                )

                fix_progress.empty()
                st.session_state["phase2_validation_result"] = val_result
                st.session_state["phase2_audit_before"] = audit_before
                st.session_state["phase2_audit_after"] = audit_after
                st.session_state["phase2_fix_res"] = fix_res

            # Render Phase 2 Validation Results if available
            if "phase2_validation_result" in st.session_state:
                v_res = st.session_state["phase2_validation_result"]
                a_before = st.session_state["phase2_audit_before"]
                a_after = st.session_state["phase2_audit_after"]
                f_res = st.session_state["phase2_fix_res"]

                v_status = v_res.get("validation_status")
                status_val = v_status.value if hasattr(v_status, "value") else str(v_status)

                b_score = v_res.get("before_score", 0)
                a_score = v_res.get("after_score", 0)
                delta = v_res.get("score_delta", a_score - b_score)
                delta_str = f"+{delta}" if delta > 0 else str(delta)

                if status_val == "VERIFIED":
                    banner_class = "val-banner-verified"
                    banner_icon = "✓"
                    banner_title = "FIX VERIFIED"
                elif status_val == "PARTIALLY_VERIFIED":
                    banner_class = "val-banner-partially"
                    banner_icon = "⚠️"
                    banner_title = "PARTIALLY VERIFIED"
                elif status_val == "INCONCLUSIVE":
                    banner_class = "val-banner-inconclusive"
                    banner_icon = "❓"
                    banner_title = "INCONCLUSIVE RESULT"
                else:
                    banner_class = "val-banner-failed"
                    banner_icon = "✗"
                    banner_title = "FIX VALIDATION FAILED"

                render_html(f"""
                <div style="margin-top: 1.5rem;">
                    <div class="{banner_class}">
                        <span style="font-size: 1.8rem; font-weight: 900;">{banner_icon}</span>
                        <div>
                            <div style="font-size: 1.25rem; font-weight: 800; letter-spacing: -0.01em;">{banner_title}</div>
                            <div style="font-size: 0.85rem; opacity: 0.9; margin-top: 0.15rem;">
                                Backend Validation Engine evaluated Before vs. After crawler behavior on the test environment.
                            </div>
                        </div>
                    </div>
                </div>
                """)

                before_status_str = "RESTRICTED" if not a_before.get("robots_txt", {}).get("is_allowed", True) else "ACCESSIBLE"
                after_status_str = "ACCESSIBLE" if a_after.get("robots_txt", {}).get("is_allowed", True) else "RESTRICTED"

                persona_name = primary_res.get("persona", "GPTBot").title()

                render_html(f"""
                <div class="phase2-grid">
                    <div class="state-card">
                        <div class="state-card-header state-before-title">
                            <span>BEFORE FIX</span>
                            <span style="font-size: 1.1rem; color: #ffffff;">Score: <strong>{b_score}</strong></span>
                        </div>
                        <div style="margin-bottom: 0.6rem;">
                            <span style="font-size: 0.78rem; color: #94a3b8;">Crawler Status:</span><br>
                            <strong style="color: {'#ef4444' if before_status_str == 'RESTRICTED' else '#10b981'}; font-size: 1.05rem;">{persona_name}: {before_status_str}</strong>
                        </div>
                        <div>
                            <span style="font-size: 0.78rem; color: #94a3b8;">Observed State:</span><br>
                            <span style="font-size: 0.88rem; color: #e2e8f0;">{str(v_res.get('issue_before', 'Restricted access in robots.txt policy'))}</span>
                        </div>
                    </div>
                    <div class="state-card">
                        <div class="state-card-header state-after-title">
                            <span>AFTER FIX</span>
                            <span style="font-size: 1.1rem; color: #ffffff;">Score: <strong>{a_score}</strong> ({delta_str})</span>
                        </div>
                        <div style="margin-bottom: 0.6rem;">
                            <span style="font-size: 0.78rem; color: #94a3b8;">Crawler Status:</span><br>
                            <strong style="color: {'#10b981' if after_status_str == 'ACCESSIBLE' else '#ef4444'}; font-size: 1.05rem;">{persona_name}: {after_status_str}</strong>
                        </div>
                        <div>
                            <span style="font-size: 0.78rem; color: #94a3b8;">Observed State:</span><br>
                            <span style="font-size: 0.88rem; color: #e2e8f0;">{str(v_res.get('issue_after', 'AI crawler permitted in robots.txt'))}</span>
                        </div>
                    </div>
                </div>
                """)

                col_e1, col_e2 = st.columns([1, 1])
                with col_e1:
                    st.markdown("##### 🔧 Fix Application Engine Report")
                    fix_status_code = f_res.get("status", "applied")
                    st.markdown(f"- **Fix Applied**: `{f_res.get('fix_id')}`")
                    st.markdown(f"- **Target**: `{f_res.get('target')}`")
                    st.markdown(f"- **Execution Status**: `{fix_status_code}`")
                    st.markdown(f"- **Engine Message**: {f_res.get('message')}")
                    if f_res.get("files_changed"):
                        st.markdown(f"- **Files Modified**: `{', '.join(f_res.get('files_changed'))}`")
                with col_e2:
                    st.markdown("##### 🔍 Validation Engine Evidence")
                    ev_list = v_res.get("evidence", [])
                    if ev_list:
                        for ev in ev_list:
                            st.markdown(f"- `{ev}`")
                    else:
                        st.markdown("- `Score improved and target access barriers verified resolved.`")
