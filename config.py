"""
Configuration management for privacy proxy server.
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class PrivacyConfig:
    """Privacy processing configuration."""

    enabled: bool = True
    strategy: str = "placeholder"  # placeholder, mask, remove
    auto_redact: bool = True
    skip_validation: bool = False
    excluded_types: List[str] = field(default_factory=list)
    custom_rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ProxyConfig:
    """Proxy server configuration."""

    host: str = "127.0.0.1"
    port: int = 8080
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    verify_ssl: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    file: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    audit_log: bool = True
    audit_file: Optional[str] = "audit.log"


@dataclass
class ServerConfig:
    """Main server configuration."""

    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_file(cls, config_path: str) -> "ServerConfig":
        """Load configuration from JSON file."""
        if not os.path.exists(config_path):
            return cls()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return cls()

        # Parse nested configs
        privacy_data = data.get("privacy", {})
        privacy_config = PrivacyConfig(**privacy_data)

        proxy_data = data.get("proxy", {})
        proxy_config = ProxyConfig(**proxy_data)

        logging_data = data.get("logging", {})
        logging_config = LoggingConfig(**logging_data)

        return cls(privacy=privacy_config, proxy=proxy_config, logging=logging_config)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "privacy": asdict(self.privacy),
            "proxy": asdict(self.proxy),
            "logging": asdict(self.logging),
        }

    def save(self, config_path: str) -> None:
        """Save configuration to file."""
        os.makedirs(os.path.dirname(config_path) or ".", exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def get_default_config_path() -> str:
    """Get default configuration file path."""
    return os.path.join(os.path.dirname(__file__), "config.json")


def load_config(config_path: Optional[str] = None) -> ServerConfig:
    """Load configuration from file or return defaults."""
    if config_path is None:
        config_path = get_default_config_path()

    return ServerConfig.from_file(config_path)
