"""
CineStream - Streaming Platform Demo Website
Designed for live demonstration and auditing with AI Crawl Optimizer.

==============================================================================
HACKATHON PRESENTATION CONTROLS (Change these settings to toggle demo behavior)
==============================================================================
"""

import os
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


def is_ai_crawler(user_agent: str) -> bool:
    """Check if the incoming request User-Agent matches known AI crawler signatures."""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(bot in ua_lower for bot in AI_BOT_PATTERNS)


@app.route("/")
def home():
    """Main landing page. Handles both regular browsers and simulated bot blocks."""
    user_agent = request.headers.get("User-Agent", "")
    bot_detected = is_ai_crawler(user_agent)

    # If blocking is active AND the request is from an AI crawler persona
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


@app.route("/robots.txt")
def robots_txt():
    """Serve robots.txt policy with configurable AI crawler directives."""
    if BLOCK_IN_ROBOTS_TXT:
        content = """# CineStream Robots Policy - AI Crawl Optimizer Demo
User-agent: *
Allow: /

# Directives blocking generative search bots
User-agent: GPTBot
Disallow: /
Crawl-delay: 5

User-agent: ClaudeBot
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: Google-Extended
Disallow: /

Sitemap: http://localhost:""" + str(PORT) + """/sitemap.xml
"""
    else:
        content = """# CineStream Robots Policy - Fully Accessible
User-agent: *
Allow: /

Sitemap: http://localhost:""" + str(PORT) + """/sitemap.xml
"""
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


if __name__ == "__main__":
    print(f"\n" + "=" * 65)
    print(f" CineStream Demo Platform Running on http://localhost:{PORT}")
    print(f" BLOCK_AI_BOTS = {BLOCK_AI_BOTS}")
    print(f" BLOCK_IN_ROBOTS_TXT = {BLOCK_IN_ROBOTS_TXT}")
    print(f"=" * 65 + "\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
