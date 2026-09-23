"""
Detects the runtime Linux environment: distribution, kernel, display
server (X11/Wayland), desktop environment, and window manager.

All detection here is best-effort and must never raise — every reader
degrades gracefully to "Unknown" so the rest of the app can render
System Information / Overview without special-casing failures.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("utils.platform_info")


@dataclass(frozen=True)
class SystemIdentity:
    distribution: str
    distribution_version: str
    kernel: str
    architecture: str
    hostname: str
    desktop_environment: str
    window_manager: str
    display_server: str  # "Wayland", "X11", or "Unknown"


def _read_os_release() -> dict:
    """Parse /etc/os-release into a dict. Never raises."""
    data: dict = {}
    path = Path("/etc/os-release")
    try:
        if not path.exists():
            return data
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip().strip('"')
    except OSError as exc:
        logger.debug("Failed reading /etc/os-release: %s", exc)
    return data


def detect_distribution() -> tuple[str, str]:
    """Return (pretty_name, version_id) for the running distribution."""
    data = _read_os_release()
    name = data.get("PRETTY_NAME") or data.get("NAME") or "Unknown Linux"
    version = data.get("VERSION_ID") or data.get("BUILD_ID") or "Rolling"
    return name, version


def detect_display_server() -> str:
    """
    Determine whether the session is running under Wayland or X11.

    Detection order:
      1. WAYLAND_DISPLAY env var -> Wayland
      2. XDG_SESSION_TYPE env var -> trust it if set
      3. DISPLAY env var without WAYLAND_DISPLAY -> X11
      4. Unknown
    """
    if os.environ.get("WAYLAND_DISPLAY"):
        return "Wayland"

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        return "Wayland"
    if session_type == "x11":
        return "X11"

    if os.environ.get("DISPLAY"):
        return "X11"

    return "Unknown"


def detect_desktop_environment() -> str:
    """Best-effort desktop environment name."""
    candidates = [
        os.environ.get("XDG_CURRENT_DESKTOP"),
        os.environ.get("XDG_SESSION_DESKTOP"),
        os.environ.get("DESKTOP_SESSION"),
    ]
    for candidate in candidates:
        if candidate:
            # XDG_CURRENT_DESKTOP can be colon-separated, e.g. "KDE:GNOME"
            return candidate.split(":")[0]
    return "Unknown"


def detect_window_manager() -> str:
    """
    Best-effort window manager detection via wmctrl, falling back to
    process-name heuristics for common WMs if wmctrl is unavailable.
    """
    if shutil.which("wmctrl"):
        try:
            result = subprocess.run(
                ["wmctrl", "-m"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            for line in result.stdout.splitlines():
                if line.lower().startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                    if name:
                        return name
        except (subprocess.SubprocessError, OSError) as exc:
            logger.debug("wmctrl detection failed: %s", exc)

    # Fallback: inspect common WM/compositor process names.
    known_wms = (
        "kwin_wayland", "kwin_x11", "mutter", "gnome-shell",
        "sway", "hyprland", "xfwm4", "i3", "bspwm", "openbox",
        "awesome", "dwm", "qtile",
    )
    try:
        import psutil  # local import to avoid a hard dependency at module load

        running = {p.name() for p in psutil.process_iter(["name"])}
        for wm in known_wms:
            if wm in running:
                return wm
    except Exception as exc:  # noqa: BLE001 - detection must never crash startup
        logger.debug("Process-based WM detection failed: %s", exc)

    return "Unknown"


def get_system_identity() -> SystemIdentity:
    """Gather a full snapshot of system identity information."""
    distro_name, distro_version = detect_distribution()
    try:
        hostname = platform.node() or "localhost"
    except Exception:  # noqa: BLE001
        hostname = "localhost"

    return SystemIdentity(
        distribution=distro_name,
        distribution_version=distro_version,
        kernel=platform.release(),
        architecture=platform.machine(),
        hostname=hostname,
        desktop_environment=detect_desktop_environment(),
        window_manager=detect_window_manager(),
        display_server=detect_display_server(),
    )


def is_arch_based() -> bool:
    """True if /etc/arch-release exists or os-release ID_LIKE mentions arch."""
    if Path("/etc/arch-release").exists():
        return True
    data = _read_os_release()
    id_like = data.get("ID_LIKE", "")
    identifier = data.get("ID", "")
    return "arch" in id_like.lower() or "arch" in identifier.lower()
