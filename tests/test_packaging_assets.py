import subprocess
from pathlib import Path

from PyQt5 import QtGui, QtWidgets
from ui.components import toolbar

ROOT = Path(__file__).resolve().parents[1]


def test_logo_asset_loads_from_source():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = toolbar.logo_asset_path()
    assert path == ROOT / "ui" / "assets" / "betawhite.png"
    assert not QtGui.QPixmap(str(path)).isNull()
    assert app is not None


def test_logo_asset_uses_pyinstaller_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(toolbar.sys, "frozen", True, raising=False)
    monkeypatch.setattr(toolbar.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert toolbar.logo_asset_path() == tmp_path / "ui" / "assets" / "betawhite.png"


def test_generated_screenshots_are_ignored_but_ui_assets_are_not():
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "artifacts/example.png"], cwd=ROOT, check=False
    )
    asset = subprocess.run(
        ["git", "check-ignore", "-q", "ui/assets/new-logo.png"], cwd=ROOT, check=False
    )
    assert ignored.returncode == 0
    assert asset.returncode == 1
