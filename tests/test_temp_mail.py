"""Tests for temp_mail.py client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from reverse_api.temp_mail import (
    Inbox,
    TempMailClient,
    TempMailError,
    TempMailTimeoutError,
    VerificationData,
)


@pytest.fixture
def client() -> TempMailClient:
    return TempMailClient(base_url="http://test-mail:8000", default_domain="test.domain")


def test_generate_random_address(client: TempMailClient):
    addr = client.generate_random_address(prefix="bot")
    assert addr.startswith("bot_")
    assert addr.endswith("@test.domain")


def test_create_mailbox_success(client: TempMailClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 42, "address": "test@test.domain", "is_active": True}

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        inbox = client.create_mailbox("test@test.domain")
        assert isinstance(inbox, Inbox)
        assert inbox.address == "test@test.domain"
        assert inbox.id == 42
        mock_post.assert_called_once_with(
            "http://test-mail:8000/mailboxes",
            params={"address": "test@test.domain"},
        )


def test_create_mailbox_failure(client: TempMailClient):
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(TempMailError, match="Failed to create mailbox"):
            client.create_mailbox("test@test.domain")


def test_get_emails_success(client: TempMailClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"id": 1, "confirm_code": "123456", "subject": "OTP"}
    ]

    with patch("httpx.Client.get", return_value=mock_resp):
        emails = client.get_emails("test@test.domain")
        assert len(emails) == 1
        assert emails[0]["confirm_code"] == "123456"


def test_get_emails_404_returns_empty(client: TempMailClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.Client.get", return_value=mock_resp):
        emails = client.get_emails("notfound@test.domain")
        assert emails == []


def test_wait_for_verification_success_server_fields(client: TempMailClient):
    mock_emails = [
        {
            "id": 10,
            "subject": "Your verification code",
            "confirm_code": "849201",
            "confirm_url": "https://example.com/confirm?token=xyz",
            "from_addr": "service@example.com",
            "body_text": "Code: 849201",
        }
    ]

    with patch.object(client, "get_emails", return_value=mock_emails):
        res = client.wait_for_verification("test@test.domain", timeout_sec=5)
        assert isinstance(res, VerificationData)
        assert res.code == "849201"
        assert res.url == "https://example.com/confirm?token=xyz"
        assert res.subject == "Your verification code"


def test_wait_for_verification_fallback_regex(client: TempMailClient):
    mock_emails = [
        {
            "id": 11,
            "subject": "Activate account",
            "confirm_code": None,
            "confirm_url": None,
            "body_text": "Please enter 958210 to activate your account or click https://example.com/activate?token=abc",
        }
    ]

    with patch.object(client, "get_emails", return_value=mock_emails):
        res = client.wait_for_verification("test@test.domain", timeout_sec=5)
        assert res.code == "958210"
        assert res.url == "https://example.com/activate?token=abc"


def test_wait_for_verification_timeout(client: TempMailClient):
    with patch.object(client, "get_emails", return_value=[]):
        with pytest.raises(TempMailTimeoutError, match="Timeout"):
            client.wait_for_verification("test@test.domain", timeout_sec=1, poll_interval_sec=0.2)
