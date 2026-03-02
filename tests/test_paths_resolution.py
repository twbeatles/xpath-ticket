from pathlib import Path

from xpath_explorer.core import paths


def test_resolve_storage_dir_prefers_home(monkeypatch, tmp_path):
    home_base = tmp_path / "home"
    temp_base = tmp_path / "temp"
    monkeypatch.setattr(paths.Path, "home", staticmethod(lambda: home_base))
    monkeypatch.setattr(paths.tempfile, "gettempdir", lambda: str(temp_base))

    resolved, source = paths.resolve_storage_dir()

    assert source == "home"
    assert resolved == home_base / paths.APP_STORAGE_DIRNAME
    assert resolved is not None and resolved.exists()


def test_resolve_storage_dir_falls_back_to_temp(monkeypatch, tmp_path):
    home_base = tmp_path / "home"
    temp_base = tmp_path / "temp"
    home_target = home_base / paths.APP_STORAGE_DIRNAME
    original_mkdir = paths.Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self == home_target:
            raise OSError("home readonly")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(paths.Path, "home", staticmethod(lambda: home_base))
    monkeypatch.setattr(paths.tempfile, "gettempdir", lambda: str(temp_base))
    monkeypatch.setattr(paths.Path, "mkdir", fake_mkdir)

    resolved, source = paths.resolve_storage_dir()

    assert source == "temp"
    assert resolved == temp_base / paths.APP_STORAGE_DIRNAME
    assert resolved is not None and resolved.exists()


def test_resolve_storage_dir_returns_memory_when_all_candidates_fail(monkeypatch, tmp_path):
    home_base = tmp_path / "home"
    temp_base = tmp_path / "temp"

    def always_fail(*_args, **_kwargs):
        raise OSError("readonly")

    monkeypatch.setattr(paths.Path, "home", staticmethod(lambda: home_base))
    monkeypatch.setattr(paths.tempfile, "gettempdir", lambda: str(temp_base))
    monkeypatch.setattr(paths.Path, "mkdir", always_fail)

    resolved, source = paths.resolve_storage_dir()

    assert resolved is None
    assert source == "memory"

