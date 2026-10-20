import logging
import os
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from PyQt5 import QtCore


class SuppressingLogger:
    """Coalesce identical noisy messages and periodically report repetitions."""

    def __init__(self, logger: logging.Logger, interval_sec: float = 30.0):
        self.logger = logger
        self.interval_sec = interval_sec
        self._last: Dict[str, Tuple[float, int]] = {}

    def record(self, message: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        previous_at, suppressed = self._last.get(message, (-1e9, 0))
        if now - previous_at < self.interval_sec:
            self._last[message] = (previous_at, suppressed + 1)
            return False
        if suppressed:
            self.logger.info("Suppressed %d repeated subprocess messages", suppressed)
        self.logger.info("%s", message)
        self._last[message] = (now, 0)
        return True

    def flush(self) -> None:
        for _message, (_at, suppressed) in list(self._last.items()):
            if suppressed:
                self.logger.info("Suppressed %d repeated subprocess messages", suppressed)
        self._last.clear()


class ResourceSampler(QtCore.QObject):
    """Low-cost /proc sampling written only to the rotating diagnostic log."""

    updated = QtCore.pyqtSignal(dict)

    def __init__(self, process_provider: Callable[[], Iterable[Tuple[str, int]]], parent=None):
        super().__init__(parent)
        self._process_provider = process_provider
        self._logger = logging.getLogger("resources")
        self._previous_cpu: Dict[int, Tuple[float, float]] = {}
        self._clock_ticks = float(os.sysconf("SC_CLK_TCK"))
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.sample)

    def start(self) -> None:
        self._timer.start()

    def sample(self) -> None:
        processes: List[Tuple[str, int]] = [("OMNILink", os.getpid())]
        processes.extend(self._process_provider())
        live = []
        now = time.monotonic()
        for name, pid in processes:
            if not pid:
                continue
            try:
                statm = (Path("/proc") / str(pid) / "statm").read_text().split()
                rss_mb = int(statm[1]) * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
                stat = (Path("/proc") / str(pid) / "stat").read_text().split()
                cpu_ticks = float(stat[13]) + float(stat[14])
                previous = self._previous_cpu.get(pid)
                cpu_text = "n/a"
                if previous and now > previous[0]:
                    cpu = (cpu_ticks - previous[1]) / self._clock_ticks / (now - previous[0]) * 100
                    cpu_text = f"{max(0.0, cpu):.1f}%"
                self._previous_cpu[pid] = (now, cpu_ticks)
                live.append(f"{name}[{pid}] cpu={cpu_text} rss={rss_mb:.1f}MB")
            except (OSError, ValueError, IndexError):
                continue
        self._logger.info("processes=%d | %s", max(0, len(live) - 1), " | ".join(live))
        self.updated.emit(
            {
                "process_count": max(0, len(live) - 1),
                "summary": " | ".join(live) if live else "No live processes",
            }
        )
        active_pids = {pid for _name, pid in processes if pid}
        self._previous_cpu = {
            pid: sample for pid, sample in self._previous_cpu.items() if pid in active_pids
        }


class TrafficSampler(QtCore.QObject):
    """Estimate live service throughput from Linux per-process I/O counters."""

    updated = QtCore.pyqtSignal(dict)

    def __init__(
        self,
        video_provider: Callable,
        telemetry_provider: Callable,
        parent=None,
        video_bytes_provider: Optional[Callable[[], int]] = None,
    ):
        super().__init__(parent)
        self._providers = {"video": video_provider, "telemetry": telemetry_provider}
        self._previous: Dict[int, int] = {}
        self._totals = {"video": 0, "telemetry": 0}
        self._video_bytes_provider = video_bytes_provider
        self._last_video_bytes: Optional[int] = None
        self._last_sample = time.monotonic()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.sample)

    def start(self) -> None:
        self._last_sample = time.monotonic()
        self._timer.start()

    @staticmethod
    def _read_process_io(pid: int) -> Optional[int]:
        try:
            values = {}
            for line in (Path("/proc") / str(pid) / "io").read_text().splitlines():
                key, _separator, value = line.partition(":")
                if value.strip().isdigit():
                    values[key] = int(value.strip())
            # rchar/wchar count bytes returned by read/write-family syscalls. They
            # include protocol and logging overhead, so the UI labels this an estimate.
            return values.get("rchar", 0) + values.get("wchar", 0)
        except (OSError, ValueError):
            return None

    def sample(self) -> None:
        now = time.monotonic()
        elapsed = max(0.001, now - self._last_sample)
        self._last_sample = now
        rates = {"video": 0.0, "telemetry": 0.0}
        active_pids = set()
        process_count = 0

        for service, provider in self._providers.items():
            for _name, pid in provider():
                if not pid:
                    continue
                current = self._read_process_io(pid)
                if current is None:
                    continue
                process_count += 1
                active_pids.add(pid)
                previous = self._previous.get(pid)
                self._previous[pid] = current
                if previous is None or current < previous:
                    continue
                delta = current - previous
                if service != "video" or self._video_bytes_provider is None:
                    self._totals[service] += delta
                    rates[service] += delta / elapsed

        if self._video_bytes_provider is not None:
            video_bytes = max(0, int(self._video_bytes_provider()))
            if self._last_video_bytes is not None:
                delta = (
                    video_bytes
                    if video_bytes < self._last_video_bytes
                    else video_bytes - self._last_video_bytes
                )
                self._totals["video"] += delta
                rates["video"] = delta / elapsed
            self._last_video_bytes = video_bytes

        self._previous = {pid: value for pid, value in self._previous.items() if pid in active_pids}
        self.updated.emit(
            {
                "video_bytes_per_sec": rates["video"],
                "telemetry_bytes_per_sec": rates["telemetry"],
                "video_total_bytes": self._totals["video"],
                "telemetry_total_bytes": self._totals["telemetry"],
                "process_count": process_count,
            }
        )
