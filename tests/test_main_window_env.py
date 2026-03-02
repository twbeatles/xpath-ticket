import os

from xpath_explorer.main_window import configure_qt_env


def test_configure_qt_env_sets_auto_scale_factor(monkeypatch):
    monkeypatch.delenv("QT_AUTO_SCREEN_SCALE_FACTOR", raising=False)

    configure_qt_env()

    assert os.environ.get("QT_AUTO_SCREEN_SCALE_FACTOR") == "1"

