"""Tests for recon.py reconnaissance and filtering engine."""

import json
from pathlib import Path

from reverse_api.recon import (
    ReconEngine,
    is_relevant_url,
    sanitize_headers,
)


def test_is_relevant_url():
    # Irrelevant extensions
    assert not is_relevant_url("https://example.com/logo.png")
    assert not is_relevant_url("https://example.com/styles.css")
    assert not is_relevant_url("https://example.com/font.woff2")
    assert not is_relevant_url("https://example.com/favicon.ico")

    # Irrelevant tracking domains
    assert not is_relevant_url("https://mc.yandex.ru/watch/12345")
    assert not is_relevant_url("https://www.google-analytics.com/g/collect")
    assert not is_relevant_url("https://sub.hotjar.com/api/v1")

    # Relevant API endpoints
    assert is_relevant_url("https://example.com/api/v1/auth/register")
    assert is_relevant_url("https://example.com/users/signup.json")
    assert is_relevant_url("https://sub.example.com/register")


def test_sanitize_headers():
    raw_headers = {
        "Host": "example.com",
        "Connection": "keep-alive",
        "sec-ch-ua": '"Chromium";v="128"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        ":method": "POST",
        "Content-Type": "application/json",
        "Authorization": "Bearer token123",
        "X-CSRF-Token": "csrf_val_456",
        "Accept": "*/*",
    }

    clean = sanitize_headers(raw_headers)

    assert "sec-ch-ua" not in clean
    assert "sec-fetch-dest" not in clean
    assert "Host" not in clean
    assert ":method" not in clean

    assert clean["Content-Type"] == "application/json"
    assert clean["Authorization"] == "Bearer token123"
    assert clean["X-CSRF-Token"] == "csrf_val_456"
    assert clean["Accept"] == "*/*"


def test_record_request_response_json(tmp_path: Path):
    engine = ReconEngine(output_dir=tmp_path)

    rec = engine.record_request_response(
        url="https://example.com/api/register",
        method="POST",
        request_headers={"Content-Type": "application/json", "sec-ch-ua": "test"},
        post_data='{"email": "test@mail.ru", "password": "pass"}',
        status=200,
        response_headers={"content-type": "application/json; charset=utf-8"},
        response_body='{"status": "ok", "user_id": 99}',
    )

    assert rec is not None
    assert rec.id == 1
    assert rec.method == "POST"
    assert rec.post_data == {"email": "test@mail.ru", "password": "pass"}
    assert rec.headers == {"Content-Type": "application/json"}
    assert rec.status == 200
    assert rec.response_body == '{"status": "ok", "user_id": 99}'


def test_record_request_response_filters_static(tmp_path: Path):
    engine = ReconEngine(output_dir=tmp_path)

    # Static CSS GET request
    rec = engine.record_request_response(
        url="https://example.com/assets/app.css",
        method="GET",
        request_headers={},
        post_data=None,
        status=200,
        response_headers={"content-type": "text/css"},
    )
    assert rec is None
    assert len(engine.recorded_requests) == 0


def test_save_session(tmp_path: Path):
    engine = ReconEngine(output_dir=tmp_path)

    engine.record_request_response(
        url="https://example.com/api/step1",
        method="GET",
        request_headers={"Accept": "application/json"},
        post_data=None,
        status=200,
        response_headers={"content-type": "application/json"},
        response_body='{"csrf": "abc"}',
    )

    out_file = engine.save_session("my_session.json")
    assert out_file.exists()

    with open(out_file, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["url"] == "https://example.com/api/step1"
    assert data[0]["method"] == "GET"
