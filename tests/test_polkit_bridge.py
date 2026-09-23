"""Tests for src.permissions.polkit_bridge."""

from __future__ import annotations

from src.permissions.polkit_bridge import is_polkit_available, run_privileged


class TestPolkitAvailability:
    def test_is_polkit_available_returns_bool(self) -> None:
        assert isinstance(is_polkit_available(), bool)


class TestRunPrivilegedWithoutPolkit:
    def test_missing_pkexec_returns_clean_failure(self, monkeypatch) -> None:
        import src.permissions.polkit_bridge as bridge_module

        monkeypatch.setattr(bridge_module, "is_polkit_available", lambda: False)
        result = bridge_module.run_privileged(["systemctl", "start", "sshd.service"])
        assert result.success is False
        assert result.returncode == 127
