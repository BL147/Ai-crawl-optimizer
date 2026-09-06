"""Safe extraction, normalization, and categorization of crawler audit results."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IssueType(str, Enum):
    ROBOTS_TXT_DISALLOW = "ROBOTS_TXT_DISALLOW"
    X_ROBOTS_TAG_RESTRICTION = "X_ROBOTS_TAG_RESTRICTION"
    META_ROBOTS_RESTRICTION = "META_ROBOTS_RESTRICTION"
    WAF_OR_CHALLENGE = "WAF_OR_CHALLENGE"
    INCONCLUSIVE_HTTP_403 = "INCONCLUSIVE_HTTP_403"
    HTTP_429_RATE_LIMITED = "HTTP_429_RATE_LIMITED"
    HTTP_503_SERVICE_UNAVAILABLE = "HTTP_503_SERVICE_UNAVAILABLE"
    NO_RESTRICTION = "NO_RESTRICTION"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class NormalizedAudit:
    """Safe, flat representation of crawler facts, inferences, and issue classification."""
    target_url: str = ""
    persona: str = ""
    user_agent: str = ""
    issue_type: IssueType = IssueType.NO_RESTRICTION
    is_inconclusive_403: bool = False

    # Robots.txt observations
    robots_exists: bool = False
    robots_url: str = ""
    robots_is_allowed: bool = True
    robots_matching_rule: Optional[str] = None
    robots_crawl_delay: Optional[float] = None
    robots_raw_content: Optional[str] = None

    # HTTP observations
    http_status_code: Optional[int] = None
    http_server: Optional[str] = None
    http_x_robots_tag: Optional[str] = None
    http_headers: Dict[str, str] = field(default_factory=dict)

    # Page observations
    page_title: Optional[str] = None
    meta_tags: Dict[str, str] = field(default_factory=dict)
    page_snippet: str = ""

    # Detection observations
    evidence_status_code: Optional[int] = None
    evidence_matched_headers: List[str] = field(default_factory=list)
    evidence_dom_signals: List[str] = field(default_factory=list)
    evidence_matched_keywords: List[str] = field(default_factory=list)

    # Detection inference
    verdict: str = "ACCESSIBLE"
    mechanism: str = "NONE"
    confidence: float = 0.0
    summary: str = ""
    is_blocked: bool = False

    # Compiled lists
    observed_facts: List[str] = field(default_factory=list)
    crawler_inferences: List[str] = field(default_factory=list)
    raw_result: Dict[str, Any] = field(default_factory=dict)


def normalize_crawler_result(result: Any) -> NormalizedAudit:
    """
    Safely extract and normalize crawler results from dict or model objects,
    guaranteeing no KeyError or AttributeError even if fields are missing.
    """
    if result is None:
        raw: Dict[str, Any] = {}
    elif hasattr(result, "to_dict") and callable(result.to_dict):
        try:
            raw = result.to_dict()
        except Exception:
            raw = {}
    elif hasattr(result, "model_dump") and callable(result.model_dump):
        try:
            raw = result.model_dump(mode="json")
        except Exception:
            raw = {}
    elif isinstance(result, dict):
        raw = dict(result)
    else:
        raw = {}

    # If a baseline comparison dictionary is passed, extract target_persona
    if "target_persona" in raw and isinstance(raw["target_persona"], dict):
        raw = dict(raw["target_persona"])

    target_url = str(raw.get("target_url") or "")
    persona = str(raw.get("persona") or "unknown")
    user_agent = str(raw.get("user_agent") or "")

    # Robots.txt block
    r_dict = raw.get("robots_txt") if isinstance(raw.get("robots_txt"), dict) else {}
    robots_exists = bool(r_dict.get("exists", False))
    robots_url = str(r_dict.get("url") or "")
    robots_is_allowed = bool(r_dict.get("is_allowed", True))
    robots_matching_rule = r_dict.get("matching_rule")
    if robots_matching_rule is not None:
        robots_matching_rule = str(robots_matching_rule)
    robots_crawl_delay = r_dict.get("crawl_delay")
    if robots_crawl_delay is not None:
        try:
            robots_crawl_delay = float(robots_crawl_delay)
        except (ValueError, TypeError):
            robots_crawl_delay = None
    robots_raw_content = r_dict.get("raw_content")
    if robots_raw_content is not None:
        robots_raw_content = str(robots_raw_content)

    # HTTP block
    h_dict = raw.get("http") if isinstance(raw.get("http"), dict) else {}
    http_status = h_dict.get("status_code")
    if http_status is not None:
        try:
            http_status = int(http_status)
        except (ValueError, TypeError):
            http_status = None
    http_server = h_dict.get("server")
    if http_server is not None:
        http_server = str(http_server)
    http_x_robots = h_dict.get("x_robots_tag")
    if http_x_robots is not None:
        http_x_robots = str(http_x_robots)
    raw_headers = h_dict.get("headers") if isinstance(h_dict.get("headers"), dict) else {}
    http_headers = {str(k).lower(): str(v) for k, v in raw_headers.items()}
    if not http_x_robots and "x-robots-tag" in http_headers:
        http_x_robots = http_headers["x-robots-tag"]
    if not http_server and "server" in http_headers:
        http_server = http_headers["server"]

    # Page block
    p_dict = raw.get("page") if isinstance(raw.get("page"), dict) else {}
    page_title = p_dict.get("title")
    if page_title is not None:
        page_title = str(page_title)
    raw_meta = p_dict.get("meta_tags") if isinstance(p_dict.get("meta_tags"), dict) else {}
    meta_tags = {str(k).lower(): str(v) for k, v in raw_meta.items()}
    page_snippet = str(p_dict.get("snippet") or "")

    # Detection block
    d_dict = raw.get("detection") if isinstance(raw.get("detection"), dict) else {}
    ev_dict = d_dict.get("evidence") if isinstance(d_dict.get("evidence"), dict) else {}
    inf_dict = d_dict.get("inference") if isinstance(d_dict.get("inference"), dict) else {}

    ev_status = ev_dict.get("status_code")
    if ev_status is not None:
        try:
            ev_status = int(ev_status)
        except (ValueError, TypeError):
            ev_status = None
    if ev_status is None:
        ev_status = http_status

    ev_headers = [str(x) for x in ev_dict.get("matched_headers", []) if x]
    ev_dom = [str(x) for x in ev_dict.get("dom_signals", []) if x]
    ev_keywords = [str(x) for x in ev_dict.get("matched_keywords", []) if x]

    verdict_val = inf_dict.get("verdict") or d_dict.get("verdict") or "ACCESSIBLE"
    verdict = str(getattr(verdict_val, "value", verdict_val)).upper()

    mech_val = inf_dict.get("mechanism") or d_dict.get("block_type") or "NONE"
    mechanism = str(getattr(mech_val, "value", mech_val)).upper()
    try:
        confidence = float(inf_dict.get("confidence", d_dict.get("confidence", 0.0)))
    except (ValueError, TypeError):
        confidence = 0.0
    summary = str(inf_dict.get("summary") or "")
    is_blocked = bool(d_dict.get("is_blocked", False))

    # Compile objective facts
    observed_facts: List[str] = []
    effective_status = http_status or ev_status
    if effective_status:
        observed_facts.append(f"HTTP Status Code: {effective_status}")

    if robots_exists:
        observed_facts.append(f"robots.txt exists at {robots_url}")
        observed_facts.append(f"robots.txt is_allowed evaluation: {robots_is_allowed}")
        if robots_matching_rule:
            observed_facts.append(f"robots.txt matching rule: '{robots_matching_rule}'")
        if robots_crawl_delay:
            observed_facts.append(f"robots.txt crawl delay: {robots_crawl_delay}s")

    if http_server:
        observed_facts.append(f"HTTP Server header: '{http_server}'")
    if http_x_robots:
        observed_facts.append(f"HTTP X-Robots-Tag: '{http_x_robots}'")

    for h in ev_headers:
        if f"Header evidence: {h}" not in observed_facts:
            observed_facts.append(f"Header evidence: {h}")

    for dom in ev_dom:
        observed_facts.append(f"DOM signal marker: '{dom}'")

    for kw in ev_keywords:
        observed_facts.append(f"Matched keyword/phrase: '{kw}'")

    if page_title:
        observed_facts.append(f"Page title: '{page_title}'")

    for m_name, m_val in meta_tags.items():
        if any(bot in m_name for bot in ["robots", "googlebot", "gptbot", "claudebot"]):
            observed_facts.append(f"HTML meta tag '{m_name}': '{m_val}'")

    # Compile inferences
    crawler_inferences: List[str] = []
    if verdict:
        crawler_inferences.append(f"Verdict: {verdict}")
    if mechanism and mechanism != "NONE":
        crawler_inferences.append(f"Identified Mechanism: {mechanism}")
    if confidence > 0:
        crawler_inferences.append(f"Confidence: {confidence:.2f}")
    if summary:
        crawler_inferences.append(f"Crawler Summary: {summary}")

    # Determine Issue Classification
    # Priority 1: Robots.txt disallow
    if not robots_is_allowed or (robots_matching_rule and "disallow" in robots_matching_rule.lower()):
        issue_type = IssueType.ROBOTS_TXT_DISALLOW
        is_inconclusive_403 = False

    # Priority 2: X-Robots-Tag restriction
    elif http_x_robots and any(r in http_x_robots.lower() for r in ["noindex", "none", "nofollow", "unavailable_after"]):
        issue_type = IssueType.X_ROBOTS_TAG_RESTRICTION
        is_inconclusive_403 = False

    # Priority 3: HTML Meta Robots restriction
    elif any(
        ("noindex" in str(v).lower() or "none" in str(v).lower())
        for k, v in meta_tags.items()
        if any(bot in k for bot in ["robots", "googlebot", "gptbot", "claudebot"])
    ):
        issue_type = IssueType.META_ROBOTS_RESTRICTION
        is_inconclusive_403 = False

    # Priority 4: Rate limit (429)
    elif effective_status == 429 or mechanism == "HTTP_429_RATE_LIMITED":
        issue_type = IssueType.HTTP_429_RATE_LIMITED
        is_inconclusive_403 = False

    # Priority 5: Service unavailable / anti-DDoS challenge (503)
    elif effective_status == 503 or mechanism == "HTTP_503_SERVICE_UNAVAILABLE":
        issue_type = IssueType.HTTP_503_SERVICE_UNAVAILABLE
        is_inconclusive_403 = False

    # Priority 6: Inconclusive HTTP 403 Forbidden
    # Triggered when status is 403 or mechanism is HTTP_FORBIDDEN without explicit anti-bot evidence,
    # or whenever the crawler verdict is explicitly INCONCLUSIVE.
    elif (
        verdict == "INCONCLUSIVE"
        or (
            (effective_status == 403 or mechanism in ("HTTP_FORBIDDEN", "HTTP_403_FORBIDDEN"))
            and mechanism not in (
                "CLOUDFLARE_CHALLENGE", "CLOUDFLARE_BLOCK", "DATADOME", "PERIMETERX",
                "AKAMAI", "AWS_WAF", "RECAPTCHA", "HCAPTCHA", "CUSTOM_BOT_BLOCK"
            )
        )
    ):
        issue_type = IssueType.INCONCLUSIVE_HTTP_403
        is_inconclusive_403 = True

    # Priority 7: WAF / Challenge mechanisms
    elif mechanism in (
        "CLOUDFLARE_CHALLENGE",
        "CLOUDFLARE_BLOCK",
        "DATADOME",
        "PERIMETERX",
        "AKAMAI",
        "AWS_WAF",
        "RECAPTCHA",
        "HCAPTCHA",
        "CUSTOM_BOT_BLOCK",
    ) or verdict in ("CHALLENGED", "BLOCKED"):
        issue_type = IssueType.WAF_OR_CHALLENGE
        is_inconclusive_403 = False

    # Priority 8: Clean accessible
    elif verdict == "ACCESSIBLE" and (effective_status is None or effective_status == 200) and robots_is_allowed:
        issue_type = IssueType.NO_RESTRICTION
        is_inconclusive_403 = False

    else:
        # Fallback to unknown or unclassified
        if raw.get("error"):
            issue_type = IssueType.UNKNOWN_ERROR
        elif effective_status and effective_status >= 400:
            issue_type = IssueType.INCONCLUSIVE_HTTP_403 if effective_status == 403 else IssueType.UNKNOWN_ERROR
        else:
            issue_type = IssueType.NO_RESTRICTION
        is_inconclusive_403 = (issue_type == IssueType.INCONCLUSIVE_HTTP_403)

    return NormalizedAudit(
        target_url=target_url,
        persona=persona,
        user_agent=user_agent,
        issue_type=issue_type,
        is_inconclusive_403=is_inconclusive_403,
        robots_exists=robots_exists,
        robots_url=robots_url,
        robots_is_allowed=robots_is_allowed,
        robots_matching_rule=robots_matching_rule,
        robots_crawl_delay=robots_crawl_delay,
        robots_raw_content=robots_raw_content,
        http_status_code=http_status,
        http_server=http_server,
        http_x_robots_tag=http_x_robots,
        http_headers=http_headers,
        page_title=page_title,
        meta_tags=meta_tags,
        page_snippet=page_snippet,
        evidence_status_code=ev_status,
        evidence_matched_headers=ev_headers,
        evidence_dom_signals=ev_dom,
        evidence_matched_keywords=ev_keywords,
        verdict=verdict,
        mechanism=mechanism,
        confidence=confidence,
        summary=summary,
        is_blocked=is_blocked,
        observed_facts=observed_facts,
        crawler_inferences=crawler_inferences,
        raw_result=raw,
    )
