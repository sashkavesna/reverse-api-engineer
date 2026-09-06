"""Client for the internal Temporary Mail (temp_mail) API on VPS.

Enables automated mailbox provisioning and incoming OTP/link polling for registration flows.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TEMP_MAIL_URL = "http://mail.expertcore.ru:8000"
DEFAULT_MAIL_DOMAIN = "mail.expertcore.ru"

OTP_REGEX = re.compile(r"\b(\d{4,8})\b")
URL_REGEX = re.compile(r'https?://[^\s<>"\']+(?:confirm|verify|activate|token)[^\s<>"\']*', re.IGNORECASE)


class TempMailError(Exception):
    """Base exception for temp_mail API errors."""
    pass


class TempMailTimeoutError(TempMailError):
    """Raised when waiting for an incoming email times out."""
    pass


@dataclass
class Inbox:
    """Represents a provisioned temporary mailbox."""
    address: str
    id: int | None = None
    is_active: bool = True


@dataclass
class VerificationData:
    """Extracted verification credentials from an incoming email."""
    code: str | None = None
    url: str | None = None
    subject: str | None = None
    from_addr: str | None = None
    raw_email: dict[str, Any] | None = None


class TempMailClient:
    """HTTP client for the temp_mail service."""

    def __init__(
        self,
        base_url: str = DEFAULT_TEMP_MAIL_URL,
        default_domain: str = DEFAULT_MAIL_DOMAIN,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_domain = default_domain
        self.timeout = timeout

    def generate_random_address(self, prefix: str = "reg", domain: str | None = None) -> str:
        """Generate a random email address."""
        target_domain = domain or self.default_domain
        token = secrets.token_hex(4)
        return f"{prefix}_{token}@{target_domain}"

    def create_mailbox(self, address: str | None = None) -> Inbox:
        """Create or ensure a mailbox exists on the temp_mail server.

        Args:
            address: Explicit email address. If None, a random address is generated.

        Returns:
            Inbox object with address and server ID.
        """
        email_addr = address or self.generate_random_address()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/mailboxes",
                    params={"address": email_addr},
                )
                response.raise_for_status()
                data = response.json()
                return Inbox(
                    address=data.get("address", email_addr),
                    id=data.get("id"),
                    is_active=data.get("is_active", True),
                )
        except httpx.HTTPError as exc:
            raise TempMailError(f"Failed to create mailbox '{email_addr}': {exc}") from exc

    def get_emails(self, address: str) -> list[dict[str, Any]]:
        """Fetch all received emails for the given address.

        Args:
            address: The email address to inspect.

        Returns:
            List of email dictionaries sorted newest first.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/mailboxes/{address}/emails")
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                result: list[dict[str, Any]] = response.json()
                return result
        except httpx.HTTPError as exc:
            raise TempMailError(f"Failed to fetch emails for '{address}': {exc}") from exc

    def wait_for_verification(
        self,
        address: str,
        timeout_sec: int = 60,
        poll_interval_sec: float = 2.0,
        filter_fn: Callable[[dict[str, Any]], bool] | None = None,
    ) -> VerificationData:
        """Poll the mailbox until an email arrives and extract verification code/URL.

        Args:
            address: Mailbox address to monitor.
            timeout_sec: Maximum wait time in seconds.
            poll_interval_sec: Interval between checks.
            filter_fn: Optional predicate to match a specific email.

        Returns:
            VerificationData containing parsed code and/or URL.

        Raises:
            TempMailTimeoutError: If no matching email is received within the timeout.
        """
        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout_sec:
            emails = self.get_emails(address)
            for email in emails:
                if filter_fn and not filter_fn(email):
                    continue

                code = email.get("confirm_code")
                url = email.get("confirm_url")
                body = email.get("body_text") or ""

                # Fallback regex parsing if the server parser didn't extract them
                if not code:
                    match = OTP_REGEX.search(body)
                    if match:
                        code = match.group(1)

                if not url:
                    url_match = URL_REGEX.search(body)
                    if url_match:
                        url = url_match.group(0)

                if code or url:
                    return VerificationData(
                        code=code,
                        url=url,
                        subject=email.get("subject"),
                        from_addr=email.get("from_addr"),
                        raw_email=email,
                    )

            time.sleep(poll_interval_sec)

        raise TempMailTimeoutError(
            f"Timeout ({timeout_sec}s) waiting for verification email at '{address}'"
        )
