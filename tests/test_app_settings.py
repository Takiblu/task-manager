"""Tests for src.settings.app_settings — persistence and clamping of untrusted values."""

from __future__ import annotations

import json

import pytest

from src.settings.app_settings import (
    MAX_UPDATE_INTERVAL_MS,
    MIN_UPDATE_INTERVAL_MS,
    AppSettings,
)


class TestAppSettingsDefaults:
    def test_defaults_are_valid(self) -> None:
        settings = AppSettings()
        settings.clamp()
        assert settings.theme in ("dark", "light", "system")
        assert MIN_UPDATE_INTERVAL_MS <= settings.update_interval_ms <= MAX_UPDATE_INTERVAL_MS


class TestAppSettingsClamping:
    def test_invalid_theme_falls_back_to_system(self) -> None:
        settings = AppSettings(theme="not-a-real-theme")
        settings.clamp()
        assert settings.theme == "system"

    def test_update_interval_clamped_to_minimum(self) -> None:
        settings = AppSettings(update_interval_ms=1)
        settings.clamp()
        assert settings.update_interval_ms == MIN_UPDATE_INTERVAL_MS

    def test_update_interval_clamped_to_maximum(self) -> None:
        settings = AppSettings(update_interval_ms=999999)
        settings.clamp()
        assert settings.update_interval_ms == MAX_UPDATE_INTERVAL_MS

    def test_chart_history_clamped(self) -> None:
        settings = AppSettings(chart_history_points=1)
        settings.clamp()
        assert settings.chart_history_points >= 30


class TestAppSettingsRoundTrip:
    def test_to_dict_from_dict_round_trip(self) -> None:
        original = AppSettings(theme="dark", update_interval_ms=1500, confirm_end_task=False)
        restored = AppSettings.from_dict(original.to_dict())
        assert restored.theme == "dark"
        assert restored.update_interval_ms == 1500
        assert restored.confirm_end_task is False

    def test_from_dict_ignores_unknown_fields(self) -> None:
        data = AppSettings().to_dict()
        data["some_future_field_we_dont_know_about"] = "value"
        # Must not raise TypeError for unexpected keys.
        restored = AppSettings.from_dict(data)
        assert isinstance(restored, AppSettings)

    def test_from_dict_handles_missing_fields(self) -> None:
        restored = AppSettings.from_dict({"theme": "light"})
        assert restored.theme == "light"
        assert restored.update_interval_ms == AppSettings().update_interval_ms

    def test_is_json_serializable(self) -> None:
        settings = AppSettings()
        # Must not raise.
        json.dumps(settings.to_dict())


class TestSettingsFilePersistence:
    def test_save_and_load_round_trip(self, tmp_path, monkeypatch) -> None:
        import src.settings.app_settings as app_settings_module

        fake_config_dir = tmp_path / "manjaro-task-manager"
        monkeypatch.setattr(
            app_settings_module, "get_config_path",
            lambda: fake_config_dir / "settings.json",
        )
        fake_config_dir.mkdir(parents=True, exist_ok=True)

        settings = AppSettings(theme="light", update_interval_ms=2000)
        assert app_settings_module.save_settings(settings) is True

        loaded = app_settings_module.load_settings()
        assert loaded.theme == "light"
        assert loaded.update_interval_ms == 2000

    def test_load_with_corrupt_json_falls_back_to_defaults(self, tmp_path, monkeypatch) -> None:
        import src.settings.app_settings as app_settings_module

        config_path = tmp_path / "settings.json"
        config_path.write_text("{ this is not valid json ", encoding="utf-8")
        monkeypatch.setattr(app_settings_module, "get_config_path", lambda: config_path)

        loaded = app_settings_module.load_settings()
        assert loaded.theme == AppSettings().theme
