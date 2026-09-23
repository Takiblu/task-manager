"""
GPU monitoring across NVIDIA, AMD, and Intel, done entirely without
proprietary Python bindings so the app has no hard GPU-vendor
dependency at import time:

  * NVIDIA  -> `nvidia-smi --query-gpu=... --format=csv` (if present)
  * AMD     -> sysfs under /sys/class/drm/card*/device/ (amdgpu)
  * Intel   -> sysfs under /sys/class/drm/card*/device/ (i915), usage
               is not reliably exposed there so we report what's
               available (frequency) and mark usage as unavailable.

If no GPU can be read, `get_gpu_snapshots()` returns an empty list and
the UI is expected to show "GPU: Not Available" rather than an error.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.utils.logger import get_logger
from src.utils.safe_exec import run_argv

logger = get_logger("system.gpu_monitor")


@dataclass
class GpuSnapshot:
    name: str
    vendor: str  # "NVIDIA" | "AMD" | "Intel" | "Unknown"
    usage_percent: float | None
    vram_used_mb: float | None
    vram_total_mb: float | None
    temperature_c: float | None
    power_watts: float | None
    frequency_mhz: float | None


def _read_sysfs_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _get_nvidia_snapshots() -> list[GpuSnapshot]:
    if not shutil.which("nvidia-smi"):
        return []

    query = (
        "name,utilization.gpu,memory.used,memory.total,"
        "temperature.gpu,power.draw,clocks.current.graphics"
    )
    result = run_argv(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        timeout=3.0,
    )
    if not result.success:
        logger.debug("nvidia-smi query failed: %s", result.stderr.strip())
        return []

    snapshots: list[GpuSnapshot] = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 7:
            continue
        name, util, mem_used, mem_total, temp, power, freq = parts

        def to_float(value: str) -> float | None:
            try:
                return float(value)
            except ValueError:
                return None

        snapshots.append(
            GpuSnapshot(
                name=name,
                vendor="NVIDIA",
                usage_percent=to_float(util),
                vram_used_mb=to_float(mem_used),
                vram_total_mb=to_float(mem_total),
                temperature_c=to_float(temp),
                power_watts=to_float(power),
                frequency_mhz=to_float(freq),
            )
        )
    return snapshots


def _get_amd_intel_snapshots() -> list[GpuSnapshot]:
    """
    Read AMD (amdgpu) / Intel (i915) info from sysfs. NVIDIA cards
    also expose a DRM node but are skipped here since nvidia-smi
    (above) is the authoritative source when available.
    """
    snapshots: list[GpuSnapshot] = []
    drm_root = Path("/sys/class/drm")
    if not drm_root.exists():
        return snapshots

    seen_devices: set[str] = set()

    for card_dir in sorted(drm_root.glob("card[0-9]*")):
        device_dir = card_dir / "device"
        if not device_dir.exists() or str(device_dir) in seen_devices:
            continue

        vendor_id = (device_dir / "vendor").read_text(encoding="utf-8").strip() \
            if (device_dir / "vendor").exists() else ""

        if vendor_id == "0x1002":
            vendor = "AMD"
        elif vendor_id == "0x8086":
            vendor = "Intel"
        elif vendor_id == "0x10de":
            # NVIDIA is handled by nvidia-smi; avoid double-reporting.
            continue
        else:
            continue

        seen_devices.add(str(device_dir))

        usage_percent = None
        gpu_busy_path = device_dir / "gpu_busy_percent"
        if gpu_busy_path.exists():
            usage_percent = _read_sysfs_int(gpu_busy_path)

        vram_used_mb = None
        vram_total_mb = None
        mem_used_path = device_dir / "mem_info_vram_used"
        mem_total_path = device_dir / "mem_info_vram_total"
        if mem_used_path.exists():
            used_bytes = _read_sysfs_int(mem_used_path)
            vram_used_mb = used_bytes / (1024 * 1024) if used_bytes is not None else None
        if mem_total_path.exists():
            total_bytes = _read_sysfs_int(mem_total_path)
            vram_total_mb = total_bytes / (1024 * 1024) if total_bytes is not None else None

        # Try to get a human-readable product name; fall back to vendor.
        name = vendor
        uevent_path = device_dir / "uevent"
        if uevent_path.exists():
            try:
                for line in uevent_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("DRIVER="):
                        name = f"{vendor} ({line.split('=', 1)[1].strip()})"
                        break
            except OSError:
                pass

        snapshots.append(
            GpuSnapshot(
                name=name,
                vendor=vendor,
                usage_percent=float(usage_percent) if usage_percent is not None else None,
                vram_used_mb=vram_used_mb,
                vram_total_mb=vram_total_mb,
                temperature_c=None,  # hwmon lookup is driver-specific; omitted for reliability
                power_watts=None,
                frequency_mhz=None,
            )
        )

    return snapshots


def get_gpu_snapshots() -> list[GpuSnapshot]:
    """
    Return snapshots for every detected GPU. Order: NVIDIA first (most
    reliable data via nvidia-smi), then AMD/Intel via sysfs.
    Never raises — GPU absence/unsupported hardware just yields [].
    """
    snapshots: list[GpuSnapshot] = []
    try:
        snapshots.extend(_get_nvidia_snapshots())
    except Exception as exc:  # noqa: BLE001
        logger.debug("NVIDIA GPU detection failed: %s", exc)

    try:
        snapshots.extend(_get_amd_intel_snapshots())
    except Exception as exc:  # noqa: BLE001
        logger.debug("AMD/Intel GPU detection failed: %s", exc)

    return snapshots
