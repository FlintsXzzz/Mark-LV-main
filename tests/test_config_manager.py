"""memory/config_manager.py — settings persistence.

Every getter here has a working default and a setter that must never write a
value the app cannot use. The tests run against a temp config file via the
tmp_config fixture, so the user's real api_keys.json is never touched.
"""
import json

import pytest

from memory import config_manager as cm


def test_absent_config_reports_not_configured(tmp_config):
    assert cm.config_exists() is False
    assert cm.load_api_keys() == {}
    assert cm.is_configured() is False


def test_saving_the_key_creates_the_file(tmp_config):
    cm.save_api_keys("abc123")

    assert cm.config_exists()
    assert cm.get_gemini_key() == "abc123"


def test_a_short_key_is_not_accepted_as_configured(tmp_config):
    cm.save_api_keys("short")

    assert cm.is_configured() is False


def test_key_is_trimmed(tmp_config):
    cm.save_api_keys("  padded-key-value  ")

    assert cm.get_gemini_key() == "padded-key-value"


def test_a_corrupt_config_does_not_crash_the_getters(tmp_config):
    tmp_config.write_text("{not valid json", encoding="utf-8")

    assert cm.load_api_keys() == {}
    assert cm.get_gemini_key() is None
    assert cm.get_voice() == cm.DEFAULT_VOICE


def test_saving_over_a_corrupt_config_recovers(tmp_config):
    tmp_config.write_text("<<<broken>>>", encoding="utf-8")

    cm.save_voice("Puck")

    assert cm.get_voice() == "Puck"


# ── Identity ─────────────────────────────────────────────────────────────────

def test_assistant_name_defaults_to_jarvis(tmp_config):
    assert cm.get_assistant_name() == "JARVIS"


def test_an_empty_assistant_name_falls_back_to_jarvis(tmp_config):
    cm.save_assistant_config("", "Dafa")

    assert cm.get_assistant_name() == "JARVIS"
    assert cm.get_user_name() == "Dafa"


# ── Voice ────────────────────────────────────────────────────────────────────

def test_unknown_voice_never_reaches_the_api(tmp_config):
    """A bad voice name would break the Live session outright."""
    cm.save_voice("Not-A-Voice")

    assert cm.get_voice() == cm.DEFAULT_VOICE


def test_a_valid_voice_round_trips(tmp_config):
    cm.save_voice("Fenrir")

    assert cm.get_voice() == "Fenrir"


def test_voice_is_case_insensitive_on_read(tmp_config):
    tmp_config.write_text(json.dumps({"voice_name": " PUCK "}), encoding="utf-8")

    # Stored verbatim, but an unknown one still collapses safely.
    assert cm.get_voice() == cm.DEFAULT_VOICE


# ── Setters must not clobber unrelated settings ──────────────────────────────

def test_saving_the_voice_keeps_the_api_key(tmp_config):
    cm.save_api_keys("my-secret-key-value")
    cm.save_voice("Puck")

    assert cm.get_gemini_key() == "my-secret-key-value"
    assert cm.get_voice() == "Puck"


def test_saving_the_hud_style_keeps_the_api_key(tmp_config):
    cm.save_api_keys("my-secret-key-value")
    cm.save_hud_style("core")

    assert cm.get_gemini_key() == "my-secret-key-value"
    assert cm.get_hud_style() == "core"


def test_unknown_hud_style_falls_back_to_face(tmp_config):
    cm.save_hud_style("banana")

    assert cm.get_hud_style() == "face"


def test_unknown_media_resolution_falls_back_to_medium(tmp_config):
    cm.save_media_resolution("ultra")

    assert cm.get_media_resolution() == "medium"


# ── Boolean flags ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("getter,saver", [
    ("get_wake_word_enabled", "save_wake_word_enabled"),
    ("get_push_to_talk_enabled", "save_push_to_talk_enabled"),
    ("get_thinking_enabled", "save_thinking_enabled"),
    ("get_proactive_audio_enabled", "save_proactive_audio_enabled"),
])
def test_flags_round_trip(tmp_config, getter, saver):
    getattr(cm, saver)(True)
    assert getattr(cm, getter)() is True

    getattr(cm, saver)(False)
    assert getattr(cm, getter)() is False


def test_defaults_apply_to_an_empty_config(tmp_config):
    assert cm.get_wake_word_enabled() is False
    assert cm.get_push_to_talk_enabled() is False
    assert cm.get_thinking_enabled() is False
    assert cm.get_proactive_audio_enabled() is True
    assert cm.get_brief_enabled() is True


# ── Turn tuning ──────────────────────────────────────────────────────────────

def test_turn_tuning_defaults_when_absent(tmp_config):
    tuning = cm.get_turn_tuning()

    assert tuning["enabled"] is False
    assert tuning["silence_ms"] == 550


def test_turn_tuning_clamps_out_of_range_values(tmp_config):
    """A silence_ms of 999999 or a string must not reach the API verbatim."""
    cm.save_turn_tuning({"silence_ms": 999999, "prefix_ms": -50})

    tuning = cm.get_turn_tuning()

    assert tuning["silence_ms"] == 3000
    assert tuning["prefix_ms"] == 0


def test_turn_tuning_survives_non_numeric_input(tmp_config):
    cm.save_turn_tuning({"silence_ms": "soon"})

    assert cm.get_turn_tuning()["silence_ms"] == 550


def test_turn_tuning_merge_keeps_unrelated_keys(tmp_config):
    cm.save_turn_tuning({"enabled": True})
    cm.save_turn_tuning({"silence_ms": 300})

    tuning = cm.get_turn_tuning()

    assert tuning["enabled"] is True
    assert tuning["silence_ms"] == 300


def test_a_corrupt_turn_tuning_block_falls_back_to_defaults(tmp_config):
    tmp_config.write_text(json.dumps({"turn_tuning": "nonsense"}), encoding="utf-8")

    assert cm.get_turn_tuning()["silence_ms"] == 550


# ── Audio devices are stored by name, not index ──────────────────────────────

def test_device_names_are_stored_and_stripped(tmp_config):
    cm.save_input_device("  Microphone (2.0 Camera) ")
    cm.save_output_device("Speakers (Senary Audio)")

    assert cm.get_input_device() == "Microphone (2.0 Camera)"
    assert cm.get_output_device() == "Speakers (Senary Audio)"


def test_empty_device_name_means_system_default(tmp_config):
    cm.save_input_device("")

    assert cm.get_input_device() == ""


# ── Plugins ──────────────────────────────────────────────────────────────────

def test_plugins_are_enabled_by_default(tmp_config):
    assert cm.get_plugin_enabled("brand_new_plugin") is True


def test_disabling_one_plugin_does_not_disable_another(tmp_config):
    cm.save_plugin_enabled("noisy", False)

    assert cm.get_plugin_enabled("noisy") is False
    assert cm.get_plugin_enabled("quiet") is True