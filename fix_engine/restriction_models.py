"""Data models and catalog for Phase 3 AI Restriction / Reverse Fix Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RestrictionCategory(str, Enum):
    """Conceptual categories of Phase 3 AI crawl restrictions."""
    AI_ROBOTS_RESTRICTION = "ai_robots_restriction"
    AI_RATE_LIMIT = "ai_rate_limit"
    AI_WAF_CHALLENGE = "ai_waf_challenge"
    AI_CAPTCHA = "ai_captcha"
    AI_AUTHENTICATION = "ai_authentication"


class RestrictionCapability(str, Enum):
    """Execution capabilities for restrictions."""
    SUPPORTED_CONTROLLED_FIX = "supported_controlled_fix"
    RECOMMENDATION_ONLY = "recommendation_only"


class RestrictionStatus(str, Enum):
    """Possible outcomes when applying or removing restrictions."""
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    REMOVED = "removed"
    ALREADY_REMOVED = "already_removed"
    UNSUPPORTED = "unsupported"
    RECOMMENDATION_ONLY = "recommendation_only"
    TARGET_NOT_ALLOWED = "target_not_allowed"
    APPLICATION_FAILED = "application_failed"


@dataclass
class RestrictionDefinition:
    """Metadata describing a restriction control and its operational capability."""
    category: RestrictionCategory
    capability: RestrictionCapability
    title: str
    description: str
    recommendation_steps: List[str] = field(default_factory=list)


RESTRICTION_CATALOG: Dict[str, RestrictionDefinition] = {
    RestrictionCategory.AI_ROBOTS_RESTRICTION.value: RestrictionDefinition(
        category=RestrictionCategory.AI_ROBOTS_RESTRICTION,
        capability=RestrictionCapability.SUPPORTED_CONTROLLED_FIX,
        title="Robots.txt AI Crawl Restriction",
        description="Enforces explicit Disallow directives in robots.txt for AI crawler user-agents.",
    ),
    RestrictionCategory.AI_RATE_LIMIT.value: RestrictionDefinition(
        category=RestrictionCategory.AI_RATE_LIMIT,
        capability=RestrictionCapability.SUPPORTED_CONTROLLED_FIX,
        title="AI Crawler Rate Limiting",
        description="Applies strict HTTP 429 rate limiting against aggressive AI crawler personas.",
    ),
    RestrictionCategory.AI_WAF_CHALLENGE.value: RestrictionDefinition(
        category=RestrictionCategory.AI_WAF_CHALLENGE,
        capability=RestrictionCapability.SUPPORTED_CONTROLLED_FIX,
        title="WAF / Anti-Bot Challenge Simulation",
        description="Interprets AI user-agents and intercepts requests with an anti-bot challenge page.",
    ),
    RestrictionCategory.AI_CAPTCHA.value: RestrictionDefinition(
        category=RestrictionCategory.AI_CAPTCHA,
        capability=RestrictionCapability.SUPPORTED_CONTROLLED_FIX,
        title="Interactive CAPTCHA Challenge",
        description="Enforces interactive human verification challenges on automated AI crawlers.",
    ),
    RestrictionCategory.AI_AUTHENTICATION.value: RestrictionDefinition(
        category=RestrictionCategory.AI_AUTHENTICATION,
        capability=RestrictionCapability.RECOMMENDATION_ONLY,
        title="AI Agent Authentication & Gating",
        description="Requires verified OAuth 2.0 bearer tokens or cryptographic mTLS for automated indexers.",
        recommendation_steps=[
            "Deploy an API gateway (e.g. Kong, Envoy, or Cloudflare API Shield) fronting public content endpoints.",
            "Configure mandatory OAuth 2.0 Bearer token validation or Signed Exchange verification for AI bots.",
            "Issue scoped credentials specifically to authorized commercial search partners.",
            "Return HTTP 401 Unauthorized for unauthenticated automated crawler requests.",
        ],
    ),
    "cloudflare_waf_config": RestrictionDefinition(
        category=RestrictionCategory.AI_WAF_CHALLENGE,
        capability=RestrictionCapability.RECOMMENDATION_ONLY,
        title="Cloudflare WAF Custom Rule for AI Bots",
        description="Production WAF configuration using Cloudflare Firewall Rules / Super Bot Fight Mode.",
        recommendation_steps=[
            "Log in to the Cloudflare Dashboard and navigate to Security > WAF > Custom Rules.",
            "Create a new rule: 'Block or Managed Challenge AI Crawlers'.",
            "Define expression: (cf.client.bot) or (http.user_agent contains 'GPTBot') or (http.user_agent contains 'ClaudeBot').",
            "Set Action to 'Managed Challenge' or 'Block'.",
            "Deploy rule with priority above general traffic pass-through rules.",
        ],
    ),
    "akamai_bot_manager": RestrictionDefinition(
        category=RestrictionCategory.AI_WAF_CHALLENGE,
        capability=RestrictionCapability.RECOMMENDATION_ONLY,
        title="Akamai Bot Manager AI Protection",
        description="Production bot mitigation policy using Akamai Bot Manager Premier / Client Reputation.",
        recommendation_steps=[
            "Navigate to Akamai Control Center > Security Configurations > Bot Management.",
            "Under 'Bot Categories', locate 'Aggregators and Scrapers' / 'AI Bots'.",
            "Change category action from 'Monitor' to 'Tarpit' or 'Deny'.",
            "Configure transactional challenge verification thresholds for unverified automation agents.",
            "Save and activate configuration on the Akamai staging and production networks.",
        ],
    ),
    "recaptcha_enterprise": RestrictionDefinition(
        category=RestrictionCategory.AI_CAPTCHA,
        capability=RestrictionCapability.RECOMMENDATION_ONLY,
        title="Google reCAPTCHA Enterprise / Turnstile Integration",
        description="Production bot challenge provider integration for interactive human verification.",
        recommendation_steps=[
            "Register site key and secret key in Google Cloud Console reCAPTCHA Enterprise or Cloudflare Turnstile.",
            "Embed client-side challenge widget scripts in high-value page templates.",
            "Implement server-side token assessment on incoming requests without verified user sessions.",
            "Enforce challenge verification before serving structured or dynamic content to unauthenticated clients.",
        ],
    ),
}

# Aliases for flexible identifier matching
RESTRICTION_ALIASES: Dict[str, str] = {
    "robots": RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
    "robots_txt": RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
    "ai_robots": RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
    "ai_robots_restriction": RestrictionCategory.AI_ROBOTS_RESTRICTION.value,
    "rate_limit": RestrictionCategory.AI_RATE_LIMIT.value,
    "ai_rate_limit": RestrictionCategory.AI_RATE_LIMIT.value,
    "waf": RestrictionCategory.AI_WAF_CHALLENGE.value,
    "waf_challenge": RestrictionCategory.AI_WAF_CHALLENGE.value,
    "ai_waf_challenge": RestrictionCategory.AI_WAF_CHALLENGE.value,
    "cloudflare_waf": "cloudflare_waf_config",
    "cloudflare_waf_config": "cloudflare_waf_config",
    "akamai": "akamai_bot_manager",
    "akamai_bot_manager": "akamai_bot_manager",
    "captcha": RestrictionCategory.AI_CAPTCHA.value,
    "ai_captcha": RestrictionCategory.AI_CAPTCHA.value,
    "recaptcha": "recaptcha_enterprise",
    "recaptcha_enterprise": "recaptcha_enterprise",
    "auth": RestrictionCategory.AI_AUTHENTICATION.value,
    "authentication": RestrictionCategory.AI_AUTHENTICATION.value,
    "ai_authentication": RestrictionCategory.AI_AUTHENTICATION.value,
}


@dataclass
class RestrictionResult:
    """Structured result returned by the Phase 3 Restriction Engine."""
    control_id: str
    status: str
    target: str
    personas: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    implementation_steps: List[str] = field(default_factory=list)
    capability: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to clean JSON-serializable dictionary conforming to Part 7 specification."""
        data: Dict[str, Any] = {
            "control_id": self.control_id,
            "status": self.status,
            "target": self.target,
            "personas": list(self.personas),
            "files_changed": list(self.files_changed),
            "message": self.message,
        }
        if self.capability:
            data["capability"] = self.capability
        if self.implementation_steps:
            data["implementation_steps"] = list(self.implementation_steps)
        if self.details:
            data["details"] = self.details
        return data
