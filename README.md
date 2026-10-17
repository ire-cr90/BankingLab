# Secure Banking System

[![CI](https://github.com/ire-cr90/BankingLab/actions/workflows/ci.yml/badge.svg)](https://github.com/ire-cr90/BankingLab/actions/workflows/ci.yml)

Banking laboratory for **SOFT-753 Automation with Python** (CENFOTEC, section SEV8, period M6-2026).
It models bank accounts and customers with encapsulation, validations, custom exceptions and
logging, and exposes everything through an interactive console menu.

## Features

- `BankAccount` with public, protected and private attributes, and every method decorator:
  `@property`, `@balance.setter`, `@classmethod` and `@staticmethod`.
- Checking and savings accounts in USD, CRC or EUR.
- Savings accounts always keep at least the equivalent of 100 USD (on creation, withdrawals and transfers).
- `InsufficientFundsError(message, amount)` custom exception.
- `Customer` with 18+ age validation, consecutive ids and a private list of accounts.
- Transfers between accounts of the same customer that never leave money half moved.
- Logging of every operation (`INFO`) and every rejected operation (`ERROR`) with timestamp,
  level and message, to the console and to `banking.log`.
- Interactive menu with input validation and graceful handling of `Ctrl+C`.
- 144 `pytest` tests, Ruff linting and formatting, and GitHub Actions CI.

## Class design

### `InsufficientFundsError(Exception)`

| Attribute | Description |
| --- | --- |
| `message` | Human-readable reason |
| `amount` | Amount that could not be withdrawn |

### `BankAccount`

| Member | Kind | Description |
| --- | --- | --- |
| `account_number` | public attribute | Account number (valid when it has exactly 10 digits) |
| `currency` | public attribute | `USD`, `CRC` or `EUR` |
| `_account_type` | protected attribute | `checking` or `savings` |
| `__balance` | private attribute | Current balance |
| `account_type` | `@property` | Read-only getter for `_account_type` |
| `balance` | `@property` + `@balance.setter` | Getter and validated setter (rejects negatives) |
| `get_account_number()`, `get_currency()` | methods | Getters for the public attributes |
| `deposit(amount)` | method | Adds money, rejects negative amounts |
| `withdraw(amount)` | method | Removes money, enforces available funds and the savings minimum |
| `convert_currency(target_currency, exchange_rate)` | method | Prints and returns the converted balance without modifying the account |
| `create_savings(account_number, currency, balance)` | `@classmethod` | Builds a savings account with at least the 100 USD equivalent |
| `minimum_savings_balance(currency)` | `@classmethod` | The 100 USD minimum expressed in a currency |
| `to_usd(amount, currency)` | `@classmethod` | Converts an amount to USD with the rate table |
| `is_valid_account_number(account_number)` | `@staticmethod` | `True` only for a string of exactly 10 digits |

### `Customer`

| Member | Kind | Description |
| --- | --- | --- |
| `user_count` | class attribute | Number of ids handed out so far |
| `_next_user_id()` | `@classmethod` | Returns the next consecutive id |
| `calculate_age(birth_date, today)` | `@staticmethod` | Age in full years considering month and day |
| `name`, `birth_date`, `user_id` | `@property` | Read-only getters |
| `accounts` | `@property` | A copy of the private `__accounts` list |
| `add_account(account)` | method | Adds an account with a valid, non-duplicated number; returns `True`/`False` |
| `find_account(account_number)` | method | Returns the account or `None` |
| `get_total_balance()` | method | Sum of all balances in USD |
| `transfer(amount, source, target)` | method | Moves money between two of the customer's accounts; returns `True`/`False` |

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 automatically if needed).

```bash
git clone https://github.com/ire-cr90/BankingLab.git
cd BankingLab
uv sync
```

## Running the application

```bash
uv run python src/banking.py
```

Menu options:

1. Add a new customer
2. Add a new account to a customer (checking or savings)
3. Deposit
4. Withdraw
5. Convert currency (show balance in another currency)
6. Transfer between two accounts of the same customer
7. Show a customer with its accounts and total balance
0. Exit

Every operation is logged to the console and appended to `banking.log` in the current directory.

## Tests and linting

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format .
```

The CI workflow (`.github/workflows/ci.yml`) runs on every pull request and on pushes to `main`:
it installs the project with `uv sync`, then runs `ruff check`, `ruff format --check` and `pytest -v`.

## Design decisions

Decisions not covered by the original instructions:

- **Dependencies.** Only `pytest` and `ruff` are installed (as dev dependencies). `logging`, `time`
  and `os` belong to the standard library and must not be installed with `uv add`.
- **Project layout.** The project was created with `uv init --app --no-package`, because the
  default layout of recent uv versions creates a package (`src/banking_lab/`) instead of the
  single `src/banking.py` file the instructions require.
- **Getters.** `account_number` and `currency` stay public attributes and get `get_account_number()`
  and `get_currency()` methods; `account_type` and `balance` are `@property` getters. Only
  `balance` has a setter, so `account_type` is read-only.
- **Zero amounts.** Deposits, withdrawals and transfers of `0` are allowed, following the
  "non-negative" wording of the instructions. Only negative amounts are rejected.
- **Exchange rates.** `BankAccount.RATES_TO_USD = {"USD": 1.0, "CRC": 0.0019, "EUR": 1.08}`.
  These values are illustrative, not real market rates. Currency codes are case-insensitive and
  stored in upper case; any other currency raises `ValueError`.
- **Savings minimum.** The 100 USD minimum is converted into the account currency and rounded to
  cents (92.59 EUR, 52,631.58 CRC). Balance checks are also rounded to cents, so withdrawing down to
  exactly the minimum is never rejected by floating-point noise.
- **`create_savings` default balance.** When no balance is given, the account opens with exactly
  the minimum in its currency.
- **Plain constructor.** `BankAccount(..., account_type="savings")` does not check the minimum
  because the instructions only require it in `create_savings`; withdrawals still enforce it.
- **Account number validation.** As required, the number is validated in `Customer.add_account`,
  not in the `BankAccount` constructor. `add_account` also rejects duplicates for the same
  customer, and the menu rejects numbers already used by any customer.
- **Total balance.** `get_total_balance()` converts every balance to USD with the rate table and
  rounds the result to cents.
- **Cross-currency transfers** are rejected with an `ERROR` log.
- **Transfer rollback.** `transfer` withdraws from the source first (which enforces the savings
  minimum) and then deposits into the target. If the deposit fails, the source balance is restored.
- **Birth dates.** `Customer` accepts a `datetime.date`, a `datetime.datetime` or a `"YYYY-MM-DD"`
  string. The age considers month and day (people born on February 29 turn a year older on
  March 1 in non-leap years). Future dates are rejected as underage.
- **Customer ids.** Rejected customers do not consume an id. Names are stored without surrounding
  spaces. `name`, `birth_date` and `user_id` are read-only.
- **Currency conversion in the menu.** For a known target currency the menu suggests the rate
  derived from the table (press Enter to accept it); for other currencies a rate is required.
- **Menu account selection.** Account operations ask for the customer id first and then for one
  of that customer's account numbers.
- **Menu input.** Empty answers, non-numeric values and non-finite numbers (`nan`, `inf`) are
  rejected with friendly messages; `Ctrl+C` and end of input exit gracefully.
- **Logging.** Handlers are attached only once to the `banking` logger so log lines are never
  duplicated. The log file is opened lazily, when the first message is written.
- **Tests.** Each feature was committed together with its tests, instead of adding all the tests
  in the last phase. Birth dates in tests are computed relative to `date.today()` so they never
  expire, and autouse fixtures reset `Customer.user_count` and the menu's customer list.

## Known issues in the original instructions

- `logging`, `time` and `os` are standard library modules. The `logging` package on PyPI is an
  old Python 2 package, so it must not be installed.
- "Getters for all attributes" conflicts with keeping `account_number` and `currency` as public
  attributes, because a property cannot share the name of an attribute. See the getters decision.
- The "equivalent amount in another currency" for the savings minimum requires exchange rates,
  which are not defined. See the exchange rates decision.
- `get_total_balance()` is ambiguous when accounts use different currencies. It returns USD.
- The PDF says `__balanced`; it means `__balance`.
