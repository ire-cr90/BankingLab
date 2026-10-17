"""Secure Banking System: accounts, customers and an interactive menu."""

import logging

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
