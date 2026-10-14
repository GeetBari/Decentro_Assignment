# API guide

Base URL: `http://127.0.0.1:8000`. JSON requests/responses. `/docs` shows all schemas; `/openapi.json` exports the API definition.

| Method | Path | Request / query | Success |
| --- | --- | --- | --- |
| POST | `/users` | `name` | 201 user |
| GET | `/users` | `limit`, `offset` | 200 user list |
| POST | `/groups` | `name`, optional INR `currency` | 201 group |
| GET | `/groups` | `limit`, `offset` | 200 group list |
| POST | `/groups/{group_id}/members` | `user_id` | 201 added user |
| GET | `/groups/{group_id}/members` | None | 200 member list |
| POST | `/expenses` | `group_id`, `paid_by`, `amount`, `description`; optional `category`, `splits` | 201 expense and shares |
| GET | `/groups/{group_id}/expenses` | `limit`, `offset`, `category`, `q`, `date_from`, `date_to` | 200 expense list |
| GET | `/balances` | Required `group_id` | 200 balances, member totals, `is_settled` |
| GET | `/groups/{group_id}/settlement-suggestions` | None | 200 payment plan |
| POST | `/groups/{group_id}/settlements` | `from_user_id`, `to_user_id`, `amount` | 201 recorded payment |
| GET | `/groups/{group_id}/settlements` | `limit`, `offset` | 200 payment list |
| GET | `/health` | None | 200 health status |

Paginated endpoints return arrays, default limit 100, maximum 100, offset 0. Expenses and payments are newest first; IDs break timestamp ties. Users/groups are in ascending ID order. All group members are returned together.

Search `q` is a case-insensitive description substring search using SQLite's comparison behavior (primarily ASCII case folding); `%` and `_` are literals. Categories match exactly. Date filters are inclusive UTC calendar dates in `YYYY-MM-DD`. Unknown groups return 404; empty histories return `[]`.

## Example

Use returned IDs. These examples assume users 1, 2, 3 and group 1 in a fresh database.

Create Mohit, Rahul, and Ankit using `POST /users`:

```json
{"name": "Mohit"}
```

Response: `{"id":1,"name":"Mohit"}`. Repeat for the other names.

Create the group using `POST /groups`:

```json
{"name": "Goa Trip"}
```

Add each user using `POST /groups/1/members`:

```json
{"user_id": 1}
```

Record dinner using `POST /expenses`:

```json
{"group_id": 1, "paid_by": 1, "amount": "1200.00", "description": "Dinner", "category": "food"}
```

The response includes the expense ID, payer ID/name, amount, description, category, split type, UTC timestamp, and three shares of `"400.00"`.

`GET /balances?group_id=1` returns:

```json
{
  "group_id": 1,
  "currency": "INR",
  "is_settled": false,
  "balances": [
    {"from_user_id": 2, "from_name": "Rahul", "to_user_id": 1, "to_name": "Mohit", "amount": "400.00"},
    {"from_user_id": 3, "from_name": "Ankit", "to_user_id": 1, "to_name": "Mohit", "amount": "400.00"}
  ],
  "members": [
    {"user_id": 1, "name": "Mohit", "paid": "1200.00", "share": "400.00", "settled_out": "0.00", "settled_in": "0.00", "net_balance": "800.00"},
    {"user_id": 2, "name": "Rahul", "paid": "0.00", "share": "400.00", "settled_out": "0.00", "settled_in": "0.00", "net_balance": "-400.00"},
    {"user_id": 3, "name": "Ankit", "paid": "0.00", "share": "400.00", "settled_out": "0.00", "settled_in": "0.00", "net_balance": "-400.00"}
  ]
}
```

IDs plus names replace the PDF's name-keyed example to avoid collisions between people with the same name. Fixed decimal strings preserve exact amounts.

Record Rahul's payment using `POST /groups/1/settlements`:

```json
{"from_user_id": 2, "to_user_id": 1, "amount": "400.00"}
```

Settlement suggestions now contain only Ankit to Mohit for `"400.00"`. Expense history is unchanged.

## Unequal expense

```json
{
  "group_id": 1,
  "paid_by": 1,
  "amount": "1000.00",
  "description": "Hotel",
  "splits": [
    {"user_id": 1, "amount": "500.00"},
    {"user_id": 2, "amount": "300.00"},
    {"user_id": 3, "amount": "200.00"}
  ]
}
```

Omit `splits` or send null for equal splitting. An empty list, duplicate participant, non-member, negative share, or incorrect total is rejected.

## Errors and retries

404 means a referenced resource is missing; 409 means duplicate membership/constraint conflict; 422 means invalid input or business rule; 503 means database unavailable or lock timeout.

```json
{"error": {"message": "User already belongs to this group"}}
```

Request validation errors also contain `details` entries with `field` and `message`. Unknown request fields are rejected. Payload validation can take precedence over resource existence checks.

POST requests do not support idempotency keys. Retrying a successful expense request creates a second expense. Settlements are balance-validated but are not generally idempotent. Reconcile uncertain responses before retrying.
