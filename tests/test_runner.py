"""Tests for runner.py autonomous execution engine."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from reverse_api.runner import (
    AutonomousRunner,
    RegistrationResult,
    render_template_data,
    render_template_string,
)
from reverse_api.synthesizer import ExtractRule, RecipeStep, ServiceRecipe
from reverse_api.temp_mail import Inbox, TempMailClient, VerificationData


def test_render_template():
    context = {"email": "user@example.com", "code": "1234"}

    res = render_template_string("Hello {{email}}, your code is {{code}}", context)
    assert res == "Hello user@example.com, your code is 1234"

    dict_data = {
        "user": "{{email}}",
        "nested": {"token": "{{code}}", "fixed": 42},
        "items": ["{{email}}", "constant"],
    }
    rendered = render_template_data(dict_data, context)
    assert rendered["user"] == "user@example.com"
    assert rendered["nested"]["token"] == "1234"
    assert rendered["nested"]["fixed"] == 42
    assert rendered["items"] == ["user@example.com", "constant"]


def test_runner_execution_success(tmp_path: Path):
    recipe = ServiceRecipe(
        name="mock_svc",
        base_url="https://mock.service.com",
        verification_mode="activation_link",
        steps=[
            RecipeStep(
                name="step1",
                url="https://mock.service.com/csrf",
                method="GET",
                extracts=[ExtractRule(source="json_key", target_var="csrf", pattern_or_key="token")],
            ),
            RecipeStep(
                name="step2",
                url="https://mock.service.com/register",
                method="POST",
                headers={"X-CSRF": "{{csrf}}"},
                payload={"email": "{{email}}", "pass": "{{password}}"},
            ),
        ],
    )

    mock_temp_mail = MagicMock(spec=TempMailClient)
    mock_temp_mail.create_mailbox.return_value = Inbox(address="auto_user@test.mail", id=1)
    mock_temp_mail.wait_for_verification.return_value = VerificationData(
        url="https://mock.service.com/activate?token=999",
        code=None,
    )

    runner = AutonomousRunner(temp_mail_client=mock_temp_mail)

    # Mock curl_cffi requests Session
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {"token": "secret_csrf"}
    mock_resp1.text = '{"token": "secret_csrf"}'

    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200

    mock_resp3 = MagicMock()
    mock_resp3.status_code = 200

    with patch("curl_cffi.requests.Session") as mock_session_cls, \
         patch("reverse_api.runner.get_profiles_dir", return_value=tmp_path):

        mock_session = MagicMock()
        mock_session.get.side_effect = [mock_resp1, mock_resp3]
        mock_session.request.return_value = mock_resp2
        mock_session.cookies = []
        mock_session_cls.return_value = mock_session

        result = runner.run(recipe, profile_name="test_profile")

        assert isinstance(result, RegistrationResult)
        assert result.success is True
        assert result.email == "auto_user@test.mail"
        assert result.profile_name == "test_profile"
        assert result.verification_url == "https://mock.service.com/activate?token=999"

        # Check vault profile was saved
        saved_file = tmp_path / "test_profile.json"
        assert saved_file.exists()


def test_runner_execution_failure():
    recipe = ServiceRecipe(
        name="fail_svc",
        base_url="https://fail.com",
        verification_mode="none",
        steps=[RecipeStep(name="step", url="https://fail.com", method="GET")],
    )

    mock_temp_mail = MagicMock(spec=TempMailClient)
    mock_temp_mail.create_mailbox.side_effect = RuntimeError("Network error")

    runner = AutonomousRunner(temp_mail_client=mock_temp_mail)
    result = runner.run(recipe)

    assert result.success is False
    assert "Network error" in (result.error or "")
