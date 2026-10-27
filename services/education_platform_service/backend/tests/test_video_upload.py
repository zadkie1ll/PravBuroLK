import io
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Course, Module
from app.services import file_streaming, video_import


def test_upload_reads_only_bounded_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(file_streaming.settings, "media_root", str(tmp_path))
    class BoundedFile(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024
            return super().read(size)
    content = b"a" * (3 * 1024 * 1024 + 17)
    upload = SimpleNamespace(filename="../../lesson.mp4", file=BoundedFile(content))
    relative = file_streaming.save_upload(upload, "education/video_sources")
    assert (tmp_path / relative).read_bytes() == content
    assert Path(relative).name.endswith("_lesson.mp4")
    assert not list(tmp_path.rglob("*.part"))


def test_upload_failure_removes_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(file_streaming.settings, "media_root", str(tmp_path))
    class BrokenFile:
        count = 0
        def read(self, size):
            self.count += 1
            if self.count == 1:
                return b"partial"
            raise OSError("disk/network failure")
    with pytest.raises(OSError):
        file_streaming.save_upload(SimpleNamespace(filename="lesson.mp4", file=BrokenFile()), "education/video_sources")
    assert not list((tmp_path / "education/video_sources").iterdir())


@pytest.fixture
def queue(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(video_import, "SessionLocal", sessions)
    monkeypatch.setattr(video_import.settings, "media_root", str(tmp_path))
    source = tmp_path / "education/video_sources/lesson.mov"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"uploaded source")
    with sessions() as db:
        course = Course(name="Course")
        db.add(course)
        db.flush()
        module = Module(course_id=course.id, name="Lesson", video_url="", private_video="old.mp4",
                        video_import_source=str(source.relative_to(tmp_path)), video_import_status="queued")
        db.add(module)
        db.commit()
        module_id = module.id
    yield sessions, module_id, source
    engine.dispose()


def test_uploaded_video_converts_after_save_without_download(queue, tmp_path, monkeypatch):
    sessions, module_id, source = queue
    monkeypatch.setattr(video_import.subprocess, "check_output", Mock(side_effect=AssertionError("no Yandex download")))
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        if command[-1].endswith(".mp4"):
            # Conversion starts only after the completed source exists.
            assert source.read_bytes() == b"uploaded source"
            Path(command[-1]).write_bytes(b"converted output")
    monkeypatch.setattr(video_import.subprocess, "run", run)
    video_import.process_next()
    with sessions() as db:
        module = db.get(Module, module_id)
        assert module.video_import_status == "ready"
        assert module.video_import_source == ""
        assert (tmp_path / module.private_video).read_bytes() == b"converted output"
    assert len(commands) == 2
    assert not source.exists()


def test_failed_conversion_keeps_old_video_and_uploaded_source(queue, monkeypatch):
    sessions, module_id, source = queue
    monkeypatch.setattr(video_import.subprocess, "run", Mock(side_effect=RuntimeError("ffmpeg failed")))
    video_import.process_next()
    with sessions() as db:
        module = db.get(Module, module_id)
        assert module.video_import_status == "failed"
        assert module.private_video == "old.mp4"
    assert source.exists()


def test_replaced_upload_is_not_overwritten_by_old_conversion(queue, monkeypatch):
    sessions, module_id, source = queue
    def run(command, **kwargs):
        if command[-1].endswith(".mp4"):
            Path(command[-1]).write_bytes(b"old conversion")
            with sessions() as db:
                module = db.get(Module, module_id)
                module.video_import_source = "education/video_sources/new.mov"
                module.video_import_status = "queued"
                db.commit()
    monkeypatch.setattr(video_import.subprocess, "run", run)
    video_import.process_next()
    with sessions() as db:
        module = db.get(Module, module_id)
        assert module.video_import_status == "queued"
        assert module.private_video == "old.mp4"
        assert module.video_import_source.endswith("new.mov")
    assert source.exists()


def test_yandex_download_still_uses_same_conversion_queue(queue, tmp_path, monkeypatch):
    sessions, module_id, _ = queue
    with sessions() as db:
        module = db.get(Module, module_id)
        module.video_import_source = ""
        module.video_url = "https://disk.yandex.ru/d/example/video.mp4"
        db.commit()
    monkeypatch.setattr(video_import.subprocess, "check_output", lambda *a, **k: b'{"href":"https://example.org/video"}')
    def run(command, **kwargs):
        if command[0] == "curl":
            Path(command[command.index("-o") + 1]).write_bytes(b"downloaded")
        elif command[-1].endswith(".mp4"):
            Path(command[-1]).write_bytes(b"converted")
    monkeypatch.setattr(video_import.subprocess, "run", run)
    video_import.process_next()
    with sessions() as db:
        assert db.get(Module, module_id).video_import_status == "ready"


def test_module_upload_is_queued_without_replacing_old_playable_file(queue, tmp_path, monkeypatch):
    from app.routers.hr import update_module
    sessions, module_id, _ = queue
    monkeypatch.setattr(file_streaming.settings, "media_root", str(tmp_path))
    with sessions() as db:
        module = db.get(Module, module_id)
        upload = SimpleNamespace(filename="new.mp4", file=io.BytesIO(b"new source"))
        response = update_module(module_id, course_id=module.course_id, name="Lesson", description="",
                                 video_url="https://disk.yandex.ru/d/ignored", order=1, is_active=True,
                                 private_video=upload, db=db)
        db.refresh(module)
        assert response.video_import_status == "queued"
        assert module.private_video == "old.mp4"
        assert module.video_url == ""
        assert (tmp_path / module.video_import_source).read_bytes() == b"new source"
        source_path = module.video_import_source
        # Editing metadata must not discard an upload waiting for conversion.
        update_module(module_id, course_id=module.course_id, name="Renamed", description="",
                      video_url="", order=1, is_active=True, private_video=None, db=db)
        db.refresh(module)
        assert module.video_import_source == source_path
        assert module.video_import_status == "queued"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="local ffmpeg not installed")
def test_real_ffmpeg_converts_small_uploaded_video(queue, tmp_path):
    sessions, module_id, source = queue
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
        "-i", "color=c=blue:s=64x64:r=2", "-t", "1", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-threads", "1", str(source),
    ], check=True)
    video_import.process_next()
    with sessions() as db:
        module = db.get(Module, module_id)
        assert module.video_import_status == "ready"
        assert (tmp_path / module.private_video).stat().st_size > 0
    assert not source.exists()
