"""Reconnaissance engine: semi-automated traffic recording and filtering.

Launches a browser session for the user to complete registration manually once,
intercepting and filtering network traffic into a clean JSON log.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Extensions to ignore
IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".css", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".webm", ".mp3", ".wav",
    ".map",
}

# Domains to ignore (analytics, trackers, CDNs noise)
IGNORED_DOMAINS = {
    "google-analytics.com",
    "googletagmanager.com",
    "mc.yandex.ru",
    "metrika.yandex",
    "facebook.net",
    "connect.facebook.net",
    "doubleclick.net",
    "sentry.io",
    "hotjar.com",
    "clarity.ms",
    "datadoghq.com",
}

# Noisy browser headers to omit from clean recordings
IGNORED_HEADER_PREFIXES = (
    "sec-ch-ua",
    "sec-fetch-",
    ":",
)


@dataclass
class RecordedRequest:
    """Represents a sanitized HTTP request/response captured during reconnaissance."""
    id: int
    url: str
    method: str
    headers: dict[str, str]
    post_data: Any | None
    status: int
    response_headers: dict[str, str]
    response_body: str | None
    timestamp: float


def is_relevant_url(url: str) -> bool:
    """Determine if a URL is relevant for API reverse engineering."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    hostname = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    # Check ignored domains
    for domain in IGNORED_DOMAINS:
        if hostname == domain or hostname.endswith("." + domain):
            return False

    # Check ignored extensions
    for ext in IGNORED_EXTENSIONS:
        if path.endswith(ext):
            return False

    return True


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Filter out noisy browser-generated headers while keeping essential auth/content headers."""
    clean: dict[str, str] = {}
    for key, value in headers.items():
        k_lower = key.lower()
        if any(k_lower.startswith(p) for p in IGNORED_HEADER_PREFIXES):
            continue
        if k_lower in ("accept-encoding", "host", "connection"):
            continue
        clean[key] = value
    return clean


class ReconEngine:
    """Captures and filters network traffic during an interactive browser session."""

    def __init__(self, output_dir: Path | str | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "recordings"
        self.recorded_requests: list[RecordedRequest] = []
        self._counter = 0

    def record_request_response(
        self,
        url: str,
        method: str,
        request_headers: dict[str, str],
        post_data: Any | None,
        status: int,
        response_headers: dict[str, str],
        response_body: str | None = None,
    ) -> RecordedRequest | None:
        """Process and record a single request-response pair if it passes filters."""
        if not is_relevant_url(url):
            return None

        # Filter out static resource types if method is GET and no interesting content
        content_type = (response_headers.get("content-type") or "").lower()
        if method == "GET" and ("image/" in content_type or "font/" in content_type or "text/css" in content_type):
            return None

        self._counter += 1
        clean_headers = sanitize_headers(request_headers)

        # Parse JSON body if possible
        parsed_body = post_data
        if isinstance(post_data, str) and post_data.strip().startswith(("{", "[")):
            try:
                parsed_body = json.loads(post_data)
            except Exception:
                parsed_body = post_data

        record = RecordedRequest(
            id=self._counter,
            url=url,
            method=method.upper(),
            headers=clean_headers,
            post_data=parsed_body,
            status=status,
            response_headers=response_headers,
            response_body=response_body[:5000] if response_body else None,
            timestamp=time.time(),
        )
        self.recorded_requests.append(record)
        return record

    def save_session(self, filename: str = "recorded_session.json") -> Path:
        """Save the captured requests to a JSON file."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.output_dir / filename
        serializable = [asdict(r) for r in self.recorded_requests]
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        return target_path

    def run_interactive(self, target_url: str, timeout_sec: int = 300) -> list[RecordedRequest]:
        """Launch Playwright browser, record registration flow, and save session.

        Requires user to interact with the opened browser and close it when finished.
        """
        from playwright.sync_api import sync_playwright

        self.recorded_requests.clear()
        self._counter = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            def on_response(response: Any) -> None:
                try:
                    request = response.request
                    body = None
                    try:
                        # Only fetch body for text/json
                        ct = response.headers.get("content-type", "")
                        if "json" in ct or "text" in ct or "javascript" in ct:
                            body = response.text()
                    except Exception:
                        body = None

                    self.record_request_response(
                        url=request.url,
                        method=request.method,
                        request_headers=request.headers,
                        post_data=request.post_data,
                        status=response.status,
                        response_headers=response.headers,
                        response_body=body,
                    )
                except Exception as exc:
                    logger.debug("Error recording response: %s", exc)

            page.on("response", on_response)
            page.goto(target_url)

            # Wait until page is closed by user or timeout
            start = time.monotonic()
            while not page.is_closed() and (time.monotonic() - start < timeout_sec):
                time.sleep(0.5)

            context.close()
            browser.close()

        self.save_session()
        return self.recorded_requests
