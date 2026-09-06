import streamlit as st
import time
from urllib.parse import urlparse
import pandas as pd

from crawler import list_personas
from orchestration import run_audit

# Page configuration
st.set_page_config(
    page_title="AI Accessibility Auditor",
    page_icon="🤖",
    layout="wide"
)

# Custom Styling
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Custom Styling - Modern Glassmorphism & High Contrast Dark Theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Gradient Header */
    .hero-container {
        background: radial-gradient(circle at 15% 20%, rgba(59, 130, 246, 0.15) 0%, transparent 40%),
                    radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.12) 0%, transparent 40%),
                    linear-gradient(180deg, rgba(15, 23, 42, 0.7) 0%, rgba(15, 23, 42, 0.2) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 2rem;
        backdrop-filter: blur(12px);
    }
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FFFFFF 20%, #94A3B8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.4rem;
        letter-spacing: -0.03em;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 1.2rem;
        line-height: 1.5;
    }
    
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.35rem 0.9rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .status-pill-active {
        background: rgba(16, 185, 129, 0.12);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .status-pill-fallback {
        background: rgba(245, 158, 11, 0.12);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }

    /* Cards */
    .score-card {
        background: linear-gradient(145deg, #131E33 0%, #0B132B 100%);
        border: 1px solid rgba(59, 130, 246, 0.25);
        border-radius: 20px;
        padding: 2.2rem 1.8rem;
        text-align: center;
        color: white;
        margin: 0.5rem 0;
        box-shadow: 0 20px 35px -10px rgba(0, 0, 0, 0.45);
        position: relative;
        overflow: hidden;
    }
    .score-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899);
    }
    .score-label {
        font-size: 0.85rem;
        letter-spacing: 0.14em;
        font-weight: 700;
        text-transform: uppercase;
        color: #94A3B8;
        margin-bottom: 0.5rem;
    }
    .score-num {
        font-size: 4.6rem;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.05em;
        background: linear-gradient(180deg, #FFFFFF 30%, #CBD5E1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .score-denom {
        font-size: 1.25rem;
        color: #64748B;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .risk-badge {
        display: inline-block;
        padding: 0.4rem 1.4rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .risk-high {
        background-color: rgba(239, 68, 68, 0.18);
        color: #F87171;
        border: 1px solid #EF4444;
    }
    .risk-medium {
        background-color: rgba(245, 158, 11, 0.18);
        color: #FBBF24;
        border: 1px solid #F59E0B;
    }
    .risk-low {
        background-color: rgba(34, 197, 94, 0.18);
        color: #4ADE80;
        border: 1px solid #22C55E;
    }
    
    .results-card {
        background: linear-gradient(145deg, #131E33 0%, #0E172A 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        margin-top: 0.5rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .result-item {
        font-size: 1.02rem;
        color: #E2E8F0 !important;
        padding: 0.5rem 0;
        display: flex;
        align-items: center;
        gap: 0.85rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .result-item:last-child {
        border-bottom: none;
    }
    .status-pass { color: #34D399 !important; font-weight: 800; font-size: 1.25rem; }
    .status-fail { color: #F87171 !important; font-weight: 800; font-size: 1.25rem; }
    .status-warn { color: #FBBF24 !important; font-weight: 800; font-size: 1.25rem; }
    
    /* Audit Form Styling */
    div[data-testid="stForm"] {
        background: rgba(19, 30, 51, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 1.8rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 15px 30px rgba(0, 0, 0, 0.25);
    }

    /* Remediation Callout Card */
    .remediation-box {
        background: linear-gradient(145deg, #101B2E 0%, #090F1E 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 18px;
        padding: 2rem 2.2rem;
        margin-top: 1rem;
        box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.4);
    }
    .remediation-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.4);
        color: #A5B4FC;
        border-radius: 9999px;
        padding: 0.35rem 1rem;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Environment API Key Detection Check (No sidebar key input)
has_env_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY"))

# Clean Sidebar: Information & Guidance Only (No API key bar)
with st.sidebar:
    st.markdown("### 🤖 System Configuration")
    if has_env_key:
        st.markdown("""
        <div style="background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.35); border-radius: 12px; padding: 1rem; color: #34D399;">
            <div style="font-weight: 700; font-size: 0.95rem; margin-bottom: 0.3rem;">✓ LLM Engine Configured</div>
            <div style="font-size: 0.8rem; color: #A7F3D0; line-height: 1.4;">
                API key detected from <code>.env</code> file. Generative remediation and AI synthesis are fully enabled.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.35); border-radius: 12px; padding: 1rem; color: #FBBF24;">
            <div style="font-weight: 700; font-size: 0.95rem; margin-bottom: 0.3rem;">ℹ️ Deterministic Grounded Engine</div>
            <div style="font-size: 0.8rem; color: #FDE68A; line-height: 1.4;">
                To enable Gemini AI reasoning, add your API key to <code>.env</code>:<br>
                <code>GEMINI_API_KEY=your_key_here</code>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🎯 Supported AI Crawlers")
    st.caption("• **OpenAI GPTBot** (ChatGPT Search & Retrieval)\n• **Anthropic ClaudeBot** (Claude Web Indexer)\n• **PerplexityBot** (Realtime AI Answer Engine)\n• **ByteSpider** (Douyin / TikTok AI Bot)\n• **Google-Extended** (Bard / Gemini Web Training)")
    st.markdown("---")
    st.caption("AI Crawl Optimizer v2.5 • Zero-Hallucination Grounded Remediation")

# App Hero Banner
engine_pill = '<span class="status-pill status-pill-active">⚡ Gemini 2.5 Generative Fix Active</span>' if has_env_key else '<span class="status-pill status-pill-fallback">🛡️ Grounded Remediation Active (.env key optional)</span>'

st.markdown(f"""
<div class="hero-container">
    <div class="main-title">🌐 AI Accessibility & Bot Optimizer</div>
    <div class="sub-title">Audit multi-persona AI crawler compatibility, detect edge WAF challenges, and generate instant, production-ready code fixes.</div>
    {engine_pill}
</div>
""", unsafe_allow_html=True)

# Controls & Form
available_personas = list_personas()
ai_persona_keys = [p["id"] for p in available_personas if p["is_ai_agent"]]

with st.form("audit_form"):
    col1, col2 = st.columns([2.5, 1.5])
    with col1:
        url_input = st.text_input(
            "Target Website URL:",
            placeholder="https://example.com",
            help="Enter target website or domain to audit for AI crawler accessibility"
        )
    with col2:
        audit_mode = st.radio(
            "Audit Mode:",
            options=["Multi-Persona Matrix (All AI Bots)", "Single Persona Target"],
            horizontal=True,
            index=0
        )

    selected_personas = []
    if audit_mode == "Single Persona Target":
        chosen_persona = st.selectbox(
            "Select AI Persona to simulate:",
            options=ai_persona_keys,
            format_func=lambda pid: next((p["display_name"] for p in available_personas if p["id"] == pid), pid),
            index=0
        )
        selected_personas = [chosen_persona]
    else:
        selected_personas = ["gptbot", "claudebot", "perplexitybot", "bytespider", "google_extended"]

    include_baseline = st.checkbox("Compare against standard Desktop Chrome baseline (to verify selective AI blocking)", value=True)
    submit_button = st.form_submit_button("🚀 START AUDIT", type="primary", use_container_width=True)

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def render_remediation(advice: dict) -> None:
    if advice.get("model_used"):
        st.markdown(
            '<div class="remediation-badge">✨ Generated by Gemini AI Reasoning Engine</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="remediation-badge" style="background: rgba(59,130,246,0.15); border-color: rgba(59,130,246,0.4); color: #93C5FD;">🛡️ Deterministic Grounded Engine (RFC 9309 & WAF Spec)</div>',
            unsafe_allow_html=True,
        )
        if advice.get("uncertainty"):
            st.info(f"ℹ️ {advice['uncertainty']}")

    st.markdown(
        f'<div class="remediation-box"><strong>Problem:</strong> {advice.get("problem_detected", "No remediation required.")}<br><br><strong>Recommendation:</strong> {advice.get("recommended_fix", "")}</div>',
        unsafe_allow_html=True,
    )
    if advice.get("code_or_configuration_change"):
        st.code(advice["code_or_configuration_change"])

# Run Audit Flow
if submit_button:
    if not url_input.strip():
        st.error("Please enter a valid website URL.")
    else:
        norm_url = normalize_url(url_input)

        # Scanning step animation
        scan_box = st.container()
        with scan_box:
            st.markdown("#### Scanning website...")
            status_placeholder = st.empty()

            step_items = [
                "✓ Connecting",
                "✓ Testing browser",
                "✓ Testing AI persona",
                "✓ Checking robots.txt",
                "✓ Analyzing responses"
            ]

            rendered = []
            for item in step_items:
                rendered.append(item)
                status_placeholder.markdown("\n\n".join(rendered))
                time.sleep(0.2)

        # Execute through the finalized crawler, scoring, and remediation pipeline.
        with st.spinner(f"Auditing {len(selected_personas)} personas via Chromium engine..."):
            try:
                results = [
                    run_audit(
                        norm_url,
                        persona=persona,
                        include_baseline=include_baseline,
                        headless=True,
                        timeout_seconds=12.0,
                    )
                    for persona in selected_personas
                ]
            except Exception as e:
                st.error(f"Audit failed to execute: {str(e)}")
                st.stop()

        # Isolate results
        ai_results = results
        primary_res = ai_results[0]
        baseline_result = primary_res.get("baseline")

        score = primary_res.get("summary", {}).get("score", 0)
        risk_label = primary_res.get("summary", {}).get("risk_level", "HIGH RISK")
        risk_class = {
            "HIGH RISK": "risk-high",
            "MEDIUM RISK": "risk-medium",
            "LOW RISK": "risk-low",
        }.get(risk_label, "risk-high")

        # Top Display: Score & Quick Detection Checklist
        top_col1, top_col2 = st.columns([1.2, 1.8])
        with top_col1:
            st.markdown(f"""
            <div class="score-card">
                <div class="score-label">AI ACCESSIBILITY SCORE</div>
                <div class="score-num">{score}</div>
                <div class="score-denom">/ 100</div>
                <span class="risk-badge {risk_class}">{risk_label}</span>
            </div>
            """, unsafe_allow_html=True)

        with top_col2:
            st.markdown("### Detection Results")
            http_data = primary_res.get("http", {})
            robots_data = primary_res.get("robots_txt", {})
            detection = primary_res.get("detection", {})
            inference = detection.get("inference", {})

            status_code = http_data.get("status_code")
            is_blocked = detection.get("is_blocked", False)
            mechanism = str(inference.get("mechanism", "NONE")).upper()
            robots_exists = robots_data.get("exists", False)
            robots_allowed = robots_data.get("is_allowed", True)
            is_challenge = mechanism not in ["NONE", "HTTP_FORBIDDEN", "INCONCLUSIVE", ""]

            reachable = primary_res.get("success") or (status_code is not None)
            reachable_icon = "✓" if reachable else "✗"
            reachable_class = "status-pass" if reachable else "status-fail"
            reachable_text = "Website reachable" if reachable else "Website unreachable"

            robots_icon = "✓" if robots_exists else "✗"
            robots_class = "status-pass" if robots_exists else "status-fail"
            robots_text = "robots.txt found" if robots_exists else "robots.txt not found"

            ai_icon = "✗" if (is_blocked or not robots_allowed or status_code in [403, 401]) else "✓"
            ai_class = "status-fail" if (is_blocked or not robots_allowed or status_code in [403, 401]) else "status-pass"
            ai_text = "AI crawler blocked" if (is_blocked or not robots_allowed or status_code in [403, 401]) else "AI crawler allowed"

            if status_code == 200:
                http_icon = "✓"
                http_class = "status-pass"
                http_text = "HTTP 200 OK"
            elif status_code in [403, 401]:
                http_icon = "✗"
                http_class = "status-fail"
                http_text = f"HTTP {status_code}"
            elif status_code is not None:
                http_icon = "⚠"
                http_class = "status-warn"
                http_text = f"HTTP {status_code}"
            else:
                http_icon = "✗"
                http_class = "status-fail"
                http_text = "HTTP failed"

            challenge_icon = "⚠" if is_challenge else "✓"
            challenge_class = "status-warn" if is_challenge else "status-pass"
            challenge_text = f"Bot challenge detected ({mechanism})" if is_challenge else "No bot challenge detected"

            st.markdown(f"""
            <div class="results-card">
                <div class="result-item"><span class="{reachable_class}">{reachable_icon}</span> {reachable_text}</div>
                <div class="result-item"><span class="{robots_class}">{robots_icon}</span> {robots_text}</div>
                <div class="result-item"><span class="{ai_class}">{ai_icon}</span> {ai_text}</div>
                <div class="result-item"><span class="{http_class}">{http_icon}</span> {http_text}</div>
                <div class="result-item"><span class="{challenge_class}">{challenge_icon}</span> {challenge_text}</div>
            </div>
            """, unsafe_allow_html=True)

        # MULTI-PERSONA MATRIX SECTION
        st.write("---")
        st.markdown("### 🤖 Multi-Persona AI Compliance & Access Matrix")
        st.caption("Cross-audit comparing major AI assistants against a standard desktop Chrome browser baseline.")

        matrix_rows = []
        matrix_results = list(results)
        if baseline_result:
            matrix_results.append(baseline_result)
        for r in matrix_results:
            p_id = r.get("persona")
            p_name = next((p["display_name"] for p in available_personas if p["id"] == p_id), p_id or "Standard Chrome")
            r_http = r.get("http", {})
            r_robots = r.get("robots_txt", {})
            r_det = r.get("detection", {})
            r_inf = r_det.get("inference", {})

            st_code = r_http.get("status_code")
            is_b = r_det.get("is_blocked", False)
            mech = str(r_inf.get("mechanism", "NONE"))
            verdict = str(r_inf.get("verdict", "ACCESSIBLE"))
            allowed_txt = "✅ Allowed" if r_robots.get("is_allowed", True) else "❌ Disallowed"
            
            # Status icon
            if is_b or st_code in [403, 401]:
                access_status = f"❌ Blocked ({st_code or 'Denied'})"
            elif st_code == 200:
                access_status = "✅ Accessible (200 OK)"
            else:
                access_status = f"⚠ Status {st_code}"

            matrix_rows.append({
                "Persona": p_name,
                "Access Status": access_status,
                "robots.txt Policy": allowed_txt,
                "WAF / Bot Detection": mech if mech != "NONE" else "None Detected",
                "Verdict": verdict,
                "Latency": f"{r_http.get('response_time_ms', 0)} ms"
            })

        matrix_df = pd.DataFrame(matrix_rows)
        st.dataframe(matrix_df, use_container_width=True, hide_index=True)

        # Differential Baseline Analysis
        if baseline_result and ai_results:
            base_status = baseline_result.get("http", {}).get("status_code")
            ai_blocked_any = any(
                r.get("detection", {}).get("is_blocked") or r.get("http", {}).get("status_code") in [403, 401]
                for r in ai_results
            )
            if base_status == 200 and ai_blocked_any:
                st.warning("⚠️ **Selective AI Blocking Confirmed**: Standard desktop browsers receive 200 OK, but AI crawler personas are blocked or challenged by edge WAF/bot management rules!")
            elif base_status == 200 and not ai_blocked_any:
                st.success("✅ **Consistent Access**: Both AI assistants and human browsers have unimpeded access.")

        # Senior Remediation Engine
        st.write("---")
        st.markdown("### 🛠️ Senior Engineer Diagnostic & Remediation Plan")

        render_remediation(primary_res.get("remediation", {}))

