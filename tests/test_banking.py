import logging

from src.banking import LOG_FORMAT, configure_logger, logger


def test_logger_has_console_and_file_handlers():
    handler_types = {type(handler) for handler in logger.handlers}
    assert logging.StreamHandler in handler_types
    assert logging.FileHandler in handler_types


def test_logger_uses_timestamp_level_message_format():
    for handler in logger.handlers:
        assert handler.formatter._fmt == LOG_FORMAT


def test_configure_logger_does_not_duplicate_handlers():
    handler_count = len(logger.handlers)
    configure_logger()
    assert len(logger.handlers) == handler_count


def test_logger_writes_to_log_file(tmp_path):
    log_file = tmp_path / "test.log"
    file_logger = configure_logger("test_banking_file", str(log_file))
    file_logger.info("hello log")
    for handler in file_logger.handlers:
        handler.close()
    content = log_file.read_text(encoding="utf-8")
    assert "| INFO | hello log" in content
