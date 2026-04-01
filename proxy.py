"""
Proxy logic for handling OpenAI API requests with privacy processing.
"""

import json
import time
from typing import Dict, Any, Optional, Union, List

import aiohttp

from config import ProxyConfig
from privacy_processor import PrivacyProcessor
from models import ProxyRequest, ProxyResponse, PrivacyResult
from logger import ProxyLogger


class OpenAIProxy:
    """OpenAI API proxy with privacy processing."""

    def __init__(
        self, config: ProxyConfig, processor: PrivacyProcessor, logger: ProxyLogger
    ):
        self.config = config
        self.processor = processor
        self.logger = logger
        self.session: Optional[aiohttp.ClientSession] = None

    async def ensure_session(self) -> aiohttp.ClientSession:
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self) -> None:
        """Close the proxy session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def proxy_request(self, request: ProxyRequest) -> ProxyResponse:
        """
        Proxy an OpenAI API request with privacy processing.

        Args:
            request: Proxy request object

        Returns:
            Proxy response object
        """
        start_time = time.time()
        privacy_result = None

        try:
            # Prepare request for OpenAI
            openai_url = f"{self.config.openai_base_url.rstrip('/')}{request.path}"
            headers = self._prepare_headers(request.headers)

            # Process request body for privacy
            processed_body = await self._process_request_body(request.body, request)

            # Make request to OpenAI
            session = await self.ensure_session()

            async with session.request(
                method=request.method,
                url=openai_url,
                headers=headers,
                json=processed_body if isinstance(processed_body, dict) else None,
                data=processed_body if not isinstance(processed_body, dict) else None,
                params=request.query_params,
                ssl=self.config.verify_ssl,
            ) as openai_response:
                # Read response
                response_body = await self._read_response_body(openai_response)
                response_headers = dict(openai_response.headers)

                # Process response body for privacy (if needed)
                processed_response = await self._process_response_body(
                    response_body, response_headers, openai_response.status
                )

                processing_time = (time.time() - start_time) * 1000

                return ProxyResponse(
                    status_code=openai_response.status,
                    headers=response_headers,
                    body=processed_response,
                    processing_time_ms=processing_time,
                    privacy_result=privacy_result,
                )

        except aiohttp.ClientError as e:
            self.logger.error(f"Proxy request failed: {str(e)}")
            processing_time = (time.time() - start_time) * 1000

            return ProxyResponse(
                status_code=502,
                headers={"Content-Type": "application/json"},
                body={"error": f"Proxy error: {str(e)}"},
                processing_time_ms=processing_time,
            )
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            processing_time = (time.time() - start_time) * 1000

            return ProxyResponse(
                status_code=500,
                headers={"Content-Type": "application/json"},
                body={"error": f"Internal error: {str(e)}"},
                processing_time_ms=processing_time,
            )

    def _prepare_headers(self, original_headers: Dict[str, str]) -> Dict[str, str]:
        """Prepare headers for OpenAI API request."""
        headers = original_headers.copy()

        # Set API key
        if self.config.openai_api_key:
            headers["Authorization"] = f"Bearer {self.config.openai_api_key}"

        # Ensure content type is set
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        # Remove proxy-specific headers
        headers.pop("Host", None)
        headers.pop("Content-Length", None)

        return headers

    async def _process_request_body(
        self, body: Optional[Union[Dict, str]], request: ProxyRequest
    ) -> Optional[Union[Dict, str]]:
        """Process request body for privacy."""
        if body is None:
            return None

        if not request.is_openai_request:
            return body

        # Process OpenAI chat requests
        if request.is_openai_chat and isinstance(body, dict):
            if "messages" in body:
                body["messages"] = self.processor.process_openai_messages(
                    body["messages"]
                )
                return body

        # Process OpenAI embedding requests
        if request.is_openai_embedding and isinstance(body, dict):
            if "input" in body:
                input_data = body["input"]

                # Handle different input formats
                if isinstance(input_data, str):
                    result = self.processor.process_text(input_data)
                    body["input"] = result.processed_text
                elif isinstance(input_data, list):
                    # List of strings
                    if all(isinstance(item, str) for item in input_data):
                        processed_inputs = []
                        for text in input_data:
                            result = self.processor.process_text(text)
                            processed_inputs.append(result.processed_text)
                        body["input"] = processed_inputs
                    # List of message objects (for chat completions used as embeddings)
                    elif all(isinstance(item, dict) for item in input_data):
                        body["input"] = self.processor.process_openai_messages(
                            input_data
                        )

                return body

        return body

    async def _read_response_body(
        self, response: aiohttp.ClientResponse
    ) -> Optional[Union[Dict, str]]:
        """Read response body based on content type."""
        content_type = response.headers.get("Content-Type", "")

        if "application/json" in content_type:
            try:
                return await response.json()
            except:
                return await response.text()
        else:
            return await response.text()

    async def _process_response_body(
        self,
        body: Optional[Union[Dict, str]],
        headers: Dict[str, str],
        status_code: int,
    ) -> Optional[Union[Dict, str]]:
        """Process response body for privacy (optional)."""
        # For now, just return the body as-is
        # Could add response processing here if needed
        return body

    async def health_check(self) -> Dict[str, Any]:
        """Check OpenAI API connectivity."""
        try:
            session = await self.ensure_session()

            async with session.get(
                f"{self.config.openai_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.config.openai_api_key}"}
                if self.config.openai_api_key
                else {},
                ssl=self.config.verify_ssl,
            ) as response:
                return {
                    "openai_status": "connected" if response.status == 200 else "error",
                    "status_code": response.status,
                }
        except Exception as e:
            return {"openai_status": "disconnected", "error": str(e)}
