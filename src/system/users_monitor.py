"""Active user sessions (section 17), aggregated from psutil.users() + process ownership."""

from __future__ import annotations

from dataclasses import dataclass

import psutil

from src.utils.logger import get_logger

logger = get_logger("system.users_monitor")


@dataclass
class UserSession:
    username: str
    terminal: str
    login_time: float
    process_count: int
    cpu_percent: float
    ram_percent: float


def list_user_sessions() -> list[UserSession]:
    try:
        raw_sessions = psutil.users()
    except OSError as exc:
        logger.warning("Failed to read user sessions: %s", exc)
        return []

    # Aggregate process CPU/RAM/count per username in a single pass
    # over process_iter rather than once per session.
    per_user_cpu: dict[str, float] = {}
    per_user_ram: dict[str, float] = {}
    per_user_count: dict[str, int] = {}

    for proc in psutil.process_iter(attrs=["username", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            username = info.get("username")
            if not username:
                continue
            per_user_cpu[username] = per_user_cpu.get(username, 0.0) + (info.get("cpu_percent") or 0.0)
            per_user_ram[username] = per_user_ram.get(username, 0.0) + (info.get("memory_percent") or 0.0)
            per_user_count[username] = per_user_count.get(username, 0) + 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    sessions: list[UserSession] = []
    for raw in raw_sessions:
        sessions.append(
            UserSession(
                username=raw.name,
                terminal=raw.terminal or "N/A",
                login_time=raw.started,
                process_count=per_user_count.get(raw.name, 0),
                cpu_percent=per_user_cpu.get(raw.name, 0.0),
                ram_percent=per_user_ram.get(raw.name, 0.0),
            )
        )
    return sessions
