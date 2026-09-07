"""Pydantic data models for crawler outputs and observations."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BlockType(str, Enum):
    NONE = "NONE"
    CLOUDFLARE_CHALLENGE = "CLOUDFLARE_CHALLENGE"
    CLOUDFLARE_BLOCK = "CLOUDFLARE_BLOCK"
    DATADOME = "DATADOME"
    PERIMETERX = "PERIMETERX"
    AKAMAI = "AKAMAI"
    AWS_WAF = "AWS_WAF"
    RECAPTCHA = "RECAPTCHA"
    HCAPTCHA = "HCAPTCHA"
    HTTP_FORBIDDEN = "HTTP_FORBIDDEN"
    HTTP_403_FORBIDDEN = "HTTP_FORBIDDEN"  # Backwards compatibility alias
    HTTP_429_RATE_LIMITED = "HTTP_429_RATE_LIMITED"
    HTTP_503_SERVICE_UNAVAILABLE = "HTTP_503_SERVICE_UNAVAILABLE"
    CUSTOM_BOT_BLOCK = "CUSTOM_BOT_BLOCK"


class RobotsDirectives(BaseModel):
    exists: bool = False
    url: str = ""
    status_code: Optional[int] = None
    is_allowed: bool = True
    matching_rule: Optional[str] = None
    crawl_delay: Optional[float] = None
    sitemaps: List[str] = Field(default_factory=list)
    ai_specific_rules: Dict[str, Any] = Field(default_factory=dict)
    raw_content: Optional[str] = None


class HttpObservation(BaseModel):
    status_code: Optional[int] = None
    final_url: str = ""
    redirect_count: int = 0
    redirects: List[str] = Field(default_factory=list)
    headers: Dict[str, str] = Field(default_factory=dict)
    content_type: Optional[str] = None
    response_time_ms: Optional[float] = None
    server: Optional[str] = None
    x_robots_tag: Optional[str] = None


class PageObservation(BaseModel):
    title: Optional[str] = None
    meta_tags: Dict[str, str] = Field(default_factory=dict)
    text_length: int = 0
    snippet: str = ""
    has_javascript_requirement: bool = False


class DetectionEvidence(BaseModel):
    """Direct, objective observations gathered from HTTP and DOM layers."""
    status_code: Optional[int] = None
    matched_headers: List[str] = Field(default_factory=list)
    dom_signals: List[str] = Field(default_factory=list)
    matched_keywords: List[str] = Field(default_factory=list)
    page_title: Optional[str] = None
    snippet_preview: Optional[str] = None
    robots_rule: Optional[str] = None


class DetectionInference(BaseModel):
    """Inferred conclusions derived from observations."""
    verdict: str = "ACCESSIBLE"  # ACCESSIBLE | CHALLENGED | BLOCKED | INCONCLUSIVE | RESTRICTED
    mechanism: BlockType = BlockType.NONE
    confidence: float = 0.0
    summary: str = "No access restrictions detected."


class DetectionResult(BaseModel):
    evidence: DetectionEvidence = Field(default_factory=DetectionEvidence)
    inference: DetectionInference = Field(default_factory=DetectionInference)

    # Preserved top-level fields for backwards compatibility with teammates
    is_blocked: bool = False
    block_type: BlockType = BlockType.NONE
    confidence: float = 0.0
    signals: List[str] = Field(default_factory=list)


class CrawlResult(BaseModel):
    target_url: str
    persona: str
    user_agent: str
    timestamp: str
    success: bool = True
    error: Optional[str] = None
    robots_txt: RobotsDirectives = Field(default_factory=RobotsDirectives)
    http: HttpObservation = Field(default_factory=HttpObservation)
    page: PageObservation = Field(default_factory=PageObservation)
    detection: DetectionResult = Field(default_factory=DetectionResult)

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean dictionary representation suitable for JSON serialization."""
        return self.model_dump(mode="json")
