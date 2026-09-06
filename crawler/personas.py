"""Crawler persona definitions and registry."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CrawlerPersona:
    id: str
    display_name: str
    user_agent: str
    robots_token: str
    is_ai_agent: bool = True
    extra_headers: Dict[str, str] = field(default_factory=dict)


PERSONAS: Dict[str, CrawlerPersona] = {
    "gptbot": CrawlerPersona(
        id="gptbot",
        display_name="OpenAI GPTBot",
        user_agent="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
        robots_token="GPTBot",
        is_ai_agent=True,
        extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    ),
    "oai_searchbot": CrawlerPersona(
        id="oai_searchbot",
        display_name="OpenAI SearchBot",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
        robots_token="OAI-SearchBot",
        is_ai_agent=True,
        extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    ),
    "claudebot": CrawlerPersona(
        id="claudebot",
        display_name="Anthropic ClaudeBot",
        user_agent="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +https://anthropic.com/claudebot)",
        robots_token="ClaudeBot",
        is_ai_agent=True,
        extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    ),
    "anthropic_ai": CrawlerPersona(
        id="anthropic_ai",
        display_name="Anthropic General AI",
        user_agent="anthropic-ai",
        robots_token="anthropic-ai",
        is_ai_agent=True,
        extra_headers={"Accept": "*/*"},
    ),
    "perplexitybot": CrawlerPersona(
        id="perplexitybot",
        display_name="PerplexityBot",
        user_agent="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
        robots_token="PerplexityBot",
        is_ai_agent=True,
        extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    ),
    "google_extended": CrawlerPersona(
        id="google_extended",
        display_name="Google-Extended (Gemini/Vertex)",
        user_agent="Mozilla/5.0 (compatible; Google-Extended; +https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers)",
        robots_token="Google-Extended",
        is_ai_agent=True,
        extra_headers={"Accept": "*/*"},
    ),
    "bytespider": CrawlerPersona(
        id="bytespider",
        display_name="ByteDance Bytespider",
        user_agent="Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)",
        robots_token="Bytespider",
        is_ai_agent=True,
        extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    ),
    "cohere": CrawlerPersona(
        id="cohere",
        display_name="Cohere AI",
        user_agent="cohere-ai",
        robots_token="cohere-ai",
        is_ai_agent=True,
        extra_headers={"Accept": "*/*"},
    ),
    "ccbot": CrawlerPersona(
        id="ccbot",
        display_name="Common Crawl (CCBot)",
        user_agent="CCBot/2.0 (https://commoncrawl.org/faq/)",
        robots_token="CCBot",
        is_ai_agent=True,
        extra_headers={"Accept": "*/*"},
    ),
    "standard_browser": CrawlerPersona(
        id="standard_browser",
        display_name="Standard Chrome Desktop (Baseline)",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        robots_token="*",
        is_ai_agent=False,
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    ),
}


def get_persona(persona_name: str) -> CrawlerPersona:
    """Retrieve a persona by key (case-insensitive). Defaults to gptbot if not found."""
    # First check direct key
    normalized = persona_name.lower().replace("-", "_").replace(" ", "_")
    if normalized in PERSONAS:
        return PERSONAS[normalized]

    # Check without separators (e.g. claude_bot -> claudebot)
    stripped = normalized.replace("_", "")
    for key, persona in PERSONAS.items():
        if key.replace("_", "") == stripped:
            return persona

    # Check if persona_name matches display_name or robots_token
    for persona in PERSONAS.values():
        if (
            persona.robots_token.lower() == persona_name.lower()
            or persona.display_name.lower() == persona_name.lower()
        ):
            return persona

    # Fallback to custom persona
    return CrawlerPersona(
        id=persona_name,
        display_name=f"Custom ({persona_name})",
        user_agent=persona_name,
        robots_token="*",
        is_ai_agent=True,
    )


def list_personas() -> List[Dict[str, str]]:
    """Return summary metadata for all registered personas."""
    return [
        {
            "id": p.id,
            "display_name": p.display_name,
            "user_agent": p.user_agent,
            "robots_token": p.robots_token,
            "is_ai_agent": p.is_ai_agent,
        }
        for p in PERSONAS.values()
    ]
