"""
CineStream - Streaming Platform Demo Website
Designed for live demonstration and auditing with AI Crawl Optimizer.

==============================================================================
HACKATHON PRESENTATION CONTROLS (Change these settings to toggle demo behavior)
==============================================================================
"""

import json
import os
import threading
import time
from flask import Flask, render_template, request, Response, jsonify

# ----------------------------------------------------------------------------
# DEMO CONFIGURATION (TOGGLE THESE DURING PRESENTATION)
# ----------------------------------------------------------------------------
BLOCK_AI_BOTS = False        # LINE 16: Change to True to block AI crawlers with HTTP 403
BLOCK_IN_ROBOTS_TXT = True  # LINE 17: Change to True to add AI Disallow rules to robots.txt
PORT = 5050                  # Port 5050 avoids macOS AirPlay Receiver port 5000 conflict
# ----------------------------------------------------------------------------

app = Flask(__name__, static_folder="static", template_folder="templates")

# AI bot user-agent tokens recognized by AI Crawl Optimizer
AI_BOT_PATTERNS = [
    "gptbot",
    "claudebot",
    "anthropic-ai",
    "perplexitybot",
    "google-extended",
    "bytespider",
    "cohere-ai",
    "ccbot",
    "oai-searchbot",
    "diffbot",
]

RESTRICTIONS_PATH = os.path.join(os.path.dirname(__file__), "restrictions.json")


def get_active_restrictions() -> dict:
    """Read simulated restriction controls from disk on each request."""
    if os.path.exists(RESTRICTIONS_PATH):
        try:
            with open(RESTRICTIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def is_bot_in_restriction(restriction_name: str, user_agent: str) -> bool:
    """Check if the user_agent is specifically targeted by the given active restriction."""
    if not user_agent:
        return False
    restrictions = get_active_restrictions()
    cfg = restrictions.get(restriction_name, {})
    if not cfg.get("enabled", False):
        return False
    target_bots = cfg.get("personas", [])
    ua_lower = user_agent.lower()
    return any(b.lower() in ua_lower for b in target_bots)


def is_ai_crawler(user_agent: str) -> bool:
    """Check if the incoming request User-Agent matches known AI crawler signatures."""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(bot in ua_lower for bot in AI_BOT_PATTERNS)


@app.route("/")
def home():
    """Main landing page. Handles regular browsers, AI restrictions, and simulated bot blocks."""
    user_agent = request.headers.get("User-Agent", "")

    # 1. AI Rate Limiting Simulation (HTTP 429)
    if is_bot_in_restriction("rate_limit", user_agent):
        resp_headers = {
            "Retry-After": "60",
            "Content-Type": "text/plain",
        }
        return Response("Too Many Requests: rate limit exceeded for bot crawler.", status=429, headers=resp_headers)

    # 2. WAF / Turnstile Challenge Simulation
    if is_bot_in_restriction("waf_challenge", user_agent):
        html_cf = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Just a moment...</title>
    <style>body { background: #000; color: #fff; font-family: sans-serif; }</style>
</head>
<body>
    <div id="challenge-stage">
        <div class="cf-turnstile"></div>
        <form id="challenge-form"></form>
    </div>
    <p>Checking your browser before accessing...</p>
</body>
</html>"""
        resp_headers = {
            "Server": "cloudflare",
            "cf-ray": "8e123456789abcde-IAD",
            "Content-Type": "text/html",
        }
        return Response(html_cf, status=403, headers=resp_headers)

    # 3. Interactive CAPTCHA Simulation
    if is_bot_in_restriction("captcha", user_agent):
        html_captcha = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Security Verification</title>
</head>
<body>
    <h1>Security Check</h1>
    <p>Please solve the CAPTCHA to continue.</p>
    <div class="g-recaptcha"></div>
    <iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>
</body>
</html>"""
        return Response(html_captcha, status=403, mimetype="text/html")

    bot_detected = is_ai_crawler(user_agent)

    # 4. Existing 403 Bot Block scenario
    if BLOCK_AI_BOTS and bot_detected:
        html_403 = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>403 Forbidden - Access Denied</title>
    <style>
        body { background: #0b0b0b; color: #fff; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
        .box { background: #1a1a1a; padding: 40px; border-radius: 8px; border: 1px solid #e50914; max-width: 500px; }
        h1 { color: #e50914; margin-bottom: 10px; font-size: 28px; }
        p { color: #aaa; font-size: 15px; line-height: 1.6; }
        code { background: #2a2a2a; color: #ff858a; padding: 2px 6px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>403 Forbidden</h1>
        <p>Bot traffic detected. Automated access is prohibited on this domain.</p>
        <p>User-Agent: <code>""" + user_agent + """</code></p>
        <p style="font-size: 12px; color: #666; margin-top: 20px;">CineStream Security Gateway • Blocked by Server Rule</p>
    </div>
</body>
</html>"""
        return Response(html_403, status=403, mimetype="text/html")

    # Normal access (browser or allowed AI bot)
    return render_template("index.html", is_blocked=BLOCK_AI_BOTS, port=PORT)


ROBOTS_TXT_PATH = os.path.join(os.path.dirname(__file__), "robots.txt")


@app.route("/robots.txt")
def robots_txt():
    """Serve robots.txt directly from disk as the single source of truth."""
    if os.path.exists(ROBOTS_TXT_PATH):
        with open(ROBOTS_TXT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = "User-agent: *\nAllow: /\n"
    return Response(content, mimetype="text/plain")


@app.route("/api/status")
def status():
    """JSON status endpoint showing active demo configuration."""
    ua = request.headers.get("User-Agent", "")
    return jsonify({
        "block_ai_bots": BLOCK_AI_BOTS,
        "block_in_robots_txt": BLOCK_IN_ROBOTS_TXT,
        "port": PORT,
        "request_user_agent": ua,
        "is_ai_crawler": is_ai_crawler(ua),
    })


@app.route("/toggle")
def toggle():
    """
    Live presentation helper route:
    Quickly toggle blocking on/off via browser without restarting the server:
      - /toggle?block=true
      - /toggle?block=false
      - /toggle (toggles current state)
    """
    global BLOCK_AI_BOTS, BLOCK_IN_ROBOTS_TXT
    block_param = request.args.get("block")
    robots_param = request.args.get("robots")

    if block_param is not None:
        BLOCK_AI_BOTS = block_param.lower() in ("true", "1", "yes")
    else:
        BLOCK_AI_BOTS = not BLOCK_AI_BOTS

    if robots_param is not None:
        BLOCK_IN_ROBOTS_TXT = robots_param.lower() in ("true", "1", "yes")

    return jsonify({
        "message": f"BLOCK_AI_BOTS is now {BLOCK_AI_BOTS}",
        "BLOCK_AI_BOTS": BLOCK_AI_BOTS,
        "BLOCK_IN_ROBOTS_TXT": BLOCK_IN_ROBOTS_TXT,
        "instructions": "Visit http://localhost:" + str(PORT) + " to see the updated status."
    })


_server_thread = None


def _is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_server(port: int = PORT) -> str:
    """Starts demo server in background daemon thread if not already running."""
    global _server_thread
    if _is_port_in_use(port):
        return f"http://127.0.0.1:{port}"
    if _server_thread is None or not _server_thread.is_alive():
        _server_thread = threading.Thread(
            target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
            daemon=True,
        )
        _server_thread.start()
        time.sleep(0.8)
    return f"http://127.0.0.1:{port}"


if __name__ == "__main__":
    print(f"\n" + "=" * 65)
    print(f" CineStream Demo Platform Running on http://localhost:{PORT}")
    print(f" BLOCK_AI_BOTS = {BLOCK_AI_BOTS}")
    print(f" BLOCK_IN_ROBOTS_TXT = {BLOCK_IN_ROBOTS_TXT}")
    print(f"=" * 65 + "\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
