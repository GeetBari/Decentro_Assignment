# Assignment coverage

The attached document specifies an **Expense Sharing Service**. Its filename mentions a different project; this implementation follows the document contents. The original PDF is not redistributed in this repository.

## Required

| Requirement | Implementation / evidence |
| --- | --- |
| Python, with FastAPI/Flask/Django | Python 3.13 and FastAPI; pinned dependencies |
| PostgreSQL/MySQL/SQLite | SQLite via SQLAlchemy |
| Create/list users | POST/GET `/users`; API tests |
| Create groups | POST `/groups`; API tests |
| Add/list group members | POST/GET `/groups/{id}/members`; duplicate and missing-user tests |
| Record expenses | POST `/expenses`; example and custom-split tests |
| Amount greater than zero | Pydantic plus database constraints; zero/negative/precision tests |
| Valid group | Group lookup and foreign keys; missing-group tests |
| Equal split across all members | Default split algorithm; conservation, rounding, and snapshot tests |
| No self-debt | Pairwise ledger excludes payer's own share; single-member and dinner tests |
| Group expense history | GET `/groups/{id}/expenses`; history/filter tests |
| Structured balances | GET `/balances?group_id=...`; exact PDF example test |
| Additional product feature | Settlement suggestions; algorithm invariant tests |
| Explain enhancement purpose/decisions/tradeoffs | README and architecture guide |
| GitHub repository | `GeetBari/Decentro_Assignment` |
| README and setup instructions | Root README, local and Docker steps |
| API documentation | `docs/API.md`, live `/docs`, `/openapi.json` |
| Database schema explanation | `docs/ARCHITECTURE.md` and `app/models.py` |
| Architecture, assumptions, design choices, future work | README and architecture guide |

## Optional bonuses

| Bonus | Implementation |
| --- | --- |
| Record balance settlements | Settlement routes with partial-payment and overpayment tests |
| Unequal splits | Explicit `splits` request field and validation tests |
| Unit tests | Money and algorithm tests, plus API/database integration tests |
| Docker | Dockerfile and Compose with persistent volume and health check |
| Postman collection | `docs/postman_collection.json`, generated IDs captured as variables |
| Demo video | Not recorded; `docs/DEMO.md` supplies a walkthrough and `scripts/demo.py` runs the example |

## Intentional API differences

- IDs plus names replace name-keyed balance objects so duplicate names work correctly.
- Money responses are decimal strings to avoid losing precision in clients.
- `/balances` requires a group ID; debts from different groups are never silently combined.
- The membership path supplies `group_id`; the body only needs `user_id`.
- Extra expense/payment details support auditability, while all required fields are available.

Before submission, confirm reviewer access to the private repository and use the verification notes to distinguish actual checks from planned future work.
