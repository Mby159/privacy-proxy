#!/usr/bin/env python3
"""
Privacy Proxy Server - Entry point for the privacy proxy server.
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config, ServerConfig
from server import PrivacyProxyServer


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Privacy Proxy Server - OpenAI compatible proxy with privacy processing"
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to configuration file (default: config.json)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind to (default: from config or 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Port to bind to (default: from config or 8080)",
    )

    parser.add_argument(
        "--openai-api-key",
        type=str,
        default=None,
        help="OpenAI API key (default: from config or OPENAI_API_KEY env var)",
    )

    parser.add_argument(
        "--openai-base-url",
        type=str,
        default=None,
        help="OpenAI base URL (default: from config or https://api.openai.com/v1)",
    )

    parser.add_argument(
        "--no-privacy", action="store_true", help="Disable privacy processing"
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate example configuration file and exit",
    )

    return parser.parse_args()


def generate_config():
    """Generate example configuration file."""
    config = ServerConfig()
    config_path = "config.example.json"
    config.save(config_path)
    print(f"Example configuration generated: {config_path}")
    return config_path


async def run_server(config: ServerConfig):
    """Run the privacy proxy server."""
    server = PrivacyProxyServer(config)

    print(f"Starting Privacy Proxy Server...")
    print(f"Host: {config.proxy.host}")
    print(f"Port: {config.proxy.port}")
    print(f"Privacy enabled: {config.privacy.enabled}")
    print(f"OpenAI base URL: {config.proxy.openai_base_url}")
    print(f"OpenAI API key: {'*' * 8 if config.proxy.openai_api_key else 'Not set'}")
    print(f"Logging level: {config.logging.level}")
    print(f"Audit logging: {config.logging.audit_log}")

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await server.stop()


def main():
    """Main entry point."""
    args = parse_args()

    # Generate config if requested
    if args.generate_config:
        generate_config()
        return

    # Load configuration
    config = load_config(args.config)

    # Apply command line overrides
    if args.host:
        config.proxy.host = args.host
    if args.port:
        config.proxy.port = args.port
    if args.openai_api_key:
        config.proxy.openai_api_key = args.openai_api_key
    elif os.getenv("OPENAI_API_KEY"):
        config.proxy.openai_api_key = os.getenv("OPENAI_API_KEY")
    if args.openai_base_url:
        config.proxy.openai_base_url = args.openai_base_url
    if args.no_privacy:
        config.privacy.enabled = False
    if args.debug:
        config.logging.level = "DEBUG"

    # Run server
    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
