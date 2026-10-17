import logging
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from src.banking import (
    LOG_FORMAT,
    BankAccount,
    Customer,
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


@pytest.fixture
def savings() -> BankAccount:
    return BankAccount("0987654321", "USD", "savings", 300.0)


def test_withdraw_decreases_balance(checking):
    assert checking.withdraw(200) == 300.0
    assert checking.balance == 300.0


def test_withdraw_logs_new_balance(checking, caplog):
    with caplog.at_level(logging.INFO, logger="banking"):
        checking.withdraw(50)
    assert caplog.records[-1].levelname == "INFO"
    assert "New balance: 450.00 USD" in caplog.text


def test_withdraw_entire_checking_balance(checking):
    assert checking.withdraw(500) == 0.0


def test_withdraw_rejects_negative_amount(checking, caplog):
    with pytest.raises(ValueError):
        checking.withdraw(-1)
    assert checking.balance == 500.0
    assert "Rejected negative withdrawal" in caplog.text


def test_withdraw_more_than_balance_raises_insufficient_funds(checking, caplog):
    with pytest.raises(InsufficientFundsError) as exc_info:
        checking.withdraw(500.01)
    assert exc_info.value.amount == 500.01
    assert checking.balance == 500.0
    assert caplog.records[-1].levelname == "ERROR"
    assert "Insufficient funds" in caplog.text


def test_savings_withdraw_down_to_minimum_is_allowed(savings):
    assert savings.withdraw(200) == 100.0


def test_savings_withdraw_below_minimum_is_rejected(savings, caplog):
    with pytest.raises(InsufficientFundsError) as exc_info:
        savings.withdraw(200.01)
    assert exc_info.value.amount == 200.01
    assert savings.balance == 300.0
    assert "below the minimum of 100.00 USD" in caplog.text


def test_savings_minimum_in_other_currency_is_converted():
    account = BankAccount("1111111111", "CRC", "savings", 60000.0)
    minimum = BankAccount.minimum_savings_balance("CRC")
    assert minimum == pytest.approx(52631.58)
    with pytest.raises(InsufficientFundsError):
        account.withdraw(60000.0 - minimum + 1)
    assert account.withdraw(60000.0 - minimum) == pytest.approx(minimum)


@pytest.mark.parametrize(
    ("currency", "expected"),
    [("USD", 100.0), ("EUR", 92.59), ("CRC", 52631.58)],
)
def test_minimum_savings_balance_per_currency(currency, expected):
    assert BankAccount.minimum_savings_balance(currency) == pytest.approx(expected)


def test_minimum_savings_balance_rejects_unknown_currency():
    with pytest.raises(ValueError):
        BankAccount.minimum_savings_balance("GBP")


def test_convert_currency_returns_and_prints_converted_balance(checking, capsys):
    result = checking.convert_currency("crc", 520.0)
    assert result == pytest.approx(260000.0)
    assert "260000.00 CRC" in capsys.readouterr().out
    assert checking.balance == 500.0
    assert checking.currency == "USD"


@pytest.mark.parametrize("rate", [0, -1.5])
def test_convert_currency_rejects_non_positive_rate(checking, caplog, rate):
    with pytest.raises(ValueError):
        checking.convert_currency("EUR", rate)
    assert caplog.records[-1].levelname == "ERROR"
    assert "Rejected non-positive exchange rate" in caplog.text


def test_create_savings_builds_savings_account():
    account = BankAccount.create_savings("1234567890", "USD", 150.0)
    assert isinstance(account, BankAccount)
    assert account.account_type == "savings"
    assert account.balance == 150.0


def test_create_savings_defaults_to_minimum_balance():
    assert BankAccount.create_savings("1234567890").balance == 100.0
    assert BankAccount.create_savings("1234567890", "EUR").balance == pytest.approx(92.59)


def test_create_savings_rejects_balance_below_minimum(caplog):
    with pytest.raises(ValueError):
        BankAccount.create_savings("1234567890", "USD", 99.99)
    assert caplog.records[-1].levelname == "ERROR"
    assert "below the minimum of 100.00 USD" in caplog.text


def test_create_savings_minimum_in_other_currency():
    with pytest.raises(ValueError):
        BankAccount.create_savings("1234567890", "CRC", 50000.0)
    account = BankAccount.create_savings("1234567890", "crc", 52631.58)
    assert account.currency == "CRC"


def test_create_savings_rejects_unknown_currency():
    with pytest.raises(ValueError):
        BankAccount.create_savings("1234567890", "BTC", 1000.0)


@pytest.mark.parametrize("account_number", ["1234567890", "0000000000"])
def test_is_valid_account_number_accepts_ten_digits(account_number):
    assert BankAccount.is_valid_account_number(account_number) is True


@pytest.mark.parametrize(
    "account_number",
    [
        "123456789",
        "12345678901",
        "12345abcde",
        "",
        " 1234567890",
        "1234567890\n",
        "١٢٣٤٥٦٧٨٩٠",
        1234567890,
        None,
        12.5,
        ["1234567890"],
    ],
)
def test_is_valid_account_number_rejects_invalid_values(account_number):
    assert BankAccount.is_valid_account_number(account_number) is False


def test_account_repr(checking):
    assert repr(checking) == (
        "BankAccount(account_number='1234567890', currency='USD', "
        "account_type='checking', balance=500.00)"
    )


def test_account_str(savings):
    savings.deposit(1000)
    assert str(savings) == "Savings account 0987654321: 1,300.00 USD"


def years_ago(years: int, today: date | None = None) -> date:
    today = today or date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


@pytest.fixture(autouse=True)
def reset_user_count():
    Customer.user_count = 0
    yield
    Customer.user_count = 0


@pytest.fixture
def adult_birth_date() -> date:
    return years_ago(30)


def test_customer_stores_name_birth_date_and_id(adult_birth_date):
    customer = Customer("  Ana Mora  ", adult_birth_date)
    assert customer.name == "Ana Mora"
    assert customer.birth_date == adult_birth_date
    assert customer.user_id == 1
    assert customer._user_id == 1
    assert customer.accounts == []


def test_customer_accepts_iso_string_birth_date(adult_birth_date):
    customer = Customer("Ana", adult_birth_date.isoformat())
    assert customer.birth_date == adult_birth_date


def test_customer_accepts_datetime_birth_date(adult_birth_date):
    moment = datetime.combine(adult_birth_date, datetime.min.time())
    assert Customer("Ana", moment).birth_date == adult_birth_date


@pytest.mark.parametrize("birth_date", ["16/10/1990", "1990-13-01", "", "not a date", 19900101])
def test_customer_rejects_invalid_birth_date(birth_date, caplog):
    with pytest.raises(ValueError):
        Customer("Ana", birth_date)
    assert caplog.records[-1].levelname == "ERROR"


@pytest.mark.parametrize("name", ["", "   ", None])
def test_customer_rejects_empty_name(name, adult_birth_date, caplog):
    with pytest.raises(ValueError):
        Customer(name, adult_birth_date)
    assert "empty name" in caplog.text


def test_customer_turning_18_today_is_accepted():
    assert Customer("Ana", years_ago(18)).user_id == 1


def test_customer_turning_18_tomorrow_is_rejected(caplog):
    with pytest.raises(ValueError):
        Customer("Ana", years_ago(18) + timedelta(days=1))
    assert caplog.records[-1].levelname == "ERROR"
    assert "is under 18" in caplog.text


def test_customer_with_future_birth_date_is_rejected():
    with pytest.raises(ValueError):
        Customer("Ana", date.today() + timedelta(days=1))


def test_customer_ids_are_consecutive(adult_birth_date):
    first = Customer("Ana", adult_birth_date)
    second = Customer("Luis", adult_birth_date)
    third = Customer("Sofia", adult_birth_date)
    assert [first.user_id, second.user_id, third.user_id] == [1, 2, 3]
    assert Customer.user_count == 3


def test_rejected_customer_does_not_consume_an_id(adult_birth_date):
    Customer("Ana", adult_birth_date)
    with pytest.raises(ValueError):
        Customer("Kid", years_ago(10))
    assert Customer("Luis", adult_birth_date).user_id == 2


@pytest.mark.parametrize(
    ("birth_date", "today", "expected"),
    [
        (date(2000, 5, 20), date(2026, 5, 19), 25),
        (date(2000, 5, 20), date(2026, 5, 20), 26),
        (date(2000, 5, 20), date(2026, 4, 30), 25),
        (date(2000, 5, 20), date(2026, 6, 1), 26),
        (date(2004, 2, 29), date(2022, 2, 28), 17),
        (date(2004, 2, 29), date(2022, 3, 1), 18),
    ],
)
def test_calculate_age_considers_month_and_day(birth_date, today, expected):
    assert Customer.calculate_age(birth_date, today) == expected


@pytest.fixture
def customer(adult_birth_date) -> Customer:
    return Customer("Ana Mora", adult_birth_date)


def test_add_account_with_valid_number(customer, checking, caplog):
    with caplog.at_level(logging.INFO, logger="banking"):
        assert customer.add_account(checking) is True
    assert customer.accounts == [checking]
    assert "added checking account 1234567890" in caplog.text


@pytest.mark.parametrize("account_number", ["123456789", "12345678901", "abcdefghij"])
def test_add_account_rejects_invalid_number(customer, account_number, caplog):
    assert customer.add_account(BankAccount(account_number)) is False
    assert customer.accounts == []
    assert caplog.records[-1].levelname == "ERROR"
    assert "invalid account number" in caplog.text


def test_add_account_rejects_duplicates(customer, checking, caplog):
    customer.add_account(checking)
    assert customer.add_account(BankAccount("1234567890", "EUR")) is False
    assert len(customer.accounts) == 1
    assert "already exists" in caplog.text


def test_add_account_rejects_non_accounts(customer):
    assert customer.add_account("1234567890") is False


def test_accounts_property_returns_a_copy(customer, checking):
    customer.add_account(checking)
    accounts = customer.accounts
    accounts.clear()
    assert customer.accounts == [checking]


def test_find_account(customer, checking, savings):
    customer.add_account(checking)
    customer.add_account(savings)
    assert customer.find_account("0987654321") is savings
    assert customer.find_account("5555555555") is None


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [(100.0, "USD", 100.0), (100.0, "EUR", 108.0), (100000.0, "crc", 190.0)],
)
def test_to_usd_uses_rate_table(amount, currency, expected):
    assert BankAccount.to_usd(amount, currency) == pytest.approx(expected)


def test_to_usd_rejects_unknown_currency():
    with pytest.raises(ValueError):
        BankAccount.to_usd(1.0, "XYZ")


def test_total_balance_without_accounts_is_zero(customer):
    assert customer.get_total_balance() == 0.0


def test_total_balance_sums_usd_accounts(customer, checking, savings):
    customer.add_account(checking)
    customer.add_account(savings)
    assert customer.get_total_balance() == 800.0


def test_total_balance_converts_other_currencies_to_usd(customer, checking):
    customer.add_account(checking)
    customer.add_account(BankAccount("2222222222", "EUR", balance=100.0))
    customer.add_account(BankAccount("3333333333", "CRC", balance=100000.0))
    assert customer.get_total_balance() == pytest.approx(500.0 + 108.0 + 190.0)


@pytest.fixture
def customer_with_accounts(customer, checking, savings) -> Customer:
    customer.add_account(checking)
    customer.add_account(savings)
    return customer


def test_transfer_moves_money(customer_with_accounts, checking, savings, caplog):
    with caplog.at_level(logging.INFO, logger="banking"):
        assert customer_with_accounts.transfer(200, "1234567890", "0987654321") is True
    assert checking.balance == 300.0
    assert savings.balance == 500.0
    assert caplog.records[-1].levelname == "INFO"
    assert "transferred 200.00 USD" in caplog.text


def test_transfer_from_savings_respects_minimum(customer_with_accounts, checking, savings, caplog):
    assert customer_with_accounts.transfer(250, "0987654321", "1234567890") is False
    assert savings.balance == 300.0
    assert checking.balance == 500.0
    assert caplog.records[-1].levelname == "ERROR"
    assert "transfer of 250" in caplog.text


def test_transfer_with_insufficient_funds_fails(customer_with_accounts, checking, savings):
    assert customer_with_accounts.transfer(1000, "1234567890", "0987654321") is False
    assert checking.balance == 500.0
    assert savings.balance == 300.0


def test_transfer_with_negative_amount_fails(customer_with_accounts, checking, savings):
    assert customer_with_accounts.transfer(-10, "1234567890", "0987654321") is False
    assert checking.balance == 500.0
    assert savings.balance == 300.0


def test_transfer_to_unknown_account_fails(customer_with_accounts, checking, caplog):
    assert customer_with_accounts.transfer(10, "1234567890", "9999999999") is False
    assert checking.balance == 500.0
    assert "must both belong to them" in caplog.text


def test_transfer_to_another_customers_account_fails(customer_with_accounts, adult_birth_date):
    other = Customer("Luis", adult_birth_date)
    other.add_account(BankAccount("5555555555", balance=10.0))
    assert customer_with_accounts.transfer(10, "1234567890", "5555555555") is False


def test_transfer_to_same_account_fails(customer_with_accounts, checking, caplog):
    assert customer_with_accounts.transfer(10, "1234567890", "1234567890") is False
    assert checking.balance == 500.0
    assert "same account" in caplog.text


def test_transfer_between_currencies_fails(customer, checking, caplog):
    euros = BankAccount("2222222222", "EUR", balance=100.0)
    customer.add_account(checking)
    customer.add_account(euros)
    assert customer.transfer(10, "1234567890", "2222222222") is False
    assert checking.balance == 500.0
    assert euros.balance == 100.0
    assert "currencies differ" in caplog.text


def test_transfer_restores_source_when_deposit_fails(customer_with_accounts, checking, savings):
    with patch.object(BankAccount, "deposit", side_effect=ValueError("boom")):
        assert customer_with_accounts.transfer(100, "1234567890", "0987654321") is False
    assert checking.balance == 500.0
    assert savings.balance == 300.0


def test_customer_repr():
    customer = Customer("Ana Mora", date(1990, 1, 15))
    assert repr(customer) == (
        "Customer(user_id=1, name='Ana Mora', birth_date='1990-01-15', accounts=0)"
    )


def test_customer_str_without_accounts():
    customer = Customer("Ana Mora", date(1990, 1, 15))
    assert str(customer) == (
        "Customer 1: Ana Mora (born 1990-01-15)\n  - No accounts\nTotal balance: 0.00 USD"
    )


def test_customer_str_with_accounts(checking):
    customer = Customer("Ana Mora", date(1990, 1, 15))
    customer.add_account(checking)
    customer.add_account(BankAccount("2222222222", "EUR", "savings", 1000.0))
    assert str(customer) == (
        "Customer 1: Ana Mora (born 1990-01-15)\n"
        "  - Checking account 1234567890: 500.00 USD\n"
        "  - Savings account 2222222222: 1,000.00 EUR\n"
        "Total balance: 1,580.00 USD"
    )
