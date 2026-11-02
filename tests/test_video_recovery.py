import logging

from core.diagnostics import SuppressingLogger
from core.video_config import MAIN_CAMERA_URLS
from core.video_manager import VideoManager
from PyQt5 import QtCore


class FakeProcess:
    def __init__(self, state=QtCore.QProcess.Running):
        self._state = state

    def state(self):
        return self._state


def ensure_app():
    return QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])


def publisher_record(process, started_at=0.0, last_progress=None):
    return {
        "source": None,
        "process": process,
        "retry_timer": None,
        "retry_index": 0,
        "state": "streaming",
        "last_progress": last_progress,
        "started_at": started_at,
        "stable_since": None,
        "buffer": "",
    }


def test_stalled_camera_is_restarted_without_touching_other_camera(monkeypatch):
    ensure_app()
    manager = VideoManager()
    stalled = FakeProcess()
    healthy = FakeProcess()
    manager._publishers = {
        "cam1": publisher_record(stalled, started_at=1.0, last_progress=2.0),
        "cam2": publisher_record(healthy, started_at=1.0, last_progress=99.0),
    }
    terminated = []
    monkeypatch.setattr("core.video_manager.time.monotonic", lambda: 100.0)
    monkeypatch.setattr(manager, "_terminate_process", lambda process: terminated.append(process))
    manager._watch()
    assert terminated == [stalled]
    assert manager._publishers["cam1"]["state"] == "waiting"
    assert manager._publishers["cam2"]["state"] == "streaming"


def test_stale_session_callback_cannot_start_publisher(monkeypatch):
    ensure_app()
    manager = VideoManager()
    manager._session = 8
    manager._publishers = {"cam1": publisher_record(None)}
    monkeypatch.setattr(manager, "is_running", lambda: True)
    manager._start_publisher("cam1", 7)
    assert manager._publishers["cam1"]["process"] is None


def test_stop_cancels_pending_retry_timer():
    ensure_app()
    manager = VideoManager()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.start(30000)
    manager._publishers = {"cam1": publisher_record(None)}
    manager._publishers["cam1"]["retry_timer"] = timer
    manager.stop()
    assert not timer.isActive()
    assert manager._publishers == {}


def test_only_one_pending_retry_is_created_per_camera():
    ensure_app()
    manager = VideoManager()
    manager._publishers = {"cam1": publisher_record(None)}
    manager._schedule_retry("cam1", manager._session)
    first_timer = manager._publishers["cam1"]["retry_timer"]
    manager._schedule_retry("cam1", manager._session)
    assert manager._publishers["cam1"]["retry_timer"] is first_timer
    first_timer.stop()


def test_main_camera_tries_viewpro_after_mt11_then_retries(monkeypatch):
    app = ensure_app()
    manager = VideoManager()
    manager._session = 1
    starts = []
    retries = []
    monkeypatch.setattr(
        manager, "_start_publisher", lambda path, session: starts.append((path, session))
    )
    monkeypatch.setattr(
        manager, "_schedule_retry", lambda path, session: retries.append((path, session))
    )

    first = QtCore.QProcess()
    record = publisher_record(first)
    record.update(source_urls=MAIN_CAMERA_URLS, source_index=0)
    manager._publishers = {"cam1": record}
    manager._publisher_finished("cam1", 1, first, 1, None)
    app.processEvents()

    assert record["source_index"] == 1
    assert starts == [("cam1", 1)]
    assert retries == []
    assert record["process"] is None

    second = QtCore.QProcess()
    record["process"] = second
    manager._publisher_finished("cam1", 1, second, 1, None)
    app.processEvents()

    assert record["source_index"] == 0
    assert starts == [("cam1", 1)]
    assert retries == [("cam1", 1)]


def test_delayed_kill_ignores_process_already_deleted():
    class DeletedProcess:
        def state(self):
            raise RuntimeError("wrapped object deleted")

    VideoManager._safe_kill(DeletedProcess())


def test_repeated_log_messages_are_suppressed_and_reported(caplog):
    logger = logging.getLogger("test.suppression")
    limiter = SuppressingLogger(logger, interval_sec=10)
    with caplog.at_level(logging.INFO):
        assert limiter.record("same", now=0)
        assert not limiter.record("same", now=1)
        assert not limiter.record("same", now=2)
        assert limiter.record("same", now=11)
    assert "Suppressed 2 repeated subprocess messages" in caplog.text
