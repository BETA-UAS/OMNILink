from core.diagnostics import TrafficSampler
from PyQt5 import QtCore
from ui.components.diagnostics_panel import DiagnosticsPanel


def ensure_app():
    return QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])


def test_traffic_sampler_reports_per_service_rates_and_totals(monkeypatch):
    ensure_app()
    sampler = TrafficSampler(
        lambda: [("FFmpeg:cam1", 1)],
        lambda: [("MAVLink Router", 2)],
    )
    values = {1: 100, 2: 200}
    now = [1.0]
    monkeypatch.setattr("core.diagnostics.time.monotonic", lambda: now[0])
    monkeypatch.setattr(sampler, "_read_process_io", lambda pid: values[pid])
    sampler._last_sample = 0.0
    updates = []
    sampler.updated.connect(updates.append)

    sampler.sample()
    values.update({1: 1124, 2: 2248})
    now[0] = 2.0
    sampler.sample()

    assert updates[-1]["video_bytes_per_sec"] == 1024
    assert updates[-1]["telemetry_bytes_per_sec"] == 2048
    assert updates[-1]["video_total_bytes"] == 1024
    assert updates[-1]["telemetry_total_bytes"] == 2048
    assert updates[-1]["process_count"] == 2


def test_traffic_units_are_readable():
    assert DiagnosticsPanel._format_rate(1536) == "1.5 KB/s"
    assert DiagnosticsPanel._format_bytes(2 * 1024 * 1024) == "2.0 MB"


def test_video_payload_counter_overrides_process_io_estimate(monkeypatch):
    ensure_app()
    published = [1000]
    sampler = TrafficSampler(
        lambda: [("FFmpeg:cam1", 1)],
        lambda: [],
        video_bytes_provider=lambda: published[0],
    )
    monkeypatch.setattr(sampler, "_read_process_io", lambda _pid: 999999)
    sampler._last_sample = 0.0
    sampler._last_video_bytes = 0
    monkeypatch.setattr("core.diagnostics.time.monotonic", lambda: 1.0)
    updates = []
    sampler.updated.connect(updates.append)
    sampler.sample()
    assert updates[-1]["video_bytes_per_sec"] == 1000
    assert updates[-1]["video_total_bytes"] == 1000
