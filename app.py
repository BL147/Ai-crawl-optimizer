"""
app.py - AI Crawl Optimizer UI & Demo Dashboard
Author: Shlok (System Integrator) & Team

Streamlit frontend connecting all pieces:
- Orchestrator (run_audit)
- Scoring Engine
- Live Sandbox Switcher (BEFORE vs AFTER)
- WAF & Robots.txt Remediation Generator
"""

import streamlit as st
import pandas as pd
from orchestrator import run_audit
from sandbox.server import start_sandbox, set_mode, get_mode

st.set_page_config(
    page_title="AI Crawl Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #334155;
        text-align: center;
    }
    .score-number {
        font-size: 56px;
        font-weight: 900;
        margin: 0;
    }
    .grade-badge {
        display: inline-block;
        font-size: 20px;
        font-weight: bold;
        padding: 4px 16px;
        border-radius: 20px;
        margin-top: 8px;
    }
    .badge-f { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }
    .badge-a { background: #064e3b; color: #6ee7b7; border: 1px solid #10b981; }
    .badge-b { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }
    .badge-c { background: #78350f; color: #fcd34d; border: 1px solid #f59e0b; }
</style>
""", unsafe_allow_html=True)

# Ensure sandbox is running in the background
sandbox_url = start_sandbox(port=5050)

# Sidebar: Controls & Pitch Tools
with st.sidebar:
    st.title("⚡ Control Center")
    st.markdown("**Role**: System Integrator")
    
    st.divider()
    st.subheader("🛠️ Demo Sandbox Control")
    current_mode = get_mode()
    
    if current_mode == "before":
        st.error("Sandbox: **BEFORE Mode** (AI Blocked with 403)")
    else:
        st.success("Sandbox: **AFTER Mode** (AI Optimized with 200)")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔴 Set BEFORE", use_container_width=True):
            set_mode("before")
            st.rerun()
    with col_btn2:
        if st.button("🟢 Set AFTER", use_container_width=True):
            set_mode("after")
            st.rerun()

    st.caption(f"Sandbox Server running on: `{sandbox_url}`")
    st.info("Use this during your pitch to demonstrate a guaranteed 403 to 200 transition!")

# Main Header
st.title("⚡ AI Crawl Optimizer")
st.markdown("### Generative Search Indexing Audit & Autonomous WAF Remediation")
st.caption("Inspect whether your website is visible or blocked by AI search crawlers (ChatGPT, Claude, Perplexity).")

# URL Audit Form
col_url, col_preset, col_btn = st.columns([4, 2, 1.5])
with col_url:
    target_url = st.text_input("Target URL to Audit", value=sandbox_url, label_visibility="collapsed")
with col_preset:
    preset = st.selectbox("Quick Presets", ["Sandbox (Local Enterprise)", "https://example.com", "https://wikipedia.org"], label_visibility="collapsed")
    if preset == "Sandbox (Local Enterprise)":
        target_url = sandbox_url
    elif preset:
        target_url = preset
with col_btn:
    run_button = st.button("🚀 Run Audit", type="primary", use_container_width=True)

if run_button or "audit_data" in st.session_state:
    if run_button:
        with st.spinner(f"Emulating multi-agent crawlers on {target_url}..."):
            st.session_state["audit_data"] = run_audit(target_url)

    result = st.session_state["audit_data"]
    summary = result["summary"]
    score = summary["score"]
    grade = summary["grade"]
    status_text = summary["status"]
    score_color = summary["color"]

    st.markdown("---")

    # Metrics Section
    col_m1, col_m2, col_m3, col_m4 = st.columns([2, 3, 2, 2])
    with col_m1:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 13px; color: #94a3b8; font-weight: bold;">AI CRAWLABILITY SCORE</div>
            <div class="score-number" style="color: {score_color};">{score}</div>
            <div class="grade-badge badge-{grade.lower()}">Grade: {grade} &bull; {status_text}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_m2:
        st.markdown("#### 📋 Executive Diagnosis")
        st.write(summary["text"])
        st.markdown(f"**Target Analyzed:** `{result['url']}`")
        st.markdown(f"**Timestamp:** `{result['timestamp']}`")

    with col_m3:
        st.metric("Total Penalties Deducted", f"-{result['scoring']['total_deductions']} pts", delta_color="inverse")
    with col_m4:
        robots_ai = result["robots_txt"].get("ai_disallowed", False)
        st.metric("Robots.txt AI Status", "BLOCKED" if robots_ai else "PERMITTED", delta="Policy Strict" if robots_ai else "Friendly")

    st.markdown("---")

    # Tabs for granular views
    tab1, tab2, tab3 = st.tabs(["🤖 Multi-Bot Emulation Matrix", "⚠️ Scoring Deductions", "💡 AI Remediation & WAF Rules"])

    with tab1:
        st.subheader("Crawl Response by User-Agent")
        bot_list = []
        for bot_id, info in result["bot_matrix"].items():
            status = info.get("status")
            blocked = info.get("blocked", False)
            bot_list.append({
                "User-Agent / Agent Name": bot_id.replace("_", " ").title(),
                "HTTP Status": status,
                "State": "⛔ BLOCKED" if blocked else "✅ PERMITTED",
                "WAF Detected": info.get("waf") or "None",
                "CAPTCHA / Challenge": "YES" if info.get("captcha") else "NO",
                "Latency (ms)": f"{info.get('latency_ms', 0)} ms"
            })
        df_bots = pd.DataFrame(bot_list)
        st.dataframe(df_bots, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Deduction Breakdown")
        penalties = result["scoring"].get("penalties", [])
        if not penalties:
            st.success("🎉 Zero penalties detected! The target website has optimal AI accessibility.")
        else:
            p_list = []
            for p in penalties:
                p_list.append({
                    "Category": p.get("category"),
                    "Deduction": f"{p.get('penalty')} pts",
                    "Severity": p.get("severity"),
                    "Factor": p.get("factor"),
                    "Technical Detail": p.get("detail")
                })
            st.dataframe(pd.DataFrame(p_list), use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Autonomous Optimization & Fixes")
        ai_rec = result["ai_recommendations"]
        
        st.markdown("#### 🔍 Root Cause Analysis")
        st.info(ai_rec["root_cause"])

        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.markdown("#### 🛡️ Cloudflare WAF Bypass Expression")
            st.caption("Paste into Cloudflare Dashboard -> Security -> WAF -> Custom Rules (Action: Skip/Allow)")
            st.code(ai_rec["cloudflare_waf_rule"], language="plaintext")

        with col_w2:
            st.markdown("#### 📄 AI-Optimized `robots.txt`")
            st.caption("Deploy this to your root web server to grant explicit indexing rights")
            st.code(ai_rec["robots_txt_fix"], language="robots")

        st.markdown("#### 🎯 Priority Action Items")
        for act in ai_rec["action_items"]:
            st.markdown(f"- {act}")
