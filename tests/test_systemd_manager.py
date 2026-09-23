"""
Tests for src.services.systemd_manager.

The parsing/validation logic is tested directly; the actual systemctl
calls are exercised only for "does this raise" safety (they're
allowed to fail gracefully on a CI box without systemd services to
manage — the point is that a failure never becomes an exception).
"""

from __future__ import annotations

import pytest

from src.services.systemd_manager import (
    ServiceActionOutcome,
    _run_systemctl_action,
    _validate_unit_name,
    list_services,
)


class TestValidateUnitName:
    def test_appends_service_suffix(self) -> None:
        assert _validate_unit_name("sshd") == "sshd.service"

    def test_leaves_existing_suffix_untouched(self) -> None:
        assert _validate_unit_name("sshd.service") == "sshd.service"

    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValueError):
            _validate_unit_name("../../etc/passwd")

    def test_rejects_slash(self) -> None:
        with pytest.raises(ValueError):
            _validate_unit_name("foo/bar")

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValueError):
            _validate_unit_name("")

    def test_rejects_null_byte(self) -> None:
        with pytest.raises(ValueError):
            _validate_unit_name("sshd\x00.service")


class TestListServices:
    def test_does_not_raise_and_returns_list(self) -> None:
        # On a real systemd system this returns real services; in a
        # minimal container it may return an empty list — either way
        # it must never raise.
        services = list_services(user_scope=False)
        assert isinstance(services, list)

    def test_service_info_shape(self) -> None:
        services = list_services(user_scope=False)
        if not services:
            pytest.skip("No systemd services visible in this environment")
        sample = services[0]
        assert sample.name.endswith(".service")
        assert isinstance(sample.is_active, bool)
        assert isinstance(sample.is_failed, bool)


class TestServiceActionOnNonexistentUnit:
    def test_action_on_bogus_unit_reports_not_found_or_failed(self) -> None:
        result = _run_systemctl_action(
            "start", "definitely-not-a-real-service-xyz123", user_scope=False,
            allow_privileged_retry=False,
        )
        assert result.outcome in (
            ServiceActionOutcome.NOT_FOUND,
            ServiceActionOutcome.FAILED,
            ServiceActionOutcome.PERMISSION_DENIED,
        )
