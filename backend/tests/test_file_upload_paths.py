import os

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.services import file_upload


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def test_normal_name_resolves_inside_org_dir(upload_dir):
    path = file_upload.resolve_upload_path(7, "abc123_report.csv")
    assert path == os.path.join(os.path.realpath(upload_dir), "7", "abc123_report.csv")


@pytest.mark.parametrize(
    "name", ["../8/secret.csv", "../../etc/passwd", "/etc/passwd", "a/../../x", ""]
)
def test_escaping_names_are_refused(upload_dir, name):
    with pytest.raises(HTTPException) as exc:
        file_upload.resolve_upload_path(7, name)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid file name"


def test_relative_upload_dir_still_resolves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "UPLOAD_DIR", "uploads")
    path = file_upload.resolve_upload_path(1, "abc_x.csv")
    assert path == os.path.join(os.path.realpath(tmp_path / "uploads"), "1", "abc_x.csv")


def test_delete_refuses_an_escaping_name(upload_dir):
    outside = upload_dir.parent / "victim.txt"
    outside.write_text("keep")
    with pytest.raises(HTTPException):
        file_upload.delete_upload_file(7, "../../victim.txt")
    assert outside.exists()
