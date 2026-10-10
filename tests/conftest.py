"""Isolate any test that touches config_manager away from the real
config/api_keys.json — it holds the user's live Gemini key.

config_manager resolves CONFIG_FILE at import time, so the redirection has to
patch the module attribute rather than an environment variable.
"""
import pytest

from memory import config_manager


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Point config_manager at a throwaway config file."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "api_keys.json"

    monkeypatch.setattr(config_manager, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_file)
    return cfg_file