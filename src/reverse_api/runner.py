"""Autonomous recipe runner powered by curl_cffi.

Replays service recipes using Chrome TLS impersonation (JA3/JA4) for anti-bot bypass,
integrates with temp_mail for email/OTP verification, and persists sessions to State Vault.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from curl_cffi import requests

from .synthesizer import ServiceRecipe
from .temp_mail import TempMailClient
from .vault import get_profiles_dir

logger = logging.getLogger(__name__)

TEMPLATE_VAR_REGEX = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


@dataclass
class RegistrationResult:
    """Outcome of an autonomous registration workflow."""
    success: bool
    email: str
    password: str
    profile_name: str
    cookies_count: int
    error: str | None = None
    verification_code: str | None = None
    verification_url: str | None = None


def render_template_string(template_str: str, context: dict[str, Any]) -> str:
    """Replace {{var}} markers in a string with values from context."""
    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return str(context.get(var_name, match.group(0)))

    return TEMPLATE_VAR_REGEX.sub(replacer, template_str)


def render_template_data(data: Any, context: dict[str, Any]) -> Any:
    """Recursively render template variables in dicts, lists, and strings."""
    if isinstance(data, str):
        return render_template_string(data, context)
    elif isinstance(data, dict):
        return {k: render_template_data(v, context) for k, v in data.items()}
    elif isinstance(data, list):
        return [render_template_data(i, context) for i in data]
    return data


class AutonomousRunner:
    """Executes ServiceRecipes autonomously without running heavy browsers."""

    def __init__(
        self,
        temp_mail_client: TempMailClient | None = None,
        impersonate: str = "chrome120",
        timeout: float = 30.0,
    ) -> None:
        self.temp_mail = temp_mail_client or TempMailClient()
        self.impersonate = impersonate
        self.timeout = timeout

    def _save_session_to_vault(self, session: requests.Session, profile_name: str) -> Path:
        """Persist session cookies to the State Vault (~/.reverse-api/profiles)."""
        profiles_dir = get_profiles_dir()
        target_path = profiles_dir / f"{profile_name}.json"

        cookies_list = []
        for cookie in session.cookies:
            cookies_list.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "secure": cookie.secure,
            })

        state = {
            "cookies": cookies_list,
            "origins": [],
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        return target_path

    def run(
        self,
        recipe: ServiceRecipe,
        profile_name: str | None = None,
        custom_email: str | None = None,
        custom_password: str | None = None,
        wait_for_mail_timeout_sec: int = 60,
    ) -> RegistrationResult:
        """Execute the registration workflow defined in the ServiceRecipe."""
        email = custom_email or ""
        password = custom_password or secrets.token_urlsafe(12)
        prof_name = profile_name or f"{recipe.name}_{secrets.token_hex(3)}"
        session: requests.Session | None = None

        try:
            # 1. Provision email
            if not email:
                inbox = self.temp_mail.create_mailbox()
                email = inbox.address

            context: dict[str, Any] = {
                "email": email,
                "password": password,
                "profile_name": prof_name,
            }

            session = requests.Session(impersonate=self.impersonate)

            # 2. Execute recipe steps sequentially
            for step in recipe.steps:
                target_url = render_template_string(step.url, context)
                headers = render_template_data(step.headers, context)
                payload = render_template_data(step.payload, context)

                is_json = False
                ct = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
                if "json" in ct or isinstance(payload, (dict, list)):
                    is_json = True

                if step.method == "GET":
                    resp = session.get(target_url, headers=headers, timeout=self.timeout)
                elif step.method in ("POST", "PUT", "PATCH"):
                    if is_json:
                        resp = session.request(step.method, target_url, headers=headers, json=payload, timeout=self.timeout)
                    else:
                        resp = session.request(step.method, target_url, headers=headers, data=payload, timeout=self.timeout)
                else:
                    resp = session.request(step.method, target_url, headers=headers, timeout=self.timeout)

                # Process extraction rules
                for extract in step.extracts:
                    if extract.source == "json_key":
                        try:
                            body_json = resp.json()
                            if isinstance(body_json, dict) and extract.pattern_or_key in body_json:
                                context[extract.target_var] = body_json[extract.pattern_or_key]
                        except Exception as e:
                            logger.debug("Failed extracting json key %s: %s", extract.pattern_or_key, e)
                    elif extract.source == "regex":
                        pattern = re.compile(extract.pattern_or_key)
                        match = pattern.search(resp.text)
                        if match:
                            context[extract.target_var] = match.group(1)

            # 3. Handle verification if required
            verif_code = None
            verif_url = None
            if recipe.verification_mode in ("otp_code", "activation_link"):
                verif = self.temp_mail.wait_for_verification(
                    address=email,
                    timeout_sec=wait_for_mail_timeout_sec,
                )
                verif_code = verif.code
                verif_url = verif.url

                if recipe.verification_mode == "activation_link" and verif_url:
                    # Follow activation link in the same session
                    session.get(verif_url, timeout=self.timeout)

            # 4. Save session state to Vault
            self._save_session_to_vault(session, prof_name)

            return RegistrationResult(
                success=True,
                email=email,
                password=password,
                profile_name=prof_name,
                cookies_count=len(session.cookies),
                verification_code=verif_code,
                verification_url=verif_url,
            )

        except Exception as exc:
            logger.error("Runner execution failed for recipe %s: %s", recipe.name, exc)
            return RegistrationResult(
                success=False,
                email=email,
                password=password,
                profile_name=prof_name,
                cookies_count=0,
                error=str(exc),
            )
        finally:
            if session is not None:
                session.close()
