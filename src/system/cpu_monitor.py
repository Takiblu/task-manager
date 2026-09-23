"""
CPU monitoring: total/per-core usage, frequency, temperature (best
effort via psutil sensors), load average, core/thread counts, and a
best-effort CPU model string parsed from /proc/cpuinfo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from src.utils.logger import get_logger

logger = get_logger("system.cpu_monitor")


@dataclass
class CpuSnapshot:
    total_percent: float
    per_core_percent: list[float] = field(default_factory=list)
    current_freq_mhz: float | None = None
    max_freq_mhz: float | None = None
    temperature_c: float | None = None
    load_avg_1: float = 0.0
    load_avg_5: float = 0.0
    load_avg_15: float = 0.0
    physical_cores: int = 0
    logical_cores: int = 0
    model_name: str = "Unknown CPU"
    architecture: str = "unknown"


_cached_model_name: str | None = None


def _read_cpu_model_name() -> str:
    """Parse the CPU model string from /proc/cpuinfo (cached)."""
    global _cached_model_name
    if _cached_model_name is not None:
        return _cached_model_name

    path = Path("/proc/cpuinfo")
    model = "Unknown CPU"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.lower().startswith("model name"):
                _, _, value = line.partition(":")
                model = value.strip()
                break
    except OSError as exc:
        logger.debug("Could not read /proc/cpuinfo: %s", exc)

    _cached_model_name = model
    return model


def _read_temperature_c() -> float | None:
    """
    Best-effort CPU package temperature via psutil.sensors_temperatures().
    Different kernels/drivers expose different sensor label names, so we
    try a list of common candidates and fall back to the first available
    sensor group if none match.
    """
    try:
        sensors = psutil.sensors_temperatures()
    except (AttributeError, OSError) as exc:
        logger.debug("sensors_temperatures unavailable: %s", exc)
        return None

    if not sensors:
        return None

    preferred_groups = ("coretemp", "k10temp", "zenpower", "cpu_thermal")
    for group_name in preferred_groups:
        entries = sensors.get(group_name)
        if entries:
            for entry in entries:
                if entry.label.lower() in ("package id 0", "tctl", "tdie", ""):
                    return entry.current
            return entries[0].current

    # Fall back to the first sensor group available at all.
    for entries in sensors.values():
        if entries:
            return entries[0].current
    return None


def get_cpu_snapshot() -> CpuSnapshot:
    """
    Take one CPU measurement. Note: percent=True calls should use a
    non-blocking sample (interval=None) here because the polling
    worker thread already spaces calls apart by the configured
    update interval — calling with a blocking interval here would
    stack up sleeps across every metric we collect per tick.
    """
    total_percent = psutil.cpu_percent(interval=None)
    per_core = psutil.cpu_percent(interval=None, percpu=True)

    current_freq_mhz = None
    max_freq_mhz = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            current_freq_mhz = freq.current
            max_freq_mhz = freq.max or None
    except (FileNotFoundError, OSError) as exc:
        logger.debug("cpu_freq unavailable: %s", exc)

    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = 0.0

    return CpuSnapshot(
        total_percent=total_percent,
        per_core_percent=per_core,
        current_freq_mhz=current_freq_mhz,
        max_freq_mhz=max_freq_mhz,
        temperature_c=_read_temperature_c(),
        load_avg_1=load1,
        load_avg_5=load5,
        load_avg_15=load15,
        physical_cores=psutil.cpu_count(logical=False) or 0,
        logical_cores=psutil.cpu_count(logical=True) or 0,
        model_name=_read_cpu_model_name(),
        architecture=os.uname().machine,
    )
