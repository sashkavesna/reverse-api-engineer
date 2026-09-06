"""Tests for synthesizer.py ServiceRecipe generation."""

from pathlib import Path

import pytest

from reverse_api.recon import RecordedRequest
from reverse_api.synthesizer import (
    ExtractRule,
    RecipeStep,
    RecipeSynthesizer,
    ServiceRecipe,
)


def test_service_recipe_save_and_load(tmp_path: Path):
    step1 = RecipeStep(
        name="step1",
        url="https://example.com/login",
        method="GET",
        headers={"Accept": "application/json"},
        extracts=[ExtractRule(source="json_key", target_var="token", pattern_or_key="csrf")],
    )
    step2 = RecipeStep(
        name="step2",
        url="https://example.com/api/register",
        method="POST",
        headers={"X-CSRF-Token": "{{token}}"},
        payload={"email": "{{email}}", "password": "{{password}}"},
    )

    recipe = ServiceRecipe(
        name="test_service",
        base_url="https://example.com",
        verification_mode="otp_code",
        steps=[step1, step2],
    )

    save_path = tmp_path / "recipe.json"
    recipe.save(save_path)
    assert save_path.exists()

    loaded = ServiceRecipe.load(save_path)
    assert loaded.name == "test_service"
    assert loaded.base_url == "https://example.com"
    assert loaded.verification_mode == "otp_code"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].extracts[0].target_var == "token"
    assert loaded.steps[1].payload["email"] == "{{email}}"


def test_synthesizer_direct_post():
    records = [
        RecordedRequest(
            id=1,
            url="https://site.com/api/auth/register",
            method="POST",
            headers={"Content-Type": "application/json"},
            post_data={"email": "realuser@mail.com", "password": "SecretPassword123"},
            status=200,
            response_headers={"content-type": "application/json"},
            response_body='{"ok": true}',
            timestamp=100.0,
        )
    ]

    synth = RecipeSynthesizer()
    recipe = synth.synthesize(records, service_name="mysite")

    assert recipe.name == "mysite"
    assert recipe.base_url == "https://site.com"
    assert len(recipe.steps) == 1
    assert recipe.steps[0].url == "https://site.com/api/auth/register"
    assert recipe.steps[0].payload == {"email": "{{email}}", "password": "{{password}}"}


def test_synthesizer_detects_csrf_step():
    records = [
        RecordedRequest(
            id=1,
            url="https://site.com/signup",
            method="GET",
            headers={"Accept": "text/html"},
            post_data=None,
            status=200,
            response_headers={"content-type": "text/html"},
            response_body='<html><input name="_csrf" value="secret_csrf_999"></html>',
            timestamp=100.0,
        ),
        RecordedRequest(
            id=2,
            url="https://site.com/api/signup",
            method="POST",
            headers={"Content-Type": "application/json", "X-CSRF-Token": "secret_csrf_999"},
            post_data={"email": "tester@domain.com", "password": "Pass"},
            status=200,
            response_headers={"content-type": "application/json"},
            response_body='{"status": "pending_verification"}',
            timestamp=102.0,
        ),
    ]

    synth = RecipeSynthesizer()
    recipe = synth.synthesize(records, service_name="secured_site")

    assert len(recipe.steps) == 2
    assert recipe.steps[0].name == "get_csrf_and_session"
    assert len(recipe.steps[0].extracts) == 1
    assert recipe.steps[0].extracts[0].target_var == "csrf_token"
    assert recipe.steps[1].headers["X-CSRF-Token"] == "{{csrf_token}}"
    assert recipe.steps[1].payload["email"] == "{{email}}"


def test_synthesizer_raises_on_empty():
    synth = RecipeSynthesizer()
    with pytest.raises(ValueError, match="No recorded requests"):
        synth.synthesize([])
