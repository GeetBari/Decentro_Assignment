# Demo walkthrough and interview preparation

## A short demo

1. Start the API using the README's local or Docker instructions. Open `/docs`.
2. Run `python scripts/demo.py` in another terminal. Note the generated group/user IDs.
3. Show the dinner's three saved shares and the two INR 400 debts.
4. Show that Rahul's payment removes his outstanding net balance without changing the dinner record.
5. Add a new member and show that the old expense still has three shares.
6. Create an expense for INR 100 with three participants in a separate group, showing exact remainder handling.
7. Show a rejected expense with a negative amount or a non-member payer.
8. Show settlement suggestions and explain that suggestions do not move money or write records.
9. Run the test suite and open the schema explanation.

For a video, keep the recording focused on this workflow and a short explanation of the database. No video is included in the repository.

## Code reading order

1. `app/models.py`: the six tables and their constraints.
2. `app/services/money.py`: integer paise and deterministic equal splitting.
3. `app/schemas.py`: validation and custom-split checks.
4. `app/services/expenses.py`: atomic expense/share creation.
5. `app/services/balances.py`: pairwise ledger, net positions, and suggestions.
6. `app/database.py`: transaction boundaries and the SQLite write lock.
7. `tests/test_api.py`: expected behavior and edge cases.

## Questions to practice

- Why save expense shares instead of dividing by today's group membership?
- Why can floating-point money produce inconsistent totals?
- Where does the extra paisa go when a split is not divisible?
- What happens if an expense is saved but inserting its shares fails?
- How do two simultaneous settlement requests avoid overpaying?
- What is the difference between pairwise debt and a net balance?
- Why can a zero-net ledger cycle remain after a cross-pair payment?
- Does the greedy algorithm guarantee the fewest possible payments? Why not claim that?
- What happens if a client retries a POST after a network timeout?
- What would have to change for PostgreSQL and multiple concurrent writers?

Use the implementation and tests to answer these in your own words. Before an interview, practice adding a validation rule and a corresponding test without assistance.
