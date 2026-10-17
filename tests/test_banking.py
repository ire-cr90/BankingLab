import logging

import pytest

from src.banking import (
    LOG_FORMAT,
    BankAccount,
    InsufficientFundsError,
    configure_logger,
    logger,
)


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


def test_insufficient_funds_error_carries_message_and_amount():
    error = InsufficientFundsError("Not enough funds", 250.0)
    assert error.message == "Not enough funds"
    assert error.amount == 250.0
    assert str(error) == "Not enough funds"


def test_insufficient_funds_error_is_an_exception():
    with pytest.raises(InsufficientFundsError) as exc_info:
        raise InsufficientFundsError("Not enough funds", 10.0)
    assert exc_info.value.amount == 10.0


@pytest.fixture
def checking() -> BankAccount:
    return BankAccount("1234567890", "USD", "checking", 500.0)


def test_account_stores_public_protected_and_private_attributes(checking):
    assert checking.account_number == "1234567890"
    assert checking.currency == "USD"
    assert checking._account_type == "checking"
    assert checking._BankAccount__balance == 500.0
    assert not hasattr(checking, "__balance")


def test_account_getters(checking):
    assert checking.get_account_number() == "1234567890"
    assert checking.get_currency() == "USD"
    assert checking.account_type == "checking"
    assert checking.balance == 500.0


def test_account_defaults():
    account = BankAccount("1234567890")
    assert account.currency == "USD"
    assert account.account_type == "checking"
    assert account.balance == 0.0


def test_account_type_is_read_only(checking):
    with pytest.raises(AttributeError):
        checking.account_type = "savings"


def test_currency_is_normalized_to_upper_case():
    assert BankAccount("1234567890", "crc").currency == "CRC"


def test_unknown_currency_is_rejected(caplog):
    with pytest.raises(ValueError):
        BankAccount("1234567890", "JPY")
    assert "Unsupported currency 'JPY'" in caplog.text


def test_invalid_account_type_is_rejected(caplog):
    with pytest.raises(ValueError):
        BankAccount("1234567890", account_type="investment")
    assert "ERROR" in caplog.text
    assert "Invalid account type 'investment'" in caplog.text


def test_balance_setter_updates_balance(checking):
    checking.balance = 42.5
    assert checking.balance == 42.5


def test_balance_setter_rejects_negative_values(checking, caplog):
    with pytest.raises(ValueError):
        checking.balance = -1
    assert checking.balance == 500.0
    assert "Rejected negative balance" in caplog.text
    assert caplog.records[-1].levelname == "ERROR"


def test_constructor_validates_initial_balance_through_setter():
    with pytest.raises(ValueError):
        BankAccount("1234567890", balance=-10.0)


def test_deposit_increases_balance(checking):
    assert checking.deposit(150.25) == pytest.approx(650.25)
    assert checking.balance == pytest.approx(650.25)


def test_deposit_logs_new_balance(checking, caplog):
    with caplog.at_level(logging.INFO, logger="banking"):
        checking.deposit(100)
    assert caplog.records[-1].levelname == "INFO"
    assert "New balance: 600.00 USD" in caplog.text


def test_deposit_of_zero_is_allowed(checking):
    assert checking.deposit(0) == 500.0


def test_deposit_rejects_negative_amount(checking, caplog):
    with pytest.raises(ValueError):
        checking.deposit(-5)
    assert checking.balance == 500.0
    assert caplog.records[-1].levelname == "ERROR"
    assert "Rejected negative deposit" in caplog.text
