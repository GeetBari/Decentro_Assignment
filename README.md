# Decentro Assignment: Expense Sharing Service

A Python backend for recording group expenses, splitting costs, viewing balances, and recording settlements. Built with FastAPI, SQLAlchemy, and SQLite.

For a dinner costing INR 1,200 paid by Mohit and shared with Rahul and Ankit, the service records a share of INR 400 each. Rahul owes Mohit INR 400, Ankit owes Mohit INR 400, and Mohit has no self-debt.

## Run locally

Requires Python 3.13. Run commands from the repository root.

```bash
git clone https://github.com/GeetBari/Decentro_Assignment.git
cd Decentro_Assignment
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install and start:

```bash
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` instead of `python`; changing the execution policy is unnecessary.

- Interactive API documentation: [Swagger UI](http://127.0.0.1:8000/docs)
- Alternative API documentation: [ReDoc](http://127.0.0.1:8000/redoc)
- Machine-readable schema: [OpenAPI JSON](http://127.0.0.1:8000/openapi.json)
- Health check: [Health](http://127.0.0.1:8000/health)

Tables are created on startup. The default SQLite database is `expenses.db` in the working directory, excluded from Git. To change it, set `DATABASE_URL` to another SQLite URL; its parent directory must already exist. `.env.example` documents the variable, but `.env` files are not automatically loaded.

The repository is private during development. Reviewers need access or the repository must be made public before submission.

## Run the demo

With the API running, open a second terminal in the activated environment:

```bash
python scripts/demo.py
```

The script creates three users and a fresh group, adds the INR 1,200 dinner, checks the expected balances, records Rahul's INR 400 payment, and verifies that Ankit's INR 400 payment is the only remaining suggestion. Re-running creates a new group without deleting existing data.

For manual requests, see [API examples](docs/API.md) or import [the Postman collection](docs/postman_collection.json). Run the collection in order; it captures generated IDs automatically.

## Features

- Create/list users and groups; add/list group members.
- Equal expense splitting across all members present when an expense is created.
- Expense history with category, description search, UTC date filters, and pagination.
- Pairwise balances and member totals for amounts paid, shares, payments, and net position.
- **Product enhancement:** settlement suggestions that remove unnecessary intermediate payments.
- Optional custom unequal splits and recorded partial/full settlements.
- Validation of amounts, memberships, duplicate members, and overpayments.
- Automated tests, Docker configuration, and a GitHub Actions test workflow.

## Architecture

```text
Swagger UI / Postman / HTTP client
             |
      FastAPI routes + Pydantic schemas
             |
      Expense and balance services
             |
      SQLAlchemy models + transactions
             |
           SQLite
```

`app/routes.py` handles HTTP and simple user/group operations. `app/services/` contains splitting, expense creation, balances, and settlement rules. `app/models.py` declares the schema. `app/database.py` supplies one transaction per request. `app/main.py` initializes the application and handles errors.

Balances are derived from expenses, shares, and payments. There is no separate balance table that could drift out of sync. See [architecture and schema](docs/ARCHITECTURE.md) for relationships and transaction choices.

## Assumptions and decisions

- Currency is **INR**, with two decimal places. Currency conversion is out of scope.
- Requests accept numbers or decimal strings; responses use fixed two-decimal strings, such as `"400.00"`, to preserve precision for clients.
- Money is stored as integer paise. Each expense/payment is capped at INR 1,000,000,000.00.
- Equal splits include the payer. INR 100 across three people becomes INR 33.34, 33.33, and 33.33. Remainder paise go to ascending user IDs. Tiny expenses can produce zero shares.
- Saved shares preserve historical membership. New members do not inherit old expenses.
- Custom shares must be nonnegative, reference distinct group members, and total the expense. Omitted members have no share. The payer may pay entirely for another member.
- Names need not be unique; IDs identify users. Creating a group does not automatically add members.
- Positive `net_balance` means receivable; negative means payable. Group net balances sum to zero.
- Settlements record payments made elsewhere. Sender must be a net debtor, recipient a net creditor, and the amount cannot exceed either outstanding net position.
- **Pairwise ledger balances and simplified payment plans are different views.** Cross-pair payments can leave a zero-net cycle in the pairwise ledger. Use `is_settled` and settlement suggestions to determine whether more payments are needed; the architecture guide explains this with an example.
- No authentication, payment gateway, editing/deletion, or membership removal is provided. This is a trusted local assignment demo.

## Why settlement suggestions?

After a trip, people want to know which payments to make. If A owes B INR 100 and B owes C INR 100, A can pay C directly. This feature answers that question without modifying expense records.

The algorithm calculates net positions, sorts debtors and creditors by outstanding amount, then matches them until their positions reach zero. IDs break ties deterministically. With `k` nonzero members, it returns at most `k - 1` payments. Sorting costs `O(k log k)` and matching costs `O(k)` after loading the ledger.

Tradeoffs: suggested recipients can differ from the original payer, so group agreement to net settlement is assumed. This greedy algorithm does not guarantee the absolute minimum number of transfers. It is deterministic, easy to explain, and sufficient for small groups. It performs no real money transfers.

## Tests and code checks

```bash
python -m pytest -q
python -m pytest --cov=app --cov-report=term-missing
python -m ruff check app tests scripts
python -m ruff format --check app tests scripts
```

Tests use isolated temporary SQLite databases. They cover the PDF example, multiple payers, rounding, validation, custom splits, late members, duplicate names, group isolation, partial/cross-pair settlements, transaction rollback, and concurrent settlements. Deterministic randomized tests check money conservation and settlement-plan correctness.

GitHub Actions runs checks on Python 3.13. See [verification notes](docs/VERIFICATION.md) for actual verification results and limitations.

## Docker

With Docker Desktop running in Linux-container mode:

```bash
docker compose up --build -d
docker compose ps
```

Open `http://127.0.0.1:8000/docs`. A named volume preserves the database across container restarts. The container runs as a non-root user; the published port binds to localhost.

```bash
docker compose down
```

Stopping the service keeps its database volume. `requirements.txt` contains runtime packages; `requirements-dev.txt` adds testing tools.

## Submission documents

- [Requirements checklist](docs/REQUIREMENTS.md)
- [Architecture and database schema](docs/ARCHITECTURE.md)
- [API guide](docs/API.md)
- [Postman collection](docs/postman_collection.json)
- [Demo and interview preparation](docs/DEMO.md)
- [Verification notes](docs/VERIFICATION.md)

## Improvements with more time

1. Authentication and per-group authorization before public deployment.
2. Idempotency keys for expense/payment creation to make retries safe.
3. Alembic schema migrations and PostgreSQL if concurrent write volume grows.
4. Audited expense corrections and membership removal rules.
5. SQL aggregation or cached summaries for very large ledgers.
6. Receipt attachments, a small UI, and explicit multi-currency rules.

Lifecycle and database patterns were checked against the [FastAPI documentation](https://fastapi.tiangolo.com/advanced/events/) and [SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).
