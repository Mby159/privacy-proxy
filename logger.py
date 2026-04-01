"""
Logging system for privacy proxy server.
"""

import logging
import logging.handlers
import json
import time
import os
from typing import Optional, Dict, Any
from dataclasses import asdict

from models import AuditLogEntry


class AuditLogger:
    """Audit logger for tracking privacy proxy operations."""

    def __init__(
        self,
        audit_file: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.audit_file = audit_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup audit logger."""
        logger = logging.getLogger("privacy_proxy.audit")
        logger.setLevel(logging.INFO)

        # Remove existing handlers
        logger.handlers.clear()

        if self.audit_file:
            # Create directory if needed
            os.makedirs(os.path.dirname(self.audit_file) or ".", exist_ok=True)

            # Use rotating file handler
            handler = logging.handlers.RotatingFileHandler(
                self.audit_file,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8",
            )
        else:
            # Use console handler if no file specified
            handler = logging.StreamHandler()

        # JSON formatter for structured logging
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                if hasattr(record, "audit_data"):
                    return json.dumps(record.audit_data, ensure_ascii=False)
                return json.dumps(
                    {
                        "timestamp": record.created,
                        "level": record.levelname,
                        "message": record.getMessage(),
                        "logger": record.name,
                    },
                    ensure_ascii=False,
                )

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        return logger

    def log_request(self, entry: AuditLogEntry) -> None:
        """Log an audit entry."""
        self._logger.info("", extra={"audit_data": entry.to_dict()})

    def log_error(self, request_id: Optional[str], error: str, **kwargs) -> None:
        """Log an error entry."""
        entry = AuditLogEntry(request_id=request_id, error=error, **kwargs)
        self.log_request(entry)


class ProxyLogger:
    """General logger for privacy proxy server."""

    def __init__(
        self,
        level: str = "INFO",
        log_file: Optional[str] = None,
        audit_file: Optional[str] = None,
        audit_enabled: bool = True,
    ):
        self.level = level
        self.log_file = log_file
        self.audit_enabled = audit_enabled

        # Setup main logger
        self.logger = self._setup_main_logger()

        # Setup audit logger if enabled
        self.audit_logger = AuditLogger(audit_file) if audit_enabled else None

    def _setup_main_logger(self) -> logging.Logger:
        """Setup main application logger."""
        logger = logging.getLogger("privacy_proxy")
        logger.setLevel(getattr(logging, self.level.upper(), logging.INFO))

        # Remove existing handlers
        logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler if specified
        if self.log_file:
            os.makedirs(os.path.dirname(self.log_file) or ".", exist_ok=True)
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)

    def audit(self, entry: AuditLogEntry) -> None:
        """Log audit entry if audit logging is enabled."""
        if self.audit_logger:
            self.audit_logger.log_request(entry)

    def audit_error(self, request_id: Optional[str], error: str, **kwargs) -> None:
        """Log audit error."""
        if self.audit_logger:
            self.audit_logger.log_error(request_id, error, **kwargs)


def get_logger(name: str = "privacy_proxy") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
