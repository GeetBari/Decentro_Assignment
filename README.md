# Expense Sharing Service

An expense-sharing app for groups such as trips, flatmates, or dinners. Add members and expenses, see who owes whom, record repayments, and export the expense history to Excel.

**Demo video:** [Watch the walkthrough](https://drive.google.com/file/d/1L4uYmp-l_88obeMvAG4dZrQ2d1IkUJug/view?usp=drive_link)

## What it includes

- Groups, members, and shared expenses
- Equal and custom expense splits
- Balances and settlement suggestions
- Partial or full payment records
- Expense search, category filters, and date filters
- Monthly totals and a spending-by-category chart
- Excel export with formatted dates
- Optional JPG, PNG, or PDF receipt attachment
- Rename and delete controls for groups and expenses
- FastAPI documentation, Postman collection, Docker setup, and automated tests

## Tech stack

- Python and FastAPI
- SQLAlchemy and SQLite
- HTML, CSS, and JavaScript
- Pytest and Docker Compose

## Run locally

Run these commands from the repository root:

```bash
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install packages and start the app:

```bash
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

If PowerShell blocks activation, run commands with `.\.venv\Scripts\python.exe` instead.

Open these links after the server starts:

- [Dashboard](http://127.0.0.1:8000/)
- [Simple API guide](http://127.0.0.1:8000/api-guide)
- [Interactive API documentation](http://127.0.0.1:8000/docs)
- [Health check](http://127.0.0.1:8000/health)

SQLite creates `expenses.db` automatically in the project folder. It is ignored by Git.

## Try it quickly

Use **Load demo data** in the dashboard to create a ready-to-use group, or run:

```bash
python scripts/demo.py
```

The script creates Mohit, Rahul, and Ankit; adds a ₹1,200 dinner; records Rahul's ₹400 payment; and leaves Ankit's ₹400 suggested repayment.

To test the API manually, import [the Postman collection](docs/postman_collection.json). Run its requests in order so it can store generated IDs automatically.

## How balances work

Each expense stores the amount paid and every member's saved share. A person's balance is calculated from what they paid, what they owe, and any repayments they have recorded. This means balances are always derived from the underlying records instead of being stored separately.

Money is stored as integer paise to avoid floating-point rounding problems. For example, ₹100 split between three people becomes ₹33.34, ₹33.33, and ₹33.33.

Settlement suggestions use each member's net position. If A owes B and B owes C, the app can suggest that A pays C directly, reducing the number of payments needed.

## Project structure

```text
app/
  routes.py        API endpoints
  services/        expense, balance, and settlement logic
  models.py        database tables
  static/          dashboard files
tests/             API and business-rule tests
docs/              API, architecture, demo, and verification notes
scripts/demo.py    sample data script
```

## Test and lint

```bash
python -m pytest -q
python -m ruff check app tests scripts
python -m ruff format --check app tests scripts
```

The tests cover validation, equal and custom splits, rounding, balance calculations, settlements, deletion, and concurrent repayment attempts.

## Docker

With Docker Desktop running:

```bash
docker compose up --build -d
```

Open `http://127.0.0.1:8000/`. Use `docker compose down` to stop the containers. The named volume keeps the database between restarts.

## Notes and supporting files

- [Requirements checklist](docs/REQUIREMENTS.md)
- [Architecture and database schema](docs/ARCHITECTURE.md)
- [API examples](docs/API.md)
- [Postman collection](docs/postman_collection.json)
- [Demo walkthrough](docs/DEMO.md)
- [Demo video captions and guide](docs/VIDEO_DEMO.md)
- [Verification notes](docs/VERIFICATION.md)

For a production version, the next steps would be authentication, database migrations, and PostgreSQL for a larger multi-user deployment.
