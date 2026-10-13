# Decentro Assignment

An expense sharing backend for tracking group expenses, calculating balances, and suggesting settlements.

## Project status

Planning and repository setup. The backend is not implemented yet. The checklist below describes the intended scope, not completed functionality. Setup commands and API examples will be added and verified during implementation.

## Planned technology stack

- Python
- FastAPI for the REST API and interactive API documentation
- SQLAlchemy for database models and transactions
- SQLite for a simple local setup
- pytest for automated tests
- Docker for a reproducible runtime

## Required functionality

- [ ] Create and list users.
- [ ] Create groups, add users to groups, and list group members.
- [ ] Record positive-value expenses in valid groups.
- [ ] Split expenses equally among all current group members by default.
- [ ] Exclude self-debts from balances.
- [ ] List expense history for a group.
- [ ] Return structured balances between users.
- [ ] Implement a product enhancement and explain its purpose, decisions, and tradeoffs.

## Planned enhancements and bonuses

- [ ] Smart settlement suggestions based on group net balances.
- [ ] Record payments made between members to settle balances.
- [ ] Support explicit unequal expense splits.
- [ ] Add expense filtering and pagination.
- [ ] Test expense creation, balance calculations, and validation.
- [ ] Provide Docker support.
- [ ] Provide a Postman collection and reproducible demo walkthrough.

## Proposed data model

| Table | Responsibility |
| --- | --- |
| `users` | User identity and display name |
| `groups` | Group details and currency |
| `group_members` | Unique group memberships |
| `expenses` | Payer, amount, description, category, and creation time |
| `expense_splits` | Persisted participant shares for each expense |
| `settlements` | Payments recorded between group members |

## Planned engineering decisions

- Store monetary amounts in integer minor units to avoid floating-point rounding errors.
- Persist expense shares so later membership changes do not change past expenses.
- Distribute rounding remainders deterministically while preserving the total amount.
- Validate membership and require custom shares to sum to the expense total.
- Use IDs to distinguish users who share a display name.
- Keep balances scoped to groups and currencies.
- Keep recorded settlements separate from expenses for an auditable history.
- Document that settlement suggestions use a greedy algorithm and do not guarantee the absolute minimum number of payments.
- Record settlements as payments made elsewhere; the application will not transfer money.

## Submission documentation checklist

- [ ] Verified project setup instructions
- [ ] Architecture overview
- [ ] Database schema and relationships
- [ ] API documentation and example requests
- [ ] Assumptions and design decisions
- [ ] Product enhancement rationale and tradeoffs
- [ ] Test instructions and results
- [ ] Improvements to make with more time

## Local files

The `.gitignore` excludes virtual environments, Python caches, local secrets, SQLite database files, test artifacts, and editor files. A safe `.env.example` may be committed when configuration is introduced.
