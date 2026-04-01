"""
Main privacy proxy server using aiohttp.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional

from aiohttp import web

from config import ServerConfig, load_config
from privacy_processor import PrivacyProcessor
from proxy import OpenAIProxy
from models import ProxyRequest, AuditLogEntry, HealthStatus
from logger import ProxyLogger


class PrivacyProxyServer:
    """Privacy proxy server with aiohttp."""

    def __init__(self, config: Optional[ServerConfig] = None):
        self.config = config or load_config()
        self.logger = ProxyLogger(
            level=self.config.logging.level,
            log_file=self.config.logging.file,
            audit_file=self.config.logging.audit_file,
            audit_enabled=self.config.logging.audit_log,
        )

        self.processor = PrivacyProcessor(self.config.privacy)
        self.proxy = OpenAIProxy(self.config.proxy, self.processor, self.logger)

        self.start_time = time.time()
        self.total_requests = 0
        self.total_sensitive_detected = 0

        # Create aiohttp app
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup aiohttp routes."""
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_post("/v1/chat/completions", self.handle_chat_completions)
        self.app.router.add_post("/v1/embeddings", self.handle_embeddings)
        self.app.router.add_get("/v1/models", self.handle_models)
        self.app.router.add_route("*", "/v1/{path:.*}", self.handle_proxy)
        self.app.router.add_post("/process", self.handle_process)
        self.app.router.add_post("/detect", self.handle_detect)

        # Add middleware for logging
        self.app.middlewares.append(self._logging_middleware)

    @web.middleware
    async def _logging_middleware(self, request: web.Request, handler) -> web.Response:
        """Middleware for request logging and audit."""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Store request ID
        request["request_id"] = request_id

        try:
            response = await handler(request)
            processing_time = (time.time() - start_time) * 1000

            # Create audit entry
            entry = AuditLogEntry(
                request_id=request_id,
                client_ip=request.remote,
                method=request.method,
                path=request.path,
                status_code=response.status,
                processing_time_ms=processing_time,
            )

            self.logger.audit(entry)
            return response

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self.logger.error(f"Request failed: {str(e)}")

            # Create error audit entry
            entry = AuditLogEntry(
                request_id=request_id,
                client_ip=request.remote,
                method=request.method,
                path=request.path,
                status_code=500,
                processing_time_ms=processing_time,
                error=str(e),
            )

            self.logger.audit(entry)
            raise

    async def handle_health(self, request: web.Request) -> web.Response:
        """Handle health check requests."""
        uptime = time.time() - self.start_time
        openai_health = await self.proxy.health_check()

        status = HealthStatus(
            status="healthy"
            if openai_health.get("openai_status") == "connected"
            else "degraded",
            uptime_seconds=uptime,
            version="0.1.0",
            privacy_enabled=self.config.privacy.enabled,
            total_requests=self.total_requests,
            total_sensitive_detected=self.total_sensitive_detected,
        )

        return web.json_response(
            {
                "status": status.status,
                "uptime": status.uptime_seconds,
                "version": status.version,
                "privacy_enabled": status.privacy_enabled,
                "openai_status": openai_health.get("openai_status"),
                "openai_status_code": openai_health.get("status_code"),
                "total_requests": status.total_requests,
                "total_sensitive_detected": status.total_sensitive_detected,
            }
        )

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
        """Handle OpenAI chat completions proxy."""
        return await self._handle_proxy_request(request, "/v1/chat/completions")

    async def handle_embeddings(self, request: web.Request) -> web.Response:
        """Handle OpenAI embeddings proxy."""
        return await self._handle_proxy_request(request, "/v1/embeddings")

    async def handle_models(self, request: web.Request) -> web.Response:
        """Handle OpenAI models list proxy."""
        return await self._handle_proxy_request(request, "/v1/models")

    async def handle_proxy(self, request: web.Request) -> web.Response:
        """Handle generic OpenAI API proxy."""
        path = f"/v1/{request.match_info.get('path', '')}"
        return await self._handle_proxy_request(request, path)

    async def _handle_proxy_request(
        self, request: web.Request, path: str
    ) -> web.Response:
        """Handle proxy request with privacy processing."""
        self.total_requests += 1

        try:
            # Read request body
            body = None
            if request.can_read_body:
                try:
                    body = await request.json()
                except:
                    body = await request.text()

            # Get query params
            query_params = dict(request.query)

            # Get headers
            headers = dict(request.headers)

            # Create proxy request
            proxy_request = ProxyRequest(
                method=request.method,
                path=path,
                headers=headers,
                body=body,
                query_params=query_params,
            )

            # Proxy request
            response = await self.proxy.proxy_request(proxy_request)

            # Update statistics
            if response.privacy_result and response.privacy_result.has_sensitive_info:
                self.total_sensitive_detected += len(
                    response.privacy_result.detected_items
                )

            # Create response
            web_response = web.json_response(
                response.body, status=response.status_code, headers=response.headers
            )

            # Add custom headers
            web_response.headers["X-Privacy-Processed"] = str(
                self.config.privacy.enabled
            )
            web_response.headers["X-Processing-Time-Ms"] = str(
                response.processing_time_ms
            )

            return web_response

        except Exception as e:
            self.logger.error(f"Proxy request failed: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_process(self, request: web.Request) -> web.Response:
        """Handle text processing requests."""
        try:
            data = await request.json()
            text = data.get("text", "")
            strategy = data.get("strategy")

            result = self.processor.process_text(text, strategy)
            summary = self.processor.get_risk_summary(result)

            return web.json_response(
                {
                    "original_text": result.original_text,
                    "processed_text": result.processed_text,
                    "mapping": result.mapping,
                    "risk_summary": summary,
                    "processing_time_ms": result.processing_time_ms,
                }
            )

        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_detect(self, request: web.Request) -> web.Response:
        """Handle sensitive information detection."""
        try:
            data = await request.json()
            text = data.get("text", "")

            result = self.processor.process_text(text, strategy=None)
            summary = self.processor.get_risk_summary(result)

            detected_items = []
            for item in result.detected_items:
                detected_items.append(
                    {
                        "type": item.info_type,
                        "value": item.original_value,
                        "risk_level": item.risk_level.value,
                    }
                )

            return web.json_response(
                {
                    "has_sensitive_info": result.has_sensitive_info,
                    "detected_items": detected_items,
                    "risk_summary": summary,
                }
            )

        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def start(self) -> None:
        """Start the proxy server."""
        self.logger.info(
            f"Starting privacy proxy server on {self.config.proxy.host}:{self.config.proxy.port}"
        )

        # Create runner
        runner = web.AppRunner(self.app)
        await runner.setup()

        # Create site
        site = web.TCPSite(runner, self.config.proxy.host, self.config.proxy.port)
        await site.start()

        self.logger.info(
            f"Server started at http://{self.config.proxy.host}:{self.config.proxy.port}"
        )

        # Keep running
        try:
            await asyncio.Future()  # run forever
        except asyncio.CancelledError:
            pass
        finally:
            await self.proxy.close()
            await runner.cleanup()

    async def stop(self) -> None:
        """Stop the proxy server."""
        await self.proxy.close()


def create_app(config: Optional[ServerConfig] = None) -> web.Application:
    """Create aiohttp application."""
    server = PrivacyProxyServer(config)
    return server.app
