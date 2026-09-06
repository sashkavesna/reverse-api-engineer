"""Recipe synthesizer: transforms recorded session traffic into a declarative ServiceRecipe.

Analyzes captured HTTP requests, identifies registration endpoints, extracts dynamic
CSRF tokens, cookies, and verification patterns, and produces an actionable recipe for replay.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .recon import RecordedRequest

logger = logging.getLogger(__name__)

REGISTRATION_KEYWORDS = ("register", "signup", "sign-up", "create", "user", "auth", "join")
EMAIL_FIELDS = ("email", "mail", "username", "login", "user")
PASSWORD_FIELDS = ("password", "pass", "passwd")
CSRF_PATTERNS = (
    re.compile(r'name=["\'](?:_csrf|csrf[-_]?token|authenticity_token)["\']\s+value=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'["\'](?:csrf[-_]?token|csrf)["\']\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE),
)


@dataclass
class ExtractRule:
    """Extraction instruction for dynamic tokens from responses."""
    source: str  # "json_key", "regex", "header", "cookie"
    target_var: str
    pattern_or_key: str


@dataclass
class RecipeStep:
    """A single HTTP step within a ServiceRecipe."""
    name: str
    url: str
    method: str
    headers: dict[str, str] = field(default_factory=dict)
    payload: Any | None = None
    extracts: list[ExtractRule] = field(default_factory=list)


@dataclass
class ServiceRecipe:
    """Declarative definition of a service's registration/action workflow."""
    name: str
    base_url: str
    verification_mode: str  # "otp_code" | "activation_link" | "none"
    steps: list[RecipeStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, filepath: Path | str) -> Path:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    @classmethod
    def load(cls, filepath: Path | str) -> ServiceRecipe:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        steps = []
        for s in data.get("steps", []):
            extracts = [ExtractRule(**e) for e in s.get("extracts", [])]
            steps.append(RecipeStep(
                name=s["name"],
                url=s["url"],
                method=s["method"],
                headers=s.get("headers", {}),
                payload=s.get("payload"),
                extracts=extracts,
            ))

        return cls(
            name=data["name"],
            base_url=data["base_url"],
            verification_mode=data.get("verification_mode", "none"),
            steps=steps,
        )


class RecipeSynthesizer:
    """Synthesizes clean, executable ServiceRecipes from raw recorded requests."""

    def __init__(self) -> None:
        pass

    def _find_registration_request(self, records: list[RecordedRequest]) -> RecordedRequest | None:
        """Locate the primary form submission request in the sequence."""
        for rec in reversed(records):
            if rec.method not in ("POST", "PUT", "PATCH"):
                continue

            url_lower = rec.url.lower()
            if any(kw in url_lower for kw in REGISTRATION_KEYWORDS):
                return rec

            # Check body keys if it's a dict
            if isinstance(rec.post_data, dict):
                keys = [k.lower() for k in rec.post_data.keys()]
                if any(p in keys for p in PASSWORD_FIELDS) or any(e in keys for e in EMAIL_FIELDS):
                    return rec

        # Fallback: any POST with body
        for rec in reversed(records):
            if rec.method == "POST" and rec.post_data:
                return rec

        return None

    def _templatize_payload(self, payload: Any) -> Any:
        """Replace user-specific values with template variables."""
        if not isinstance(payload, dict):
            return payload

        templated: dict[str, Any] = {}
        for k, v in payload.items():
            k_lower = k.lower()
            if any(e == k_lower or e in k_lower for e in EMAIL_FIELDS) and isinstance(v, str) and "@" in v:
                templated[k] = "{{email}}"
            elif any(p == k_lower or p in k_lower for p in PASSWORD_FIELDS):
                templated[k] = "{{password}}"
            else:
                templated[k] = v

        return templated

    def _find_csrf_source(
        self,
        records: list[RecordedRequest],
        target_token: str,
        reg_index: int,
    ) -> tuple[int, ExtractRule] | None:
        """Search prior GET/POST requests for where the token originated."""
        for i in range(reg_index):
            rec = records[i]
            body = rec.response_body or ""

            # Check JSON response
            if body.strip().startswith(("{", "[")):
                try:
                    data = json.loads(body)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if str(v) == target_token:
                                return i, ExtractRule(
                                    source="json_key",
                                    target_var="csrf_token",
                                    pattern_or_key=k,
                                )
                except Exception:
                    pass

            # Check HTML regex
            for pattern in CSRF_PATTERNS:
                match = pattern.search(body)
                if match and match.group(1) == target_token:
                    return i, ExtractRule(
                        source="regex",
                        target_var="csrf_token",
                        pattern_or_key=pattern.pattern,
                    )

        return None

    def synthesize(
        self,
        records: list[RecordedRequest],
        service_name: str = "custom_service",
        verification_mode: str = "otp_code",
    ) -> ServiceRecipe:
        """Analyze recorded requests and produce an executable ServiceRecipe."""
        if not records:
            raise ValueError("No recorded requests provided for synthesis.")

        reg_req = self._find_registration_request(records)
        if not reg_req:
            raise ValueError("Could not identify registration endpoint in recorded traffic.")

        reg_index = records.index(reg_req)
        parsed_url = urlparse(reg_req.url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        steps: list[RecipeStep] = []

        # Check for dynamic CSRF in headers or body
        csrf_in_header = None
        csrf_header_name = None
        for h_name, h_val in reg_req.headers.items():
            if "csrf" in h_name.lower() or "token" in h_name.lower():
                csrf_in_header = h_val
                csrf_header_name = h_name
                break

        # Check if previous GET step provided CSRF
        if csrf_in_header and reg_index > 0:
            found = self._find_csrf_source(records, csrf_in_header, reg_index)
            if found:
                step_idx, rule = found
                init_rec = records[step_idx]
                steps.append(RecipeStep(
                    name="get_csrf_and_session",
                    url=init_rec.url,
                    method=init_rec.method,
                    headers=init_rec.headers,
                    extracts=[rule],
                ))

        # Main registration submission step
        templated_payload = self._templatize_payload(reg_req.post_data)
        reg_headers = dict(reg_req.headers)

        if csrf_header_name and csrf_in_header:
            reg_headers[csrf_header_name] = "{{csrf_token}}"

        steps.append(RecipeStep(
            name="submit_registration",
            url=reg_req.url,
            method=reg_req.method,
            headers=reg_headers,
            payload=templated_payload,
        ))

        return ServiceRecipe(
            name=service_name,
            base_url=base_url,
            verification_mode=verification_mode,
            steps=steps,
        )
