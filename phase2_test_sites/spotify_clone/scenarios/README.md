# Phase 2 Test Environment (Streamify)

This is a deterministic local test environment for validating the AI Crawl Optimizer. It is a fictional music streaming website designed to be audited by our crawler.

## Directory Structure
- `app.py`: The Flask application and mock database.
- `test_app.py`: Pytest suite to verify the local server functionality.
- `templates/`: Jinja2 HTML templates for the mock UI.
- `static/`: CSS for the mock UI.
- `scenarios/`: Documentation for testing scenarios.

## Running the Server

You can run the server in different configurations to test how the AI Crawl Optimizer reacts to specific conditions.

### A. Normal Environment
Runs the server with standard behavior.
```bash
python phase2_test_sites/spotify_clone/app.py
```

### B. AI Crawler Restriction Enabled
Sets `BLOCK_AI_IN_ROBOTS=true` to dynamically block GPTBot and ClaudeBot in `/robots.txt`.
```bash
BLOCK_AI_IN_ROBOTS=true python phase2_test_sites/spotify_clone/app.py
```

### C. Latency Enabled
Sets `TEST_LATENCY_MS` to simulate backend delay on all requests.
```bash
TEST_LATENCY_MS=1500 python phase2_test_sites/spotify_clone/app.py
```

### D. Both Scenarios Enabled
Combines the AI restriction and the latency simulation.
```bash
BLOCK_AI_IN_ROBOTS=true TEST_LATENCY_MS=1500 python phase2_test_sites/spotify_clone/app.py
```

## Available Routes
- `/`: Home page displaying featured albums and popular artists.
- `/search`: Search page linking to other views.
- `/library`: User library displaying saved albums and playlists.
- `/playlists`: List of all available playlists.
- `/playlist/<id>`: Playlist detail view.
- `/artist/<id>`: Artist profile and discography.
- `/album/<id>`: Album details and tracklist.

## Resetting the Environment
To reset the environment to its original state, simply stop the server (`CTRL+C`) and restart it using the **Normal Environment** command. No database state is preserved between restarts.

## Running Tests
Run the automated test suite using pytest:
```bash
pytest phase2_test_sites/spotify_clone/test_app.py
```

## Auditing with the Crawler
To audit the test site with the existing Phase 1 crawler, start the server and run:
```bash
python run_crawler.py http://localhost:5051 --persona gptbot
```
