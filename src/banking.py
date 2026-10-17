"""Secure Banking System: accounts, customers and an interactive menu."""

import logging
import re

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
LOG_FILE = "banking.log"


def configure_logger(name: str = "banking", log_file: str = LOG_FILE) -> logging.Logger:
    """Return a named logger that writes to the console and to a log file.

    Handlers are only attached once, so calling this function several times
    does not duplicate log lines.
    """
    configured_logger = logging.getLogger(name)
    configured_logger.setLevel(logging.INFO)
    if not configured_logger.handlers:
        formatter = logging.Formatter(LOG_FORMAT)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        file_handler = logging.FileHandler(log_file, encoding="utf-8", delay=True)
        file_handler.setFormatter(formatter)
        configured_logger.addHandler(console_handler)
        configured_logger.addHandler(file_handler)
    return configured_logger


logger = configure_logger()


class InsufficientFundsError(Exception):
    """Raised when an account does not have enough funds for an operation."""

    def __init__(self, message: str, amount: float) -> None:
        """Store the error message and the amount that could not be processed."""
        super().__init__(message)
        self.message = message
        self.amount = amount


class BankAccount:
    """A bank account with a private balance and validated operations."""

    ACCOUNT_TYPES: tuple[str, ...] = ("checking", "savings")
    RATES_TO_USD: dict[str, float] = {"USD": 1.0, "CRC": 0.0019, "EUR": 1.08}
    SAVINGS_MINIMUM_USD: float = 100.0

    def __init__(
        self,
        account_number: str,
        currency: str = "USD",
        account_type: str = "checking",
        balance: float = 0.0,
    ) -> None:
        """Create an account, validating its currency, type and initial balance."""
        currency = self._validate_currency(currency)
        if account_type not in self.ACCOUNT_TYPES:
            logger.error("Invalid account type '%s' for account %s", account_type, account_number)
            raise ValueError(f"Account type must be one of {', '.join(self.ACCOUNT_TYPES)}.")
        self.account_number = account_number
        self.currency = currency
        self._account_type = account_type
        self.__balance = 0.0
        self.balance = balance

    @classmethod
    def _validate_currency(cls, currency: str) -> str:
        """Return the currency code in upper case or raise ValueError if it is unknown."""
        code = str(currency).strip().upper()
        if code not in cls.RATES_TO_USD:
            logger.error("Unsupported currency '%s'", currency)
            raise ValueError(
                f"Unsupported currency '{currency}'. Use one of {', '.join(cls.RATES_TO_USD)}."
            )
        return code

    @property
    def account_type(self) -> str:
        """Return the account type, either 'checking' or 'savings'."""
        return self._account_type

    @property
    def balance(self) -> float:
        """Return the current balance in the account currency."""
        return self.__balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Set the balance, rejecting negative values."""
        if value < 0:
            logger.error(
                "Rejected negative balance %.2f for account %s", value, self.account_number
            )
            raise ValueError("Balance cannot be negative.")
        self.__balance = float(value)

    def get_account_number(self) -> str:
        """Return the account number."""
        return self.account_number

    def get_currency(self) -> str:
        """Return the account currency code."""
        return self.currency

    def deposit(self, amount: float) -> float:
        """Add a non-negative amount to the balance and return the new balance."""
        if amount < 0:
            logger.error(
                "Rejected negative deposit of %.2f into account %s", amount, self.account_number
            )
            raise ValueError("Deposit amount cannot be negative.")
        self.balance = self.balance + amount
        logger.info(
            "Deposited %.2f %s into account %s. New balance: %.2f %s",
            amount,
            self.currency,
            self.account_number,
            self.balance,
            self.currency,
        )
        return self.balance

    @classmethod
    def minimum_savings_balance(cls, currency: str = "USD") -> float:
        """Return the savings minimum of 100 USD expressed in the given currency."""
        code = cls._validate_currency(currency)
        return round(cls.SAVINGS_MINIMUM_USD / cls.RATES_TO_USD[code], 2)

    def withdraw(self, amount: float) -> float:
        """Subtract an amount from the balance and return the new balance.

        Savings accounts must keep at least the equivalent of 100 USD.
        """
        if amount < 0:
            logger.error(
                "Rejected negative withdrawal of %.2f from account %s", amount, self.account_number
            )
            raise ValueError("Withdrawal amount cannot be negative.")
        if amount > self.balance:
            message = (
                f"Insufficient funds in account {self.account_number}: "
                f"requested {amount:.2f} {self.currency}, available {self.balance:.2f} "
                f"{self.currency}."
            )
            logger.error(message)
            raise InsufficientFundsError(message, amount)
        if self.account_type == "savings":
            minimum = self.minimum_savings_balance(self.currency)
            if round(self.balance - amount, 2) < minimum:
                message = (
                    f"Withdrawal of {amount:.2f} {self.currency} would leave savings account "
                    f"{self.account_number} below the minimum of {minimum:.2f} {self.currency}."
                )
                logger.error(message)
                raise InsufficientFundsError(message, amount)
        self.balance = self.balance - amount
        logger.info(
            "Withdrew %.2f %s from account %s. New balance: %.2f %s",
            amount,
            self.currency,
            self.account_number,
            self.balance,
            self.currency,
        )
        return self.balance

    def convert_currency(self, target_currency: str, exchange_rate: float) -> float:
        """Print and return the balance converted with the given rate.

        The account itself is not modified.
        """
        if exchange_rate <= 0:
            logger.error(
                "Rejected non-positive exchange rate %s for account %s",
                exchange_rate,
                self.account_number,
            )
            raise ValueError("Exchange rate must be greater than zero.")
        target = str(target_currency).strip().upper()
        converted = self.balance * exchange_rate
        print(
            f"Account {self.account_number}: {self.balance:.2f} {self.currency} = "
            f"{converted:.2f} {target}"
        )
        logger.info(
            "Converted balance of account %s to %.2f %s at rate %s",
            self.account_number,
            converted,
            target,
            exchange_rate,
        )
        return converted

    @classmethod
    def create_savings(
        cls, account_number: str, currency: str = "USD", balance: float | None = None
    ) -> "BankAccount":
        """Create a savings account holding at least the equivalent of 100 USD.

        When no balance is given, the account opens with exactly the minimum.
        """
        minimum = cls.minimum_savings_balance(currency)
        if balance is None:
            balance = minimum
        if balance < minimum:
            logger.error(
                "Rejected savings account %s: initial balance %.2f is below the minimum of %.2f %s",
                account_number,
                balance,
                minimum,
                currency.upper(),
            )
            raise ValueError(
                f"A savings account needs at least {minimum:.2f} {currency.upper()} to open."
            )
        account = cls(account_number, currency, "savings", balance)
        logger.info(
            "Created savings account %s with %.2f %s",
            account.account_number,
            account.balance,
            account.currency,
        )
        return account

    @staticmethod
    def is_valid_account_number(account_number: object) -> bool:
        """Return True only for a string made of exactly 10 digits."""
        return (
            isinstance(account_number, str)
            and re.fullmatch(r"\d{10}", account_number, re.ASCII) is not None
        )

    def __repr__(self) -> str:
        """Return an unambiguous representation of the account."""
        return (
            f"BankAccount(account_number={self.account_number!r}, currency={self.currency!r}, "
            f"account_type={self.account_type!r}, balance={self.balance:.2f})"
        )

    def __str__(self) -> str:
        """Return a human-friendly description of the account."""
        return (
            f"{self.account_type.capitalize()} account {self.account_number}: "
            f"{self.balance:,.2f} {self.currency}"
        )
