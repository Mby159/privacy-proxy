"""
Privacy processor - integrates with privacy-guard for sensitive information handling.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# Add privacy-guard to path
privacy_guard_path = Path(__file__).parent.parent / "privacy-guard"
sys.path.insert(0, str(privacy_guard_path))

try:
    from privacy_guard import PrivacyGuard

    HAS_PRIVACY_GUARD = True
except ImportError:
    HAS_PRIVACY_GUARD = False

from models import PrivacyResult, SensitiveItem, RiskLevel
from config import PrivacyConfig


class PrivacyProcessor:
    """Privacy processor using privacy-guard library."""

    def __init__(self, config: Optional[PrivacyConfig] = None):
        self.config = config or PrivacyConfig()
        self.guard = PrivacyGuard() if HAS_PRIVACY_GUARD else None
        self._load_custom_rules()

    def _load_custom_rules(self) -> None:
        """Load custom rules from configuration."""
        if not self.guard:
            return

        for rule in self.config.custom_rules:
            name = rule.get("name")
            pattern = rule.get("pattern")
            risk_level = rule.get("risk_level", "medium")
            if name and pattern:
                self.guard.add_rule(name, pattern, risk_level)

    def process_text(self, text: str, strategy: Optional[str] = None) -> PrivacyResult:
        """
        Process text for sensitive information.

        Args:
            text: Input text to process
            strategy: Override strategy (placeholder, mask, remove)

        Returns:
            PrivacyResult with processed text and metadata
        """
        if not self.config.enabled or not self.guard:
            return PrivacyResult(
                original_text=text,
                processed_text=text,
                mapping={},
                detected_items=[],
                risk_level=RiskLevel.LOW,
            )

        start_time = time.time()

        # Detect sensitive information
        detection = self.guard.detect(text, skip_validation=self.config.skip_validation)

        # Convert to SensitiveItem objects
        detected_items = []
        for item in detection:
            detected_items.append(
                SensitiveItem(
                    info_type=item["info_type"],
                    original_value=item["original_value"],
                    placeholder=item["placeholder"],
                    risk_level=RiskLevel(item["risk_level"]),
                )
            )

        # Filter excluded types
        if self.config.excluded_types:
            detected_items = [
                item
                for item in detected_items
                if item.info_type not in self.config.excluded_types
            ]

        # Determine risk level
        risk_level = self._calculate_risk_level(detected_items)

        # Apply redaction strategy
        use_strategy = strategy or self.config.strategy
        if detected_items and self.config.auto_redact:
            redacted = self.guard.redact(text, strategy=use_strategy)
            processed_text = redacted["text"]
            mapping = redacted["mapping"]
        else:
            processed_text = text
            mapping = {}

        processing_time = (time.time() - start_time) * 1000

        return PrivacyResult(
            original_text=text,
            processed_text=processed_text,
            mapping=mapping,
            detected_items=detected_items,
            risk_level=risk_level,
            processing_time_ms=processing_time,
        )

    def process_openai_messages(
        self, messages: List[Dict[str, str]], strategy: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Process OpenAI messages for sensitive information.

        Args:
            messages: List of OpenAI message objects
            strategy: Override strategy

        Returns:
            Processed messages
        """
        if not self.config.enabled or not self.guard:
            return messages

        processed_messages = []
        for message in messages:
            if message.get("role") == "user" and "content" in message:
                content = message["content"]

                # Handle different content types
                if isinstance(content, str):
                    result = self.process_text(content, strategy)
                    processed_content = result.processed_text
                elif isinstance(content, list):
                    # Handle multimodal content
                    processed_content = []
                    for part in content:
                        if part.get("type") == "text":
                            text = part["text"]
                            result = self.process_text(text, strategy)
                            processed_content.append(
                                {"type": "text", "text": result.processed_text}
                            )
                        else:
                            processed_content.append(part)
                else:
                    processed_content = content

                processed_message = message.copy()
                processed_message["content"] = processed_content
                processed_messages.append(processed_message)
            else:
                processed_messages.append(message)

        return processed_messages

    def _calculate_risk_level(self, items: List[SensitiveItem]) -> RiskLevel:
        """Calculate overall risk level from detected items."""
        if not items:
            return RiskLevel.LOW

        # Get highest risk level
        risk_levels = [item.risk_level for item in items]

        if RiskLevel.CRITICAL in risk_levels:
            return RiskLevel.CRITICAL
        elif RiskLevel.HIGH in risk_levels:
            return RiskLevel.HIGH
        elif RiskLevel.MEDIUM in risk_levels:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def get_risk_summary(self, result: PrivacyResult) -> Dict[str, Any]:
        """Get risk summary for a privacy result."""
        type_counts = {}
        for item in result.detected_items:
            type_counts[item.info_type] = type_counts.get(item.info_type, 0) + 1

        return {
            "has_sensitive_info": result.has_sensitive_info,
            "risk_level": result.risk_level.value,
            "detected_count": len(result.detected_items),
            "type_counts": type_counts,
            "processing_time_ms": result.processing_time_ms,
        }
