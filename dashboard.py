import streamlit as st
import time
from urllib.parse import urlparse
import pandas as pd

from crawler import crawl_sync, crawl_all_sync, crawl_with_baseline_sync, list_personas
from remediation_engine import RemediationEngine

# Page configuration
st.set_page_config(
    page_title="AI Accessibility Auditor",
    page_icon="🤖",
    layout="wide"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1rem;
        opacity: 0.75;
        margin-bottom: 1.5rem;
    }
    .score-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        color: white;
        margin: 1.2rem 0;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15);
    }
    .score-label {
        font-size: 0.95rem;
        letter-spacing: 0.12em;
        font-weight: 600;
        text-transform: uppercase;
        color: #94A3B8;
        margin-bottom: 0.5rem;
    }
    .score-num {
        font-size: 4.5rem;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.04em;
    }
    .score-denom {
        font-size: 1.4rem;
        color: #64748B;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .risk-badge {
        display: inline-block;
        padding: 0.35rem 1.2rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .risk-high {
        background-color: rgba(239, 68, 68, 0.2);
        color: #F87171;
        border: 1px solid #EF4444;
    }
    .risk-medium {
        background-color: rgba(245, 158, 11, 0.2);
        color: #FBBF24;
        border: 1px solid #F59E0B;
    }
    .risk-low {
        background-color: rgba(34, 197, 94, 0.2);
        color: #4ADE80;
        border: 1px solid #22C55E;
    }
    .results-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-top: 0.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .result-item {
        font-size: 1.05rem;
        color: #F1F5F9 !important;
        padding: 0.35rem 0;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .status-pass { color: #4ADE80 !important; font-weight: 800; font-size: 1.15rem; }
    .status-fail { color: #F87171 !important; font-weight: 800; font-size: 1.15rem; }
    .status-warn { color: #FBBF24 !important; font-weight: 800; font-size: 1.15rem; }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown('<div class="main-title">AI Accessibility Auditor</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Multi-Persona AI Crawler Compatibility, WAF Challenge, & Bot Management Auditor</div>', unsafe_allow_html=True)

# Controls & Form
available_personas = list_personas()
ai_persona_keys = [p["id"] for p in available_personas if p["is_ai_agent"]]

with st.form("audit_form"):
    col1, col2 = st.columns([2.5, 1.5])
    with col1:
        url_input = st.text_input(
            "Enter website:",
            placeholder="https://example.com",
            help="Provide the target domain or URL"
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

    include_baseline = st.checkbox("Compare against standard Desktop Chrome baseline (to prove selective AI blocking)", value=True)
    submit_button = st.form_submit_button("START AUDIT", type="primary", use_container_width=True)

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def compute_score_and_risk(crawl_res: dict):
    http_data = crawl_res.get("http", {})
    robots_data = crawl_res.get("robots_txt", {})
    detection = crawl_res.get("detection", {})
    inference = detection.get("inference", {})

    status_code = http_data.get("status_code")
    is_blocked = detection.get("is_blocked", False)
    mechanism = str(inference.get("mechanism", "NONE")).upper()
    is_allowed_robots = robots_data.get("is_allowed", True)
    robots_exists = robots_data.get("exists", False)

    score = 100

    if not crawl_res.get("success") and status_code is None:
        return 0, "HIGH RISK", "risk-high"

    if is_blocked:
        score -= 35
    if status_code in [403, 401]:
        score -= 20
    elif status_code in [429, 503]:
        score -= 15
    if mechanism not in ["NONE", "HTTP_FORBIDDEN", "INCONCLUSIVE", ""]:
        score -= 20
    if robots_exists and not is_allowed_robots:
        score -= 25

    score = max(5, min(score, 100))

    if score < 50:
        return score, "HIGH RISK", "risk-high"
    elif score < 75:
        return score, "MEDIUM RISK", "risk-medium"
    else:
        return score, "LOW RISK", "risk-low"

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

        # Execution
        target_list = list(selected_personas)
        if include_baseline and "standard_browser" not in target_list:
            target_list.append("standard_browser")

        with st.spinner(f"Simulating {len(target_list)} personas via Chromium engine..."):
            try:
                results = crawl_all_sync(norm_url, personas=target_list, headless=True, timeout_seconds=12.0)
            except Exception as e:
                st.error(f"Audit failed to execute: {str(e)}")
                st.stop()

        # Isolate results
        ai_results = [r for r in results if r.get("persona") != "standard_browser"]
        baseline_result = next((r for r in results if r.get("persona") == "standard_browser"), None)

        # Compute aggregate or primary score
        primary_res = ai_results[0] if ai_results else results[0]
        score, risk_label, risk_class = compute_score_and_risk(primary_res)

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
        for r in results:
            p_id = r.get("persona")
            p_name = next((p["display_name"] for p in available_personas if p["id"] == p_id), p_id)
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
        
        engine = RemediationEngine()
        advice = engine.generate_remediation(primary_res)
        st.markdown(advice.format_markdown())
