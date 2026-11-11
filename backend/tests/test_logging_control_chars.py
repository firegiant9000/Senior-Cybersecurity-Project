import logging

import pytest

from app.core.logging import (
    ControlCharFormatter,
    JsonFormatter,
    escape_control_chars,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """setup_logging replaces the root handlers; put them back after each test."""
    root = logging.getLogger()
    handlers = root.handlers[:]
    level = root.level
    yield
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def test_escape_control_chars_replaces_newlines_and_c0():
    assert escape_control_chars("a\r\nb\x1b[31m") == "a\\r\\nb\\x1b[31m"
    assert escape_control_chars("plain text\twith tab") == "plain text\twith tab"


def test_text_handler_emits_one_line_for_a_forged_message(capsys):
    setup_logging("INFO", json_output=False)
    logging.getLogger("t").info("org %s", "1\n2026-01-01 - app - ERROR - forged")
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert "\\n2026-01-01 - app - ERROR - forged" in out


def test_traceback_stays_multiline(capsys):
    setup_logging("INFO", json_output=False)
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("t").exception("failed %s", "x\ny")
    out = capsys.readouterr().out
    assert "failed x\\ny" in out
    assert "Traceback (most recent call last):\n" in out


def test_json_handler_uses_json_formatter_only():
    setup_logging("INFO", json_output=True)
    formatter = logging.getLogger().handlers[0].formatter
    assert isinstance(formatter, JsonFormatter)
    assert not isinstance(formatter, ControlCharFormatter)


def test_text_formatter_leaves_the_original_record_untouched():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "org %s", ("a\nb",), None)
    line = ControlCharFormatter("%(message)s").format(record)
    assert line == "org a\\nb"
    assert record.msg == "org %s"
    assert record.args == ("a\nb",)
