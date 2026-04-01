"""
Data models for privacy proxy server.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import time


class RiskLevel(str, Enum):
    """Risk levels for sensitive information."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SensitiveItem:
    """Detected sensitive information item."""

    info_type: str
    original_value: str
    placeholder: str
    risk_level: RiskLevel
    position: Optional[int] = None


@dataclass
class PrivacyResult:
    """Result of privacy processing."""

    original_text: str
    processed_text: str
    mapping: Dict[str, str] = field(default_factory=dict)
    detected_items: List[SensitiveItem] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    processing_time_ms: float = 0.0

    @property
    def has_sensitive_info(self) -> bool:
        return len(self.detected_items) > 0


@dataclass
class ProxyRequest:
    """Proxy request model."""

    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Union[Dict, str]] = None
    query_params: Dict[str, str] = field(default_factory=dict)

    @property
    def is_openai_chat(self) -> bool:
        """Check if this is an OpenAI chat completion request."""
        return "/chat/completions" in self.path

    @property
    def is_openai_embedding(self) -> bool:
        """Check if this is an OpenAI embedding request."""
        return "/embeddings" in self.path

    @property
    def is_openai_request(self) -> bool:
        """Check if this is any OpenAI API request."""
        return self.is_openai_chat or self.is_openai_embedding


@dataclass
class ProxyResponse:
    """Proxy response model."""

    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Union[Dict, str]] = None
    processing_time_ms: float = 0.0
    privacy_result: Optional[PrivacyResult] = None


@dataclass
class AuditLogEntry:
    """Audit log entry."""

    timestamp: float = field(default_factory=time.time)
    request_id: Optional[str] = None
    client_ip: Optional[str] = None
    method: str = ""
    path: str = ""
    status_code: int = 0
    processing_time_ms: float = 0.0
    has_sensitive_info: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    detected_count: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "client_ip": self.client_ip,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "processing_time_ms": self.processing_time_ms,
            "has_sensitive_info": self.has_sensitive_info,
            "risk_level": self.risk_level.value
            if isinstance(self.risk_level, RiskLevel)
            else self.risk_level,
            "detected_count": self.detected_count,
            "error": self.error,
        }


@dataclass
class HealthStatus:
    """Server health status."""

    status: str = "healthy"
    uptime_seconds: float = 0.0
    version: str = ""
    privacy_enabled: bool = True
    total_requests: int = 0
    total_sensitive_detected: int = 0
    last_error: Optional[str] = None
