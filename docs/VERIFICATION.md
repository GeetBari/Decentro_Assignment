# Verification notes

Verified locally on 14 October 2026.

| Check | Result |
| --- | --- |
| Python test suite | 47 passed on Windows / Python 3.13.2, including dashboard/asset routing |
| Backend baseline statement coverage | 99% (447 statements, 4 uncovered), measured before the dashboard addition |
| Ruff lint and formatting | Passed |
| Docker image build | Passed with Python 3.13 slim |
| Compose startup and health check | Healthy |
| Container privileges | Confirmed non-root user, UID 1000 |
| End-to-end HTTP demo | Passed: dinner, balances, payment, remaining suggestion |
| Postman collection request sequence | All 20 requests replayed successfully against the container, including expected validation failure |
| Persistent database | Application restart test passed |
| Concurrent settlements | Two competing INR 300 payments against INR 400 debt yielded one 201 and one 422 |
| Atomic expense writes | Simulated share insertion failure rolled back the expense and its shares |
| Dashboard browser checks | Group creation, new/existing members, equal expense preview/save, valid and invalid custom splits, search, and partial payment passed |
| Responsive layout | Desktop and 390px phone viewport visually checked; narrow-screen amount wrapping corrected |
| Browser console | No errors observed during the dashboard checks |

The dashboard is a same-origin HTML/CSS/JavaScript client of the existing API. Browser checks used a separate sample group, Weekend trip, and persisted sample records in the local Docker database. They do not change the repository's source data or seed real users automatically.

The uncovered statements are the database exception-handler responses for integrity/operational errors. Database constraints themselves are tested. One upstream Starlette/AnyIO deprecation warning appears in the test environment; it does not fail the suite.

The Postman JSON and its request sequence were verified programmatically. The collection was not run inside the Postman desktop application. GitHub Actions is configured; its remote status is separate from these local results.

## Scope limits

- No authentication or group authorization; use as a local demo.
- No idempotency keys: uncertain POST responses require reconciliation before retrying.
- INR only; no exchange rates or actual payment processing.
- Greedy settlement suggestions are not guaranteed to minimize transfers globally.
- Pairwise ledger cycles can remain after net settlement; use `is_settled` and suggestions for payment decisions.
- No schema migrations, edits/deletes, load testing, or production deployment.
- The optional demo video is not recorded; a walkthrough is included.
- Reviewer access must be arranged before submitting the private GitHub repository.

These are deliberate scope boundaries or unperformed checks, not claims of production readiness.
