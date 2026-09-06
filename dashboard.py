import streamlit as st
import requests
import time
from urllib.parse import urlparse

# Page configuration
st.set_page_config(
    page_title="AI Accessibility Auditor",
    page_icon="🤖",
    layout="centered"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        color: #1E293B;
    }
    .sub-title {
        font-size: 1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .score-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        color: white;
        margin: 1.8rem 0;
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
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-top: 1rem;
    }
    .result-item {
        font-size: 1.05rem;
        padding: 0.35rem 0;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .status-pass { color: #16A34A; font-weight: 700; }
    .status-fail { color: #DC2626; font-weight: 700; }
    .status-warn { color: #D97706; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown('<div class="main-title">AI Accessibility Auditor</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Inspect bot management, crawler accessibility, and WAF challenge posture</div>', unsafe_allow_html=True)

# User Input Form
with st.form("audit_form"):
    url_input = st.text_input(
        "Enter website:",
        placeholder="https://example.com",
        help="Provide full URL or domain"
    )
    submit_button = st.form_submit_button("START AUDIT", type="primary", use_container_width=True)

AI_USER_AGENT = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)"
BROWSER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def audit_target(target_url: str):
    parsed = urlparse(target_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base_url}/robots.txt"

    results = {
        "reachable": False,
        "robots_found": False,
        "robots_disallowed": False,
        "browser_ok": False,
        "ai_blocked": False,
        "ai_status": None,
        "browser_status": None,
        "challenge_detected": False,
        "evidence_headers": {},
        "detected_vendor": None
    }

    # 1. Connect & test standard browser request
    try:
        browser_res = requests.get(
            target_url,
            headers={"User-Agent": BROWSER_USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=10,
            allow_redirects=True
        )
        results["reachable"] = True
        results["browser_status"] = browser_res.status_code
        results["browser_ok"] = (browser_res.status_code == 200)
    except requests.RequestException:
        results["reachable"] = False
        return results

    # 2. Check robots.txt
    try:
        robots_res = requests.get(
            robots_url,
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=8
        )
        if robots_res.status_code == 200:
            results["robots_found"] = True
            content = robots_res.text.lower()
            if any(agent in content for agent in ["gptbot", "ccbot", "claudebot", "anthropic-ai", "perplexitybot"]):
                results["robots_disallowed"] = True
    except requests.RequestException:
        results["robots_found"] = False

    # 3. Test AI Crawler Persona
    try:
        ai_res = requests.get(
            target_url,
            headers={
                "User-Agent": AI_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            },
            timeout=10,
            allow_redirects=True
        )
        results["ai_status"] = ai_res.status_code
        results["evidence_headers"] = dict(ai_res.headers)
        body_sample = ai_res.text[:1500].lower()

        # Check for challenge or blocking signatures
        challenge_signatures = [
            "cf-chl-bypass", "turnstile", "interstitial", "just a moment...",
            "ddos-guard", "verify you are human", "perimeterx", "px-captcha",
            "access denied", "security check", "incapsula_resource", "waf"
        ]

        if any(sig in body_sample for sig in challenge_signatures):
            results["challenge_detected"] = True

        if "cf-ray" in ai_res.headers or "cf-cache-status" in ai_res.headers:
            results["detected_vendor"] = "Cloudflare"
        elif "x-amz-cf-id" in ai_res.headers:
            results["detected_vendor"] = "AWS CloudFront / AWS WAF"
        elif "x-akamai-transformed" in ai_res.headers:
            results["detected_vendor"] = "Akamai"

        if ai_res.status_code in [401, 403, 429, 503] or results["challenge_detected"]:
            results["ai_blocked"] = True
        else:
            results["ai_blocked"] = False

    except requests.RequestException:
        results["ai_blocked"] = True
        results["ai_status"] = 504

    return results

def compute_score(res):
    score = 100
    if not res["reachable"]:
        return 0, "HIGH RISK", "risk-high"
    
    if not res["robots_found"]:
        score -= 10
    if res["robots_disallowed"]:
        score -= 15
    if res["ai_blocked"]:
        score -= 25
    if res["ai_status"] in [403, 401]:
        score -= 15
    elif res["ai_status"] in [429, 503]:
        score -= 10
    if res["challenge_detected"]:
        score -= 20

    score = max(10, min(score, 100))

    if score < 50:
        return score, "HIGH RISK", "risk-high"
    elif score < 75:
        return score, "MEDIUM RISK", "risk-medium"
    else:
        return score, "LOW RISK", "risk-low"

# Run Audit Flow
if submit_button:
    if not url_input.strip():
        st.error("Please enter a website URL.")
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
                time.sleep(0.3)

        # Perform live audit
        audit_res = audit_target(norm_url)
        score, risk_label, risk_class = compute_score(audit_res)

        # AI ACCESSIBILITY SCORE Section
        st.markdown(f"""
        <div class="score-card">
            <div class="score-label">AI ACCESSIBILITY SCORE</div>
            <div class="score-num">{score}</div>
            <div class="score-denom">/ 100</div>
            <span class="risk-badge {risk_class}">{risk_label}</span>
        </div>
        """, unsafe_allow_html=True)

        # Detection Results
        st.markdown("### Detection Results")

        reachable_icon = "✓" if audit_res["reachable"] else "✗"
        reachable_class = "status-pass" if audit_res["reachable"] else "status-fail"
        reachable_text = "Website reachable" if audit_res["reachable"] else "Website unreachable"

        robots_icon = "✓" if audit_res["robots_found"] else "✗"
        robots_class = "status-pass" if audit_res["robots_found"] else "status-fail"
        robots_text = "robots.txt found" if audit_res["robots_found"] else "robots.txt not found"

        ai_icon = "✗" if audit_res["ai_blocked"] else "✓"
        ai_class = "status-fail" if audit_res["ai_blocked"] else "status-pass"
        ai_text = "AI crawler blocked" if audit_res["ai_blocked"] else "AI crawler allowed"

        status_code = audit_res["ai_status"] if audit_res["ai_status"] is not None else "N/A"
        if status_code == 200:
            http_icon = "✓"
            http_class = "status-pass"
            http_text = f"HTTP {status_code} OK"
        elif status_code in [403, 401]:
            http_icon = "✗"
            http_class = "status-fail"
            http_text = f"HTTP {status_code}"
        else:
            http_icon = "⚠"
            http_class = "status-warn"
            http_text = f"HTTP {status_code}"

        challenge_icon = "⚠" if audit_res["challenge_detected"] else "✓"
        challenge_class = "status-warn" if audit_res["challenge_detected"] else "status-pass"
        challenge_text = "Bot challenge detected" if audit_res["challenge_detected"] else "No bot challenge detected"

        st.markdown(f"""
        <div class="results-card">
            <div class="result-item"><span class="{reachable_class}">{reachable_icon}</span> {reachable_text}</div>
            <div class="result-item"><span class="{robots_class}">{robots_icon}</span> {robots_text}</div>
            <div class="result-item"><span class="{ai_class}">{ai_icon}</span> {ai_text}</div>
            <div class="result-item"><span class="{http_class}">{http_icon}</span> {http_text}</div>
            <div class="result-item"><span class="{challenge_class}">{challenge_icon}</span> {challenge_text}</div>
        </div>
        """, unsafe_allow_html=True)

        # Diagnostic & Remediation Plan Output
        st.write("---")
        server_header = audit_res["evidence_headers"].get("Server", audit_res["evidence_headers"].get("server", "Not disclosed"))
        vendor_hint = audit_res["detected_vendor"] or "Undisclosed / Generic WAF"

        st.markdown(f"""
### 1. Diagnostic Assessment
- **Severity**: {'Critical' if score < 50 else 'Medium' if score < 75 else 'Low'}
- **Observed Evidence**:
  - Target URL: `{norm_url}`
  - Standard Browser Status: `HTTP {audit_res['browser_status']}`
  - AI Persona (`GPTBot`) Status: `HTTP {status_code}`
  - Server Header: `{server_header}`
  - Interstitial Challenge Detected: `{audit_res['challenge_detected']}`
  - Identified Platform Signature: `{vendor_hint}`
- **Likely Cause**: Upstream edge proxy or bot management rules classify AI crawler user-agent strings as suspicious automated traffic or scrapers, triggering managed challenge / 403 Forbidden responses while browser traffic passes.

### 2. Remediation Strategy
- **Recommended Remediation**:
  1. Update edge WAF rules to distinguish recognized AI crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`) from hostile scrapers.
  2. Implement reverse-DNS / ASN verification to validate crawler authenticity without opening blanket access.
  3. Align `robots.txt` policy to explicitly define allowed sections and crawl-rate limits for AI bots.
- **Remediation Category**: WAF Rules | Bot Management | robots.txt
- **Potential Side Effects**: Increased origin server fetch load from AI crawlers; spoofing risk if User-Agent validation is not paired with IP / rDNS verification.

### 3. Production Code / Configuration Fix
""")

        st.code("""# Cloudflare WAF Rule Expression Example:
# (http.user_agent contains "GPTBot" and cf.client.bot) or (http.user_agent contains "ClaudeBot")
# Action: Skip Bot Fight Mode / Allow

# NGINX Reverse Proxy Directive:
map $http_user_agent $is_ai_crawler {
    default 0;
    "~*(GPTBot|ClaudeBot|PerplexityBot)" 1;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    location / {
        # Custom rate limiting zone for AI agents instead of outright 403
        limit_req zone=ai_crawlers burst=15 nodelay;
        proxy_pass http://origin_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
""", language="nginx")
