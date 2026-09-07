"""
sandbox/server.py - Controlled Enterprise Demo Website
Author: Shlok (System Integrator)

Simulates an enterprise website protected by Cloudflare WAF.
Has two modes:
1. "BEFORE": Browser gets 200 OK, but AI crawlers (GPTBot, ClaudeBot, etc.) receive 403 Forbidden + Cloudflare Challenge.
2. "AFTER": Both Browser and AI crawlers receive 200 OK with clean markdown & meta tags.

Can be run standalone: `python sandbox/server.py --port 5050`
Or started programmatically via `start_sandbox()` in a background daemon thread.
"""

import sys
import threading
import time
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

# State: 'before' or 'after'
CURRENT_MODE = "before"

AI_USER_AGENTS = [
    "gptbot",
    "chatgpt-user",
    "claudebot",
    "claude-web",
    "anthropic-ai",
    "perplexitybot",
    "ccbot",
    "bytespider",
    "cohere-ai",
    "diffbot"
]

CLOUDFLARE_403_HTML = """<!DOCTYPE html>
<html lang="en-US">
<head>
    <title>Just a moment... | Attention Required</title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <meta name="robots" content="noindex, nofollow">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f6f6f7; color: #333; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); max-width: 540px; width: 90%; }
        h1 { font-size: 24px; color: #d97706; margin-top: 0; }
        p { font-size: 14px; line-height: 1.6; color: #4b5563; }
        .spinner { border: 4px solid #e5e7eb; border-top: 4px solid #f59e0b; border-radius: 50%; width: 36px; height: 36px; animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .footer { margin-top: 30px; font-size: 12px; color: #9ca3af; border-top: 1px solid #f3f4f6; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="spinner"></div>
        <h1>Checking your browser before accessing apexcloud.io</h1>
        <p>This process is automatic. Your browser will redirect to your requested content shortly.</p>
        <p>Please allow up to 5 seconds. Cloudflare Ray ID: <strong>89f4c3a218d0-BOM</strong></p>
        <div class="footer">
            DDoS protection by Cloudflare &bull; Ray ID: 89f4c3a218d0-BOM &bull; Performance & Security by Cloudflare
        </div>
    </div>
</body>
</html>"""

WEBSITE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ApexCloud AI - Next-Gen Autonomous Cloud Platform</title>
    <meta name="description" content="ApexCloud provides serverless GPU infrastructure and real-time AI agents for enterprises.">
    <style>
        :root { --primary: #6366f1; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --sub: #94a3b8; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; }
        .banner { background: {{ banner_bg }}; color: white; padding: 10px 20px; font-size: 13px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
        .toggle-btn { background: white; color: #1e293b; border: none; padding: 6px 14px; border-radius: 6px; font-weight: bold; cursor: pointer; }
        .nav { display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; border-bottom: 1px solid #334155; }
        .logo { font-size: 20px; font-weight: 800; color: #818cf8; }
        .hero { text-align: center; padding: 60px 20px; max-width: 800px; margin: 0 auto; }
        h1 { font-size: 42px; line-height: 1.2; margin-bottom: 16px; }
        p.lead { font-size: 18px; color: var(--sub); line-height: 1.6; margin-bottom: 30px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; max-width: 1000px; margin: 40px auto; padding: 0 20px; }
        .feature-card { background: var(--card); padding: 24px; border-radius: 12px; border: 1px solid #334155; }
        .feature-card h3 { margin-top: 0; color: #c7d2fe; }
        .feature-card p { font-size: 14px; color: var(--sub); line-height: 1.5; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; background: #312e81; color: #a5b4fc; }
    </style>
</head>
<body>
    <div class="banner">
        <span>DEMO SANDBOX STATUS: <strong>{{ mode_upper }}</strong> ({{ status_desc }})</span>
        <form method="POST" action="/api/sandbox/toggle" style="margin:0;">
            <button class="toggle-btn" type="submit">Toggle to {{ other_mode }}</button>
        </form>
    </div>

    <div class="nav">
        <div class="logo">⚡ ApexCloud AI</div>
        <div>
            <a href="/robots.txt" style="color: #94a3b8; margin-right: 20px; font-size: 14px; text-decoration: none;">robots.txt</a>
            <a href="/api/sandbox/mode" style="color: #94a3b8; font-size: 14px; text-decoration: none;">API Status</a>
        </div>
    </div>

    <div class="hero">
        <span class="badge">Enterprise Cloud Infrastructure</span>
        <h1>Scale AI Models with Zero Latency & Intelligent Sharding</h1>
        <p class="lead">
            ApexCloud powers over 400 Fortune 500 AI pipelines with distributed H100 GPU clusters,
            sub-millisecond inference endpoints, and automated vector database synchronization.
        </p>
    </div>

    <div class="grid">
        <div class="feature-card">
            <h3>🚀 Sub-millisecond GPU Clusters</h3>
            <p>Instant provisioning of NVIDIA H100 and B200 nodes with high-speed NVLink interconnects.</p>
        </div>
        <div class="feature-card">
            <h3>🧠 Autonomous Agent Runtimes</h3>
            <p>Deploy multi-agent swarms with persistent memory, tool access, and dynamic failovers.</p>
        </div>
        <div class="feature-card">
            <h3>🔒 Zero-Trust Security & WAF</h3>
            <p>Enterprise encryption with automated Cloudflare WAF protection and DDoS mitigation.</p>
        </div>
    </div>
</body>
</html>"""


def is_ai_crawler(user_agent: str) -> bool:
    """Checks if incoming user-agent is an AI search crawler."""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(bot in ua_lower for bot in AI_USER_AGENTS)


@app.route("/", methods=["GET"])
def home():
    global CURRENT_MODE
    user_agent = request.headers.get("User-Agent", "")

    # If in 'before' mode and request comes from an AI crawler -> 403 Forbidden with Cloudflare Challenge
    if CURRENT_MODE == "before" and is_ai_crawler(user_agent):
        headers = {
            "Server": "cloudflare",
            "cf-ray": "89f4c3a218d0-BOM",
            "cf-mitigated": "challenge",
            "Content-Type": "text/html; charset=UTF-8"
        }
        return Response(CLOUDFLARE_403_HTML, status=403, headers=headers)

    # In 'after' mode OR standard browser user-agent -> 200 OK
    headers = {
        "Server": "cloudflare",
        "Content-Type": "text/html; charset=UTF-8"
    }
    if CURRENT_MODE == "after" and is_ai_crawler(user_agent):
        headers["x-ai-optimized"] = "true"
        headers["x-crawl-budget"] = "unrestricted"

    banner_bg = "#dc2626" if CURRENT_MODE == "before" else "#16a34a"
    status_desc = "AI Bots Blocked with 403" if CURRENT_MODE == "before" else "AI Bots Allowed with 200 OK"
    other_mode = "AFTER (Optimized)" if CURRENT_MODE == "before" else "BEFORE (Blocked)"

    rendered = WEBSITE_HTML.replace("{{ banner_bg }}", banner_bg) \
                           .replace("{{ mode_upper }}", CURRENT_MODE.upper()) \
                           .replace("{{ status_desc }}", status_desc) \
                           .replace("{{ other_mode }}", other_mode)

    return Response(rendered, status=200, headers=headers)


@app.route("/robots.txt", methods=["GET"])
def robots():
    global CURRENT_MODE
    if CURRENT_MODE == "before":
        content = """User-agent: *
Allow: /

User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: PerplexityBot
Disallow: /
"""
    else:
        content = """User-agent: *
Allow: /

# AI Crawlers explicitly permitted
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

Sitemap: /sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@app.route("/api/sandbox/mode", methods=["GET", "POST"])
def sandbox_mode():
    global CURRENT_MODE
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        new_mode = data.get("mode", "").lower()
        if new_mode in ["before", "after"]:
            CURRENT_MODE = new_mode
            return jsonify({"status": "success", "mode": CURRENT_MODE})
        return jsonify({"status": "error", "message": "Mode must be 'before' or 'after'"}), 400

    return jsonify({"mode": CURRENT_MODE, "desc": "AI blocked with 403" if CURRENT_MODE == "before" else "AI allowed with 200"})


@app.route("/api/sandbox/toggle", methods=["POST", "GET"])
def sandbox_toggle():
    global CURRENT_MODE
    CURRENT_MODE = "after" if CURRENT_MODE == "before" else "before"
    # If called from a web browser form, redirect back to homepage
    if "text/html" in request.headers.get("Accept", ""):
        return f"<script>window.location.href='/';</script>"
    return jsonify({"status": "success", "mode": CURRENT_MODE})


def set_mode(mode: str):
    """Programmatic control for tests and orchestrator."""
    global CURRENT_MODE
    if mode in ["before", "after"]:
        CURRENT_MODE = mode


def get_mode() -> str:
    global CURRENT_MODE
    return CURRENT_MODE


import socket
import urllib.request

_server_threads = {}
_server_lock = threading.Lock()
_server_thread = None


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_sandbox(port: int = 5050) -> str:
    """Starts sandbox in background daemon thread if not already running on the given port."""
    global _server_threads, _server_thread
    with _server_lock:
        thread = _server_threads.get(port)
        if thread is None or not thread.is_alive():
            if not _is_port_in_use(port):
                t = threading.Thread(
                    target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
                    daemon=True
                )
                t.start()
                _server_threads[port] = t
                _server_thread = t

            # Wait until the server is responsive on this port
            deadline = time.time() + 5.0
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/sandbox/mode", timeout=0.5):
                        break
                except Exception:
                    time.sleep(0.05)
    return f"http://127.0.0.1:{port}"



if __name__ == "__main__":
    port = 5050
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    print(f"[*] Starting Sandbox Enterprise Demo Website on http://127.0.0.1:{port}")
    print(f"[*] Current Mode: {CURRENT_MODE.upper()}")
    print("[*] Toggle mode: POST/GET http://127.0.0.1:5050/api/sandbox/toggle")
    app.run(host="127.0.0.1", port=port, debug=False)
