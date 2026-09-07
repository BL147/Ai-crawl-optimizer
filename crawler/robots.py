"""Robots.txt fetching, parsing, and rule analysis."""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urljoin
import httpx

from crawler.models import RobotsDirectives
from crawler.personas import CrawlerPersona, PERSONAS


AI_TOKENS = [
    "gptbot",
    "claudebot",
    "anthropic-ai",
    "perplexitybot",
    "google-extended",
    "bytespider",
    "cohere-ai",
    "ccbot",
]


class RobotsParser:
    """Robust parser for robots.txt with wildcard support and AI-directive inspection."""

    def __init__(self, content: str):
        self.raw_content = content
        self.sitemaps: List[str] = []
        # agent_lower -> list of ("allow"|"disallow", pattern)
        self.rules: Dict[str, List[Tuple[str, str]]] = {}
        self.crawl_delays: Dict[str, float] = {}
        self._parse()

    def _parse(self) -> None:
        current_agents: List[str] = []
        in_rules = False

        for line in self.raw_content.splitlines():
            clean = line.split("#", 1)[0].strip()
            if not clean or ":" not in clean:
                continue

            field, value = clean.split(":", 1)
            field = field.strip().lower()
            value = value.strip()

            if field == "user-agent":
                agent = value.lower()
                if in_rules:
                    # Previous record ended, start a new record group
                    current_agents = []
                    in_rules = False

                current_agents.append(agent)
                if agent not in self.rules:
                    self.rules[agent] = []
            elif field in ("allow", "disallow"):
                if not current_agents:
                    continue
                in_rules = True
                rule_type = field
                pattern = value
                for agent in current_agents:
                    self.rules[agent].append((rule_type, pattern))
            elif field == "crawl-delay":
                try:
                    delay = float(value)
                    for agent in current_agents:
                        self.crawl_delays[agent] = delay
                except ValueError:
                    pass
            elif field == "sitemap":
                if value and value not in self.sitemaps:
                    self.sitemaps.append(value)
            else:
                pass

    @staticmethod
    def _path_matches(pattern: str, path: str) -> bool:
        """Check if path matches a robots.txt pattern (supporting * and $)."""
        if not pattern:
            return False
        # Escape special regex chars except * and $
        escaped = re.escape(pattern).replace(r"\*", ".*")
        if escaped.endswith(r"\$"):
            escaped = escaped[:-2] + "$"
        else:
            escaped = escaped + ".*"
        return bool(re.match("^" + escaped, path))

    def is_allowed(self, path: str, agent_token: str) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if path is allowed for the agent using RFC 9309 longest-match precedence.
        Returns (is_allowed, matching_rule).
        """
        token = agent_token.lower()
        active_rules = self.rules.get(token)

        # Fallback to wildcard '*' if specific agent rules are not present
        if active_rules is None:
            active_rules = self.rules.get("*", [])

        matches = []
        for rule_type, pattern in active_rules:
            if not pattern:
                # Disallow: (empty) means allow all
                if rule_type == "disallow":
                    matches.append((0, 1, True, "Disallow: (empty)"))
                continue

            if self._path_matches(pattern, path):
                # Specificity: longer pattern wins; if equal length, Allow (1) beats Disallow (0)
                priority = 1 if rule_type == "allow" else 0
                is_allow = (rule_type == "allow")
                rule_text = f"{rule_type.capitalize()}: {pattern}"
                matches.append((len(pattern), priority, is_allow, rule_text))

        if not matches:
            return True, None

        # Sort by length descending, then allow-priority descending
        matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best = matches[0]
        return best[2], best[3]

    def get_crawl_delay(self, agent_token: str) -> Optional[float]:
        token = agent_token.lower()
        if token in self.crawl_delays:
            return self.crawl_delays[token]
        return self.crawl_delays.get("*")

    def inspect_ai_directives(self) -> Dict[str, Any]:
        """Summarize directives for known AI crawlers found in this robots.txt."""
        summary: Dict[str, Any] = {}
        for token in AI_TOKENS:
            if token in self.rules:
                summary[token] = {
                    "defined": True,
                    "rules_count": len(self.rules[token]),
                    "rules": [f"{r[0].capitalize()}: {r[1]}" for r in self.rules[token][:10]],
                    "crawl_delay": self.crawl_delays.get(token),
                }
        return summary


async def inspect_robots(
    target_url: str,
    persona: CrawlerPersona,
    timeout: float = 6.0,
) -> RobotsDirectives:
    """Fetch and evaluate robots.txt for a given URL and persona."""
    parsed = urlparse(target_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(origin, "/robots.txt")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    headers = {
        "User-Agent": persona.user_agent,
        "Accept": "text/plain,text/html,*/*",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            resp = await client.get(robots_url, headers=headers)

        if resp.status_code == 200:
            content = resp.text
            parser = RobotsParser(content)
            is_allowed, matching_rule = parser.is_allowed(path, persona.robots_token)
            crawl_delay = parser.get_crawl_delay(persona.robots_token)
            ai_rules = parser.inspect_ai_directives()

            return RobotsDirectives(
                exists=True,
                url=robots_url,
                status_code=resp.status_code,
                is_allowed=is_allowed,
                matching_rule=matching_rule,
                crawl_delay=crawl_delay,
                sitemaps=parser.sitemaps,
                ai_specific_rules=ai_rules,
                raw_content=content[:2000] if len(content) > 2000 else content,
            )

        elif resp.status_code in (401, 403, 429):
            # Blocked or rate limited from reading robots.txt itself (RFC 9309: fail closed)
            return RobotsDirectives(
                exists=True,
                url=robots_url,
                status_code=resp.status_code,
                is_allowed=False,
                matching_rule=f"HTTP {resp.status_code} Access Denied to robots.txt",
            )
        elif resp.status_code >= 500:
            # Server error reading robots.txt (RFC 9309 Section 2.3.1.3: fail closed)
            return RobotsDirectives(
                exists=True,
                url=robots_url,
                status_code=resp.status_code,
                is_allowed=False,
                matching_rule=f"HTTP {resp.status_code} Server Error reading robots.txt (RFC 9309: fail closed)",
            )
        else:
            # 404/410 or other client error: missing robots.txt defaults to unrestricted access
            return RobotsDirectives(
                exists=False,
                url=robots_url,
                status_code=resp.status_code,
                is_allowed=True,
                matching_rule=f"HTTP {resp.status_code} (No robots.txt found - default allow)",
            )

    except Exception as err:
        return RobotsDirectives(
            exists=False,
            url=robots_url,
            status_code=None,
            is_allowed=True,
            matching_rule=f"Failed to fetch robots.txt: {str(err)}",
        )
