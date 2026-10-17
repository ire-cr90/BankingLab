"""Secure Banking System: accounts, customers and an interactive menu."""

import logging
import re
from datetime import date, datetime

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

    @classmethod
    def to_usd(cls, amount: float, currency: str) -> float:
        """Return the amount converted from the given currency into USD."""
        code = cls._validate_currency(currency)
        return amount * cls.RATES_TO_USD[code]

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


class Customer:
    """A bank customer who is at least 18 years old and owns bank accounts."""

    MINIMUM_AGE: int = 18
    user_count: int = 0

    def __init__(self, name: str, birth_date: date | str) -> None:
        """Create a customer, validating the name and that they are an adult."""
        if not isinstance(name, str) or not name.strip():
            logger.error("Rejected customer with an empty name")
            raise ValueError("Customer name cannot be empty.")
        parsed_birth_date = self._parse_birth_date(birth_date)
        age = self.calculate_age(parsed_birth_date)
        if age < self.MINIMUM_AGE:
            logger.error(
                "Rejected customer '%s': age %d is under %d", name.strip(), age, self.MINIMUM_AGE
            )
            raise ValueError(f"Customer must be at least {self.MINIMUM_AGE} years old.")
        self._name = name.strip()
        self._birth_date = parsed_birth_date
        self._user_id = self._next_user_id()
        self.__accounts: list[BankAccount] = []
        logger.info("Created customer %d: %s", self._user_id, self._name)

    @classmethod
    def _next_user_id(cls) -> int:
        """Increase the customer counter and return the new consecutive id."""
        cls.user_count += 1
        return cls.user_count

    @staticmethod
    def _parse_birth_date(birth_date: date | str) -> date:
        """Return the birth date as a date, accepting a date or a 'YYYY-MM-DD' string."""
        if isinstance(birth_date, datetime):
            return birth_date.date()
        if isinstance(birth_date, date):
            return birth_date
        if isinstance(birth_date, str):
            try:
                return date.fromisoformat(birth_date.strip())
            except ValueError:
                pass
        logger.error("Invalid birth date '%s', expected YYYY-MM-DD", birth_date)
        raise ValueError("Birth date must be a date or a 'YYYY-MM-DD' string.")

    @staticmethod
    def calculate_age(birth_date: date, today: date | None = None) -> int:
        """Return the age in full years, taking month and day into account."""
        today = today or date.today()
        had_birthday = (today.month, today.day) >= (birth_date.month, birth_date.day)
        return today.year - birth_date.year - (0 if had_birthday else 1)

    @property
    def name(self) -> str:
        """Return the customer name."""
        return self._name

    @property
    def birth_date(self) -> date:
        """Return the customer birth date."""
        return self._birth_date

    @property
    def user_id(self) -> int:
        """Return the consecutive customer id."""
        return self._user_id

    @property
    def accounts(self) -> list[BankAccount]:
        """Return a copy of the customer accounts list."""
        return list(self.__accounts)

    def find_account(self, account_number: str) -> BankAccount | None:
        """Return the customer account with the given number, or None if it does not exist."""
        for account in self.__accounts:
            if account.account_number == account_number:
                return account
        return None

    def add_account(self, account: BankAccount) -> bool:
        """Add an account with a valid, non-duplicated number and report whether it was added."""
        if not isinstance(account, BankAccount):
            logger.error("Customer %d: rejected an object that is not a BankAccount", self._user_id)
            return False
        if not BankAccount.is_valid_account_number(account.account_number):
            logger.error(
                "Customer %d: invalid account number '%s', it must have exactly 10 digits",
                self._user_id,
                account.account_number,
            )
            return False
        if self.find_account(account.account_number) is not None:
            logger.error(
                "Customer %d: account %s already exists", self._user_id, account.account_number
            )
            return False
        self.__accounts.append(account)
        logger.info(
            "Customer %d: added %s account %s",
            self._user_id,
            account.account_type,
            account.account_number,
        )
        return True

    def get_total_balance(self) -> float:
        """Return the sum of all account balances converted to USD, rounded to cents."""
        total = 0.0
        for account in self.__accounts:
            total += BankAccount.to_usd(account.balance, account.currency)
        return round(total, 2)

    def transfer(
        self, amount: float, source_account_number: str, target_account_number: str
    ) -> bool:
        """Move money between two different accounts of this customer.

        Both accounts must use the same currency. If any step fails the source
        balance is restored, so money is never left half moved.
        """
        source = self.find_account(source_account_number)
        target = self.find_account(target_account_number)
        if source is None or target is None:
            logger.error(
                "Customer %d: transfer rejected, accounts %s and %s must both belong to them",
                self._user_id,
                source_account_number,
                target_account_number,
            )
            return False
        if source is target:
            logger.error(
                "Customer %d: transfer rejected, source and target are the same account %s",
                self._user_id,
                source_account_number,
            )
            return False
        if source.currency != target.currency:
            logger.error(
                "Customer %d: transfer rejected, currencies differ (%s to %s)",
                self._user_id,
                source.currency,
                target.currency,
            )
            return False
        original_source_balance = source.balance
        try:
            source.withdraw(amount)
            try:
                target.deposit(amount)
            except (ValueError, InsufficientFundsError):
                source.balance = original_source_balance
                raise
        except (ValueError, InsufficientFundsError) as error:
            logger.error(
                "Customer %d: transfer of %s from %s to %s failed: %s",
                self._user_id,
                amount,
                source_account_number,
                target_account_number,
                error,
            )
            return False
        logger.info(
            "Customer %d: transferred %.2f %s from %s to %s",
            self._user_id,
            amount,
            source.currency,
            source_account_number,
            target_account_number,
        )
        return True

    def __repr__(self) -> str:
        """Return an unambiguous representation of the customer."""
        return (
            f"Customer(user_id={self._user_id}, name={self._name!r}, "
            f"birth_date={self._birth_date.isoformat()!r}, accounts={len(self.__accounts)})"
        )

    def __str__(self) -> str:
        """Return the customer details, accounts and total balance in USD."""
        lines = [f"Customer {self._user_id}: {self._name} (born {self._birth_date.isoformat()})"]
        if self.__accounts:
            lines.extend(f"  - {account}" for account in self.__accounts)
        else:
            lines.append("  - No accounts")
        lines.append(f"Total balance: {self.get_total_balance():,.2f} USD")
        return "\n".join(lines)
