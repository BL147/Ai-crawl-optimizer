import os
import time
from flask import Flask, render_template, request, Response

app = Flask(__name__)

# Scenario configuration via Environment Variables
TEST_LATENCY_MS = int(os.environ.get("TEST_LATENCY_MS", 0))
BLOCK_AI_IN_ROBOTS = os.environ.get("BLOCK_AI_IN_ROBOTS", "False").lower() in ("true", "1")

# Mock Database
MOCK_ARTISTS = {
    "1": {"id": "1", "name": "Neon Synthex", "genre": "Synthwave", "listeners": "1.2M", "bio": "Pioneering the retro-future sound since 2019."},
    "2": {"id": "2", "name": "The Velvet Horizons", "genre": "Indie Rock", "listeners": "850K", "bio": "Melancholic melodies meet upbeat rhythms."}
}

MOCK_ALBUMS = {
    "101": {"id": "101", "title": "Cybernetic Dreams", "artist_id": "1", "year": "2024", "tracks": ["Neon Rain", "Grid Runner", "Digital Sunset"]},
    "102": {"id": "102", "title": "Sunset Overdrive", "artist_id": "1", "year": "2022", "tracks": ["Highway Star", "Night Drive"]},
    "201": {"id": "201", "title": "Echoes of Tomorrow", "artist_id": "2", "year": "2023", "tracks": ["Silent Echo", "Morning Dew"]}
}

MOCK_PLAYLISTS = {
    "p1": {"id": "p1", "title": "Synthwave Essentials", "description": "The best of retro-future.", "tracks": ["Neon Rain", "Digital Sunset"]},
    "p2": {"id": "p2", "title": "Indie Morning", "description": "Start your day right.", "tracks": ["Morning Dew", "Silent Echo"]}
}

@app.before_request
def simulate_latency():
    """Scenario 2: Configurable latency to test performance optimizations."""
    if TEST_LATENCY_MS > 0:
        time.sleep(TEST_LATENCY_MS / 1000.0)

@app.route("/robots.txt")
def robots():
    """Scenario 1: Configurable AI Crawler Restriction."""
    content = "User-agent: *\nAllow: /\n"
    if BLOCK_AI_IN_ROBOTS:
        content += "\nUser-agent: GPTBot\nDisallow: /\n"
        content += "\nUser-agent: ClaudeBot\nDisallow: /\n"
    return Response(content, mimetype="text/plain")

@app.route("/")
def home():
    albums = [
        {"id": a_id, "title": a["title"], "artist": MOCK_ARTISTS[a["artist_id"]]["name"]}
        for a_id, a in MOCK_ALBUMS.items()
    ]
    return render_template("index.html", albums=albums, artists=MOCK_ARTISTS.values())

@app.route("/artist/<artist_id>")
def artist(artist_id):
    art = MOCK_ARTISTS.get(artist_id)
    if not art:
        return "Not found", 404
    albs = [a for a in MOCK_ALBUMS.values() if a["artist_id"] == artist_id]
    return render_template("artist.html", artist=art, albums=albs)

@app.route("/album/<album_id>")
def album(album_id):
    alb = MOCK_ALBUMS.get(album_id)
    if not alb:
        return "Not found", 404
    art = MOCK_ARTISTS.get(alb["artist_id"])
    return render_template("album.html", album=alb, artist=art)

@app.route("/search")
def search():
    query = request.args.get("q", "")
    return render_template("search.html", query=query, artists=MOCK_ARTISTS.values())

@app.route("/library")
def library():
    return render_template("library.html", playlists=MOCK_PLAYLISTS.values(), albums=MOCK_ALBUMS.values())

@app.route("/playlists")
def playlists():
    return render_template("playlists.html", playlists=MOCK_PLAYLISTS.values())

@app.route("/playlist/<playlist_id>")
def playlist(playlist_id):
    pl = MOCK_PLAYLISTS.get(playlist_id)
    if not pl:
        return "Not found", 404
    return render_template("playlist.html", playlist=pl)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))
    print("="*60)
    print(f" Spotify Clone Test Environment running on port {port}")
    print(f" TEST_LATENCY_MS: {TEST_LATENCY_MS}")
    print(f" BLOCK_AI_IN_ROBOTS: {BLOCK_AI_IN_ROBOTS}")
    print("="*60)
    app.run(host="0.0.0.0", port=port, debug=False)
