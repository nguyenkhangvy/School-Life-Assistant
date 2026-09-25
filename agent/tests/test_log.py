import logging

import pytest

from sla_agent.log import protect, setup_logging


def _handlers_writing_under(folder):
    return [h for h in logging.getLogger().handlers if str(folder) in getattr(h, "baseFilename", "")]


@pytest.fixture
def log_file(tmp_path):
    path = setup_logging(tmp_path)
    yield path
    for handler in _handlers_writing_under(tmp_path):
        logging.getLogger().removeHandler(handler)
        handler.close()


def read(path):
    for handler in _handlers_writing_under(path.parent):
        handler.flush()
    return path.read_text(encoding="utf-8")


def test_protected_secrets_are_replaced_in_the_log_file(log_file):
    protect("s3cret-pass")

    logging.getLogger("sla_agent.test").warning("login with s3cret-pass failed")

    text = read(log_file)
    assert "login with *** failed" in text
    assert "s3cret-pass" not in text


def test_secrets_inside_error_tracebacks_are_replaced(log_file):
    protect("sla_device-key-123456")

    try:
        raise RuntimeError("server refused key sla_device-key-123456")
    except RuntimeError:
        logging.getLogger("sla_agent.test").exception("upload failed")

    text = read(log_file)
    assert "RuntimeError: server refused key ***" in text
    assert "sla_device-key-123456" not in text


def test_the_log_file_keeps_normal_text_including_vietnamese(log_file):
    logging.getLogger("sla_agent.test").info("Thời khóa biểu: 8 môn")

    assert "Thời khóa biểu: 8 môn" in read(log_file)


def test_setting_up_twice_does_not_duplicate_lines(tmp_path):
    setup_logging(tmp_path)
    path = setup_logging(tmp_path)

    logging.getLogger("sla_agent.test").warning("only once")

    for handler in _handlers_writing_under(tmp_path):
        handler.flush()
        logging.getLogger().removeHandler(handler)
        handler.close()
    assert path.read_text(encoding="utf-8").count("only once") == 1
