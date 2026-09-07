import os
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_home(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Streamify" in res.data
    assert b"Neon Synthex" in res.data

def test_artist(client):
    res = client.get("/artist/1")
    assert res.status_code == 200
    assert b"Neon Synthex" in res.data
    

def test_album(client):
    res = client.get("/album/101")
    assert res.status_code == 200
    assert b"Cybernetic Dreams" in res.data

def test_playlist(client):
    res = client.get("/playlist/p1")
    assert res.status_code == 200
    assert b"Synthwave Essentials" in res.data

def test_search(client):
    res = client.get("/search")
    assert res.status_code == 200
    assert b"Search" in res.data

def test_library(client):
    res = client.get("/library")
    assert res.status_code == 200
    assert b"Your Library" in res.data

def test_playlists(client):
    res = client.get("/playlists")
    assert res.status_code == 200
    assert b"Featured Playlists" in res.data

def test_robots_normal(client):
    res = client.get("/robots.txt")
    assert res.status_code == 200
    assert b"GPTBot" not in res.data

def test_robots_ai_restricted(monkeypatch, client):
    import app as myapp
    monkeypatch.setattr(myapp, "BLOCK_AI_IN_ROBOTS", True)
    res = client.get("/robots.txt")
    assert res.status_code == 200
    assert b"GPTBot" in res.data
    assert b"ClaudeBot" in res.data

def test_latency(monkeypatch, client):
    import app as myapp
    import time
    monkeypatch.setattr(myapp, "TEST_LATENCY_MS", 100)
    start = time.perf_counter()
    client.get("/")
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed >= 100
