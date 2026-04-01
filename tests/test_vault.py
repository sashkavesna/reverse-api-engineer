"""Tests for vault.py - Profile management (State Vault)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from reverse_api.vault import (
    ProfileNotFoundError,
    _validate_profile_name,
    delete_profile,
    list_profiles,
    load_profile,
    save_profile,
)


# --- Helpers ---

SAMPLE_STATE = {
    "cookies": [
        {"name": "session_id", "value": "abc123", "domain": ".example.com", "path": "/"},
        {"name": "csrf", "value": "xyz789", "domain": ".example.com", "path": "/"},
        {"name": "auth", "value": "tok456", "domain": "api.example.com", "path": "/v1"},
    ],
    "origins": [],
}


def _write_profile(profiles_dir: Path, name: str, data: dict) -> Path:
    """Write a profile JSON file to the profiles directory."""
    path = profiles_dir / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --- _validate_profile_name ---

class TestValidateProfileName:

    def test_valid_names(self):
        assert _validate_profile_name("twitter-acc1") == "twitter-acc1"
        assert _validate_profile_name("my_profile") == "my_profile"
        assert _validate_profile_name("Test123") == "Test123"

    def test_empty_name(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_profile_name("")

    def test_special_characters(self):
        with pytest.raises(ValueError, match="Invalid profile name"):
            _validate_profile_name("my profile")

    def test_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid profile name"):
            _validate_profile_name("../etc/passwd")

    def test_dots_rejected(self):
        with pytest.raises(ValueError, match="Invalid profile name"):
            _validate_profile_name("name.with.dots")


# --- save_profile ---

class TestSaveProfile:

    def test_saves_state_to_json(self, tmp_path):
        mock_context = MagicMock()
        mock_context.storage_state.return_value = SAMPLE_STATE

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            path = save_profile("test-site", mock_context)

        assert path == tmp_path / "test-site.json"
        assert path.exists()

        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["cookies"] == SAMPLE_STATE["cookies"]

    def test_overwrites_existing(self, tmp_path):
        _write_profile(tmp_path, "mysite", {"cookies": [{"name": "old", "value": "old"}], "origins": []})

        mock_context = MagicMock()
        mock_context.storage_state.return_value = SAMPLE_STATE

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            save_profile("mysite", mock_context)

        saved = json.loads((tmp_path / "mysite.json").read_text(encoding="utf-8"))
        assert len(saved["cookies"]) == 3

    def test_invalid_name_raises(self, tmp_path):
        mock_context = MagicMock()
        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            with pytest.raises(ValueError):
                save_profile("bad name!", mock_context)


# --- load_profile ---

class TestLoadProfile:

    def test_loads_cookies(self, tmp_path):
        _write_profile(tmp_path, "test-site", SAMPLE_STATE)

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            cookies = load_profile("test-site")

        assert isinstance(cookies, httpx.Cookies)
        assert cookies.get("session_id", domain=".example.com") == "abc123"
        assert cookies.get("auth", domain="api.example.com") == "tok456"

    def test_missing_profile_raises(self, tmp_path):
        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            with pytest.raises(ProfileNotFoundError, match="not found"):
                load_profile("nonexistent")

    def test_corrupted_json_raises(self, tmp_path):
        (tmp_path / "broken.json").write_text("not valid json{{{", encoding="utf-8")

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="corrupted"):
                load_profile("broken")

    def test_missing_cookies_key_raises(self, tmp_path):
        _write_profile(tmp_path, "nocookies", {"origins": []})

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="does not contain valid cookie data"):
                load_profile("nocookies")

    def test_empty_cookies_list(self, tmp_path):
        _write_profile(tmp_path, "empty", {"cookies": [], "origins": []})

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            cookies = load_profile("empty")

        assert isinstance(cookies, httpx.Cookies)
        assert len(list(cookies.jar)) == 0


# --- list_profiles ---

class TestListProfiles:

    def test_empty_directory(self, tmp_path):
        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            result = list_profiles()
        assert result == []

    def test_lists_profiles_with_metadata(self, tmp_path):
        _write_profile(tmp_path, "site-a", SAMPLE_STATE)
        _write_profile(tmp_path, "site-b", {"cookies": [{"name": "x", "value": "1", "domain": ".other.com"}], "origins": []})

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            result = list_profiles()

        assert len(result) == 2

        a = next(p for p in result if p["name"] == "site-a")
        assert a["cookie_count"] == 3
        assert "example.com" in a["domains"]

        b = next(p for p in result if p["name"] == "site-b")
        assert b["cookie_count"] == 1

    def test_corrupted_profile_still_listed(self, tmp_path):
        (tmp_path / "broken.json").write_text("invalid json", encoding="utf-8")

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            result = list_profiles()

        assert len(result) == 1
        assert result[0]["name"] == "broken"
        assert result[0]["cookie_count"] == 0


# --- delete_profile ---

class TestDeleteProfile:

    def test_deletes_existing(self, tmp_path):
        _write_profile(tmp_path, "to-delete", SAMPLE_STATE)

        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            path = delete_profile("to-delete")

        assert not path.exists()

    def test_missing_profile_raises(self, tmp_path):
        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            with pytest.raises(ProfileNotFoundError, match="not found"):
                delete_profile("nonexistent")

    def test_invalid_name_raises(self, tmp_path):
        with patch("reverse_api.vault.get_profiles_dir", return_value=tmp_path):
            with pytest.raises(ValueError):
                delete_profile("../hack")
